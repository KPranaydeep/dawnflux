"""Private SQLite or per-browser-session in-memory SQLite. No global cache."""
import json
import sqlite3
from pathlib import Path
import pandas as pd
from src.validation import (LIGHT_COLUMNS, SLEEP_COLUMNS, DEFAULT_SETTINGS,
                            validate_light, validate_sleep, validate_settings)
from src.sleep import add_regularity


class Database:
    def __init__(self, path=':memory:'):
        if path != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, record_key TEXT, payload TEXT, PRIMARY KEY(kind, record_key))')
        self.connection.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT)')

    def settings(self):
        row = self.connection.execute('SELECT payload FROM settings WHERE id=1').fetchone()
        return json.loads(row[0]) if row else DEFAULT_SETTINGS.copy()

    def save_settings(self, settings):
        settings = validate_settings(settings)
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO settings VALUES (1, ?)', (json.dumps(settings),))

    def read(self, kind):
        columns = LIGHT_COLUMNS if kind == 'light' else SLEEP_COLUMNS
        rows = self.connection.execute('SELECT payload FROM records WHERE kind=? ORDER BY record_key', (kind,)).fetchall()
        frame = pd.DataFrame([json.loads(row[0]) for row in rows], columns=columns)
        return add_regularity(frame) if kind == 'sleep' else frame

    def import_batch(self, light=None, sleep=None, settings=None):
        """Atomic insert, identical re-import is idempotent; conflicts never overwrite."""
        staged = []
        for kind, frame, validator in [('light', light, validate_light), ('sleep', sleep, validate_sleep)]:
            if frame is None or frame.empty:
                continue
            new = validator(frame)
            old = self.read(kind)
            # Regularity is derived from the complete timeline, not trusted input.
            if kind == 'sleep':
                new['sleep_regularity'] = None
                old['sleep_regularity'] = None
            keys = ['session_id', 'timestamp'] if kind == 'light' else ['date']
            combined = pd.concat([old, new], ignore_index=True)
            for _, group in combined.groupby(keys, dropna=False):
                if len(group.drop_duplicates()) > 1:
                    raise ValueError('Conflicting record already exists. Correct the exported dataset and import in a fresh session.')
            combined = combined.drop_duplicates(subset=keys)
            validator(combined)
            for record in json.loads(new.to_json(orient='records')):
                key = json.dumps([record[k] for k in keys])
                staged.append((kind, key, json.dumps(record, allow_nan=False)))
        if settings is not None:
            settings = validate_settings(settings)
        with self.connection:
            self.connection.executemany('INSERT OR IGNORE INTO records VALUES (?, ?, ?)', staged)
            if settings is not None:
                self.connection.execute('INSERT OR REPLACE INTO settings VALUES (1, ?)', (json.dumps(settings),))

    def export_json(self):
        return json.dumps(dict(schema_version=1, settings=self.settings(),
            morning_light=json.loads(self.read('light').to_json(orient='records')),
            sleep=json.loads(self.read('sleep').to_json(orient='records'))), indent=2, allow_nan=False)

    def import_json(self, content):
        data = json.loads(content)
        if not isinstance(data, dict) or data.get('schema_version') != 1:
            raise ValueError('Expected Dawnflux schema_version 1 JSON backup.')
        if not {'morning_light', 'sleep', 'settings'}.issubset(data):
            raise ValueError('Backup requires morning_light, sleep and settings.')
        light = pd.DataFrame(data['morning_light']) if data['morning_light'] else pd.DataFrame(columns=LIGHT_COLUMNS)
        sleep = pd.DataFrame(data['sleep']) if data['sleep'] else pd.DataFrame(columns=SLEEP_COLUMNS)
        self.import_batch(light, sleep, data['settings'])
