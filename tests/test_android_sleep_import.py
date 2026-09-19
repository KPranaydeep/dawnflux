import json
import pandas as pd
import pytest
from src.database import Database


def record(day='2026-09-19'):
    return dict(date=day, bedtime=None, sleep_onset=f'{day}T00:00:00+05:30',
                wake_time=f'{day}T08:00:00+05:30', sleep_duration=8,
                sleep_score=80, sleep_regularity=None, notes='Android')


def test_sleep_only_bundle_is_idempotent_and_computes_regularity():
    db = Database()
    payload = json.dumps(dict(schema_version=1, morning_light=[], sleep=[record('2026-09-18'), record()]))
    db.import_json(payload)
    db.import_json(payload)
    data = db.read('sleep')
    assert len(data) == 2
    assert data.bedtime.isna().all()
    assert data.iloc[1].sleep_regularity == 100
    restored = Database()
    restored.import_json(db.export_json())
    pd.testing.assert_frame_equal(data, restored.read('sleep'))


def test_missing_bedtime_does_not_bypass_duration_validation():
    row = record()
    row['sleep_duration'] = 9
    with pytest.raises(ValueError, match='duration disagrees'):
        Database().import_batch(sleep=pd.DataFrame([row]))


def test_invalid_light_rolls_back_sleep_bundle():
    db = Database()
    with pytest.raises(ValueError):
        db.import_json(json.dumps(dict(schema_version=1, morning_light=[{'bad': 1}], sleep=[record()])))
    assert db.read('sleep').empty
