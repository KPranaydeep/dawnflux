"""Real PostgreSQL tests; CI supplies an ephemeral service, never health data."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import pandas as pd
import psycopg
import pytest
from src.postgres import PostgresDatabase, StorageError

DSN = os.environ.get('DAWNFLUX_TEST_DSN')
pytestmark = pytest.mark.skipif(not DSN, reason='Requires ephemeral PostgreSQL test service')


@pytest.fixture
def remote():
    with psycopg.connect(DSN) as connection:
        connection.execute((Path(__file__).parents[1] / 'migrations/001_private_storage.sql').read_text())
    owner = uuid4().hex * 2
    return PostgresDatabase(DSN, owner, local_test=True)


def test_survives_new_session_and_keeps_other_account_private(remote, light, sleep):
    remote.import_batch(light, sleep)
    fresh = PostgresDatabase(DSN, remote._owner, local_test=True)
    assert len(fresh.read('light')) == 2
    assert len(fresh.read('sleep')) == 1
    other = PostgresDatabase(DSN, uuid4().hex * 2, local_test=True)
    assert other.read('light').empty and other.read('sleep').empty


def test_atomic_conflicts_and_restore(remote, light, sleep):
    remote.import_batch(light, sleep)
    before = remote.export_json()
    conflict = sleep.copy()
    conflict.notes = 'Conflicting correction'
    with pytest.raises(ValueError, match='Conflicting'):
        remote.import_batch(sleep=conflict, settings={**remote.settings(), 'initial_target': 123})
    remote.refresh()
    assert remote.export_json() == before
    remote.import_json(before)
    assert remote.export_json() == before


def test_concurrent_nonoverlapping_sessions_both_survive(remote, light):
    other = light.copy()
    other.session_id = 'parallel-second'
    for col in ['timestamp', 'session_start', 'session_end']:
        other[col] = other[col].map(lambda x: (pd.Timestamp(x) + pd.Timedelta(hours=1)).isoformat())
    other.minutes_after_waking += 60
    clients = [PostgresDatabase(DSN, remote._owner, local_test=True) for _ in range(2)]
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(c.import_batch, light=f) for c, f in zip(clients, [light, other])]
        for future in futures:
            future.result()
    remote.refresh()
    assert len(remote.read('light')) == 4


def test_concurrent_overlaps_cannot_bypass_validation(remote, light):
    other = light.copy()
    other.session_id = 'overlap-second'
    clients = [PostgresDatabase(DSN, remote._owner, local_test=True) for _ in range(2)]
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(c.import_batch, light=f) for c, f in zip(clients, [light, other])]
        errors = []
        for future in futures:
            try:
                future.result()
            except ValueError as exc:
                errors.append(exc)
    assert len(errors) == 1
    remote.refresh()
    assert len(remote.read('light')) == 2


def test_save_failure_does_not_adopt_or_leak_connection(remote, light, monkeypatch):
    before = remote.export_json()
    def fail():
        raise psycopg.OperationalError('password=DO_NOT_EXPOSE')
    monkeypatch.setattr(remote, '_connect', fail)
    with pytest.raises(StorageError) as exc:
        remote.import_batch(light=light)
    assert 'DO_NOT_EXPOSE' not in str(exc.value)
    assert remote.export_json() == before


def test_cloud_settings_persist_and_android_does_not_reset_them(remote, light):
    remote.save_settings({**remote.settings(), 'initial_target': 12345})
    remote.import_json(json.dumps({'schema_version': 1, 'morning_light': json.loads(light.to_json(orient='records'))}))
    fresh = PostgresDatabase(DSN, remote._owner, local_test=True)
    assert fresh.settings()['initial_target'] == 12345
    assert fresh.revision == 2


def test_daily_merge_returns_report_and_preserves_cloud_history(remote, light, sleep):
    remote.import_batch(sleep=sleep)
    conflict = sleep.copy()
    conflict.notes = 'Uploaded correction'
    payload = json.dumps(dict(schema_version=1, morning_light=light.to_dict('records'), sleep=conflict.to_dict('records')))
    report = remote.import_json(payload, conflict_policy='keep_existing')
    assert report['added_light_sessions'] == 1
    assert report['kept_conflicts'] == ['sleep: 2026-09-02']
    fresh = PostgresDatabase(DSN, remote._owner, local_test=True)
    assert fresh.read('sleep').iloc[0].notes == 'Synthetic test'
    assert len(fresh.read('light')) == 2
