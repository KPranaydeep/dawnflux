import pandas as pd
import pytest
from src.sleep import sleep_duration, clock_distance, add_regularity
from src.validation import validate_sleep


def test_midnight_and_dst():
    assert clock_distance('2026-01-01T23:50Z', '2026-01-02T00:10Z') == 20
    assert sleep_duration('2026-03-07T23:00-05:00', '2026-03-08T07:00-04:00') == 7


def test_regularity_consecutive_only(sleep):
    next_day = sleep.copy()
    for c in ['bedtime', 'sleep_onset', 'wake_time']:
        next_day[c] = next_day[c].map(lambda x: (pd.Timestamp(x) + pd.Timedelta(days=1, minutes=20)).isoformat())
    next_day.date = '2026-09-03'
    result = add_regularity(pd.concat([sleep, next_day]))
    assert pd.isna(result.sleep_regularity.iloc[0])
    assert result.sleep_regularity.iloc[1] == 80
    next_day.date = '2026-09-05'
    assert add_regularity(pd.concat([sleep, next_day])).sleep_regularity.isna().all()


def test_duration_mismatch(sleep):
    sleep.sleep_duration = 7
    with pytest.raises(ValueError):
        validate_sleep(sleep)
