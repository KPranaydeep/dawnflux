"""Neon/PostgreSQL persistence with per-owner records and serialized mutations.

SQLite remains the private per-rerun read snapshot and existing validation engine.
No server connection or health data is cached across browser sessions.
"""
import json
import re
import certifi
import psycopg
from psycopg.types.json import Jsonb
from src.database import Database
from src.validation import DEFAULT_SETTINGS


class StorageError(RuntimeError):
    """Safe user-visible error. Never expose a DSN or raw database exception."""


class PostgresDatabase(Database):
    def __init__(self, dsn, owner, *, local_test=False):
        if not re.fullmatch(r'[a-f0-9]{64}', owner):
            raise ValueError('A verified account identifier is required.')
        self._dsn, self._owner, self._local_test = dsn, owner, local_test
        self.revision, self.updated_at = 0, None
        super().__init__()
        self.refresh()

    def _connect(self):
        # Explicit kwargs override insecure sslmode parameters in supplied DSNs.
        options = {} if self._local_test else dict(sslmode='verify-full', sslrootcert=certifi.where())
        return psycopg.connect(self._dsn, connect_timeout=10, prepare_threshold=None, **options)

    def _snapshot(self, conn, lock=False):
        conn.execute("SELECT set_config('statement_timeout', '15000', true)")
        conn.execute("SELECT set_config('lock_timeout', '10000', true)")
        if lock:
            conn.execute('INSERT INTO dawnflux_owners(owner_id, settings) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                         (self._owner, Jsonb(DEFAULT_SETTINGS)))
        row = conn.execute('SELECT settings, revision, updated_at FROM dawnflux_owners WHERE owner_id=%s'
                           + (' FOR UPDATE' if lock else ''), (self._owner,)).fetchone()
        staged = Database()
        if row:
            staged.save_settings(row[0])
            records = conn.execute('SELECT kind, record_key, payload FROM dawnflux_records WHERE owner_id=%s',
                                   (self._owner,)).fetchall()
            with staged.connection:
                staged.connection.executemany('INSERT INTO records VALUES (?,?,?)',
                    [(kind, key, json.dumps(payload)) for kind, key, payload in records])
        else:
            records = []
        return staged, row, {(kind, key) for kind, key, _ in records}

    def _adopt(self, staged, revision, updated_at):
        old = self.connection
        self.connection = staged.connection
        old.close()
        self.revision, self.updated_at = revision, updated_at

    def refresh(self):
        staged = None
        try:
            with self._connect() as conn:
                # Both SELECTs see a single consistent snapshot.
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                staged, row, _ = self._snapshot(conn)
            self._adopt(staged, row[1] if row else 0, row[2] if row else None)
        except psycopg.Error:
            if staged is not None:
                staged.connection.close()
            raise StorageError('Private storage is unavailable. No temporary fallback was opened. Please retry later.') from None

    def _mutate(self, operation, *args, **kwargs):
        staged = None
        try:
            with self._connect() as conn:
                # Lock per account BEFORE reading and validating. Parallel imports
                # merge against the latest committed records, never a stale snapshot.
                staged, row, existing = self._snapshot(conn, lock=True)
                report = operation(staged, *args, **kwargs)
                records = staged.connection.execute('SELECT kind, record_key, payload FROM records').fetchall()
                with conn.cursor() as cursor:
                    cursor.executemany('INSERT INTO dawnflux_records(owner_id,kind,record_key,payload) VALUES (%s,%s,%s,%s)',
                        [(self._owner, kind, key, Jsonb(json.loads(payload)))
                         for kind, key, payload in records if (kind, key) not in existing])
                result = conn.execute('UPDATE dawnflux_owners SET settings=%s, revision=revision+1, updated_at=now() '
                    'WHERE owner_id=%s RETURNING revision, updated_at', (Jsonb(staged.settings()), self._owner)).fetchone()
            # Only show success / adopt local state AFTER COMMIT succeeds.
            self._adopt(staged, result[0], result[1])
            staged = None
            return report
        except psycopg.Error:
            raise StorageError('The save could not be confirmed. Reload to check saved records before retrying a manual entry. Re-importing the same file is safe.') from None
        finally:
            if staged is not None:
                staged.connection.close()

    def save_settings(self, settings):
        self._mutate(Database.save_settings, settings)

    def import_batch(self, light=None, sleep=None, settings=None, conflict_policy="reject"):
        return self._mutate(Database.import_batch, light, sleep, settings, conflict_policy=conflict_policy)

    def import_json(self, content, conflict_policy="reject"):
        return self._mutate(Database.import_json, content, conflict_policy=conflict_policy)
