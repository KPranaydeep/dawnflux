import pandas as pd
import pytest
from src.statistics import pair_days, window_statistics, correlation, exposure_bands


def test_pair_next_night(light, sleep):
    pair = pair_days(light, sleep)
    assert len(pair) == 1
    assert pair.outcome_date.iloc[0] == '2026-09-02'
    sleep.date = '2026-09-01'
    assert pair_days(light, sleep).empty


def test_calendar_window_not_last_n_rows():
    f = pd.DataFrame({'date': ['2026-08-01', '2026-09-04', '2026-09-10', '2026-09-11'], 'dose': [99999, 100, 300, 99999]})
    stats = window_statistics(f, '2026-09-10')
    assert stats.n.tolist() == [2, 2, 2]
    assert stats['median'].tolist() == [200, 200, 200]


def test_correlation_guards():
    f = pd.DataFrame({'x': range(10), 'y': range(10)})
    assert correlation(f, 'x', 'y')['rho'] == pytest.approx(1)
    assert correlation(f.iloc[:3], 'x', 'y')['rho'] is None
    f.y = 1
    assert correlation(f, 'x', 'y')['rho'] is None


def test_bands_boundaries():
    f = pd.DataFrame({'dose': [749, 750, 1249, 1250], 'sleep_duration': [8] * 4, 'sleep_score': [None] * 4})
    assert exposure_bands(f, 1000).n.tolist() == [1, 2, 1]
