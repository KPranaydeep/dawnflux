from pathlib import Path
from streamlit.testing.v1 import AppTest
from src.database import Database
from src.postgres import PostgresDatabase
from src.storage_ui import _current_client


def legacy_client(current, cls):
    # Same qualified class name, but an older API retained by session_state.
    old_type = type(cls.__name__, (), {'__module__': cls.__module__,
        'import_json': lambda self, content: None})
    old = old_type()
    old.__dict__.update(current.__dict__)
    return old


def test_live_temporary_session_upgrade_preserves_records(light, sleep, monkeypatch):
    monkeypatch.delenv('DAWNFLUX_DB_PATH', raising=False)
    db = Database()
    db.import_batch(light, sleep)
    original = db.export_json()
    old = legacy_client(db, Database)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'streamlit_app.py', default_timeout=30)
    app.session_state.db = old
    app.run()
    assert not app.exception
    updated = app.session_state.db
    assert type(updated) is Database
    assert updated.connection is db.connection
    assert updated.export_json() == original
    report = updated.import_json(original, conflict_policy='keep_existing')
    assert report['unchanged'] == 2
    assert updated.export_json() == original


def test_postgres_upgrade_retains_identity_and_private_snapshot():
    # No network: exercise state transfer only, not production credentials.
    current = PostgresDatabase.__new__(PostgresDatabase)
    current.__dict__.update(connection=Database().connection, _owner='synthetic-owner',
                            _dsn='synthetic-dsn', revision=5, updated_at=None)
    old = legacy_client(current, PostgresDatabase)
    upgraded = _current_client(old, PostgresDatabase)
    assert type(upgraded) is PostgresDatabase
    assert upgraded.__dict__ == current.__dict__
    assert _current_client(upgraded, PostgresDatabase) is upgraded
