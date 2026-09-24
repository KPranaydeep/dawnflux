import json
import pandas as pd
import pytest
from src.database import Database
from src.exposure import manual_session


def sensor_day(day, sid):
    wake = pd.Timestamp(f'{day}T07:00:00+05:30')
    return manual_session(sid, wake, wake + pd.Timedelta(seconds=1234),
                          20.123456789123, 500.123456789123, 20000)


def test_yesterday_rounded_backup_then_full_precision_android_export():
    yesterday = sensor_day('2026-09-23', 'yesterday')
    today = sensor_day('2026-09-24', 'today')
    db = Database()
    # Match historical backup rounding, independently of the new exporter.
    backup = dict(schema_version=1, settings=db.settings(), sleep=[],
                  morning_light=json.loads(yesterday.to_json(orient='records', double_precision=10)))
    db.import_json(json.dumps(backup))
    original = db.read('light').copy()
    upload = json.dumps(dict(schema_version=1, sleep=[],
        morning_light=pd.concat([yesterday, today]).to_dict('records')))
    report = db.import_json(upload)
    assert report['unchanged'] == 1
    assert report['added_light_sessions'] == 1
    assert len(db.read('light')) == 4
    pd.testing.assert_frame_equal(original, db.read('light').query('session_id == "yesterday"').reset_index(drop=True), check_dtype=False)
    assert db.import_json(upload)['added_light_sessions'] == 0


def test_timestamp_spelling_is_not_a_conflict(light):
    db = Database()
    db.import_batch(light=light)
    other = light.copy()
    for column in ['timestamp', 'wake_time', 'session_start', 'session_end']:
        other[column] = other[column].map(lambda x: pd.Timestamp(x).isoformat(timespec='milliseconds'))
    assert db.import_batch(light=other)['unchanged'] == 1
    assert len(db.read('light')) == 2


def test_keep_existing_skips_whole_sessions_and_sleep_days(light, sleep):
    db = Database()
    db.import_batch(light, sleep)
    before_light, before_sleep = db.read('light'), db.read('sleep')
    conflict = light.copy()
    conflict.target_lux_minutes = 20000
    conflict.target_reached = False
    # Different sample count must not create a hybrid session.
    midpoint = conflict.iloc[[0]].copy()
    midpoint.timestamp = '2026-09-01T07:30:00+05:30'
    midpoint.cumulative_lux_minutes = 5000
    conflict = pd.concat([conflict, midpoint])
    conflict_sleep = sleep.copy()
    conflict_sleep.sleep_score = 99
    newer = sensor_day('2026-09-24', 'today')
    report = db.import_batch(pd.concat([conflict, newer]), conflict_sleep, conflict_policy='keep_existing')
    assert report['kept_conflicts'] == ['light: test-session', 'sleep: 2026-09-02']
    assert report['added_light_sessions'] == 1
    pd.testing.assert_frame_equal(before_light, db.read('light').query('session_id == "test-session"').reset_index(drop=True), check_dtype=False)
    pd.testing.assert_frame_equal(before_sleep, db.read('sleep'))


def test_real_conflict_still_rejects_atomically(light, sleep):
    db = Database()
    db.import_batch(sleep=sleep)
    sleep.sleep_score = 1
    with pytest.raises(ValueError, match='2026-09-02'):
        db.import_batch(light, sleep)
    assert db.read('light').empty


def test_keep_existing_does_not_bypass_validation(light, sleep):
    db = Database()
    db.import_batch(light=light)
    light.cumulative_lux_minutes = -1
    with pytest.raises(ValueError):
        db.import_batch(light, sleep, conflict_policy='keep_existing')
    assert db.read('sleep').empty
