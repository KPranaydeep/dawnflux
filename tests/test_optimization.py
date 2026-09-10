import pandas as pd
from src.optimization import estimate_target


def evidence():
    return pd.DataFrame([dict(outcome_date=d.strftime('%Y-%m-%d'), dose=8000 + (i % 7) * 1000,
                             sleep_duration=8 if i % 7 >= 3 else 6, minutes_after_waking=20)
                         for i, d in enumerate(pd.date_range('2026-08-14', periods=28))])


def test_insufficient_data():
    result = estimate_target(evidence().iloc[:10], 10000, 8, '2026-09-10')
    assert result['target'] == 10000
    assert result['confidence'] == 'Insufficient data'


def test_capped_and_no_ratcheting():
    a = estimate_target(evidence(), 10000, 8, '2026-09-10')
    b = estimate_target(evidence(), 10000, 8, '2026-09-10')
    assert a == b
    assert a['target'] == 11000
    assert a['confidence'] == 'Low — observational'


def test_confounded_timing_no_update():
    p = evidence()
    p.loc[p.dose > p.dose.median(), 'minutes_after_waking'] = 100
    assert estimate_target(p, 10000, 8, '2026-09-10')['target'] == 10000


def test_stale_data_no_update():
    assert estimate_target(evidence(), 10000, 8, '2027-09-10')['n'] == 0


def test_inconsistent_halves_no_update():
    p = evidence()
    p.loc[14:, 'sleep_duration'] = 6
    assert estimate_target(p, 10000, 8, '2026-09-10')['target'] == 10000
