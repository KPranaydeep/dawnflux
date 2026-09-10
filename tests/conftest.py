import pandas as pd
import pytest
from src.exposure import manual_session


@pytest.fixture
def light():
    wake = pd.Timestamp('2026-09-01T07:00:00+05:30')
    return manual_session('test-session', wake, wake + pd.Timedelta(minutes=20), 20, 500, 10000)


@pytest.fixture
def sleep():
    return pd.DataFrame([dict(date='2026-09-02', bedtime='2026-09-01T22:30:00+05:30',
        sleep_onset='2026-09-01T23:00:00+05:30', wake_time='2026-09-02T07:00:00+05:30',
        sleep_duration=8., sleep_score=None, sleep_regularity=None, notes='Synthetic test')])
