import io
import pandas as pd
import pytest
from src.database import Database


def test_roundtrip_and_idempotency(light, sleep):
    db = Database()
    db.import_batch(light, sleep)
    restored = Database()
    restored.import_json(db.export_json())
    restored.import_json(db.export_json())
    assert restored.export_json() == db.export_json()
    assert len(restored.read('light')) == 2
    csv = pd.read_csv(io.StringIO(db.read('light').to_csv(index=False)))
    restored.import_batch(light=csv)
    assert len(restored.read('light')) == 2


def test_atomic_rejection(light, sleep):
    db = Database()
    sleep.sleep_duration = -1
    with pytest.raises(ValueError):
        db.import_batch(light, sleep)
    assert db.read('light').empty


def test_conflict_never_overwrites(light, sleep):
    db = Database()
    db.import_batch(sleep=sleep)
    sleep.notes = 'Changed'
    with pytest.raises(ValueError, match='Conflicting'):
        db.import_batch(light, sleep)
    assert db.read('light').empty
    assert db.read('sleep').notes.iloc[0] == 'Synthetic test'


def test_persistence_and_session_isolation(tmp_path, light):
    path = str(tmp_path / 'private.db')
    db = Database(path)
    db.import_batch(light=light)
    assert len(Database(path).read('light')) == 2
    assert Database().read('light').empty
