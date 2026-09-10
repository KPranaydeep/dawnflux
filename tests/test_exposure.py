import numpy as np
import pandas as pd
import pytest
from src.exposure import integrate, daily_exposure
from src.validation import validate_light


def test_trapezoid_irregular():
    c, coverage = integrate(['2026-01-01T07:00Z', '2026-01-01T07:01Z', '2026-01-01T07:03Z'], [100, 300, 500])
    assert list(c) == [0, 200, 1000]
    assert coverage == 1


def test_gap_not_imputed():
    c, coverage = integrate(['2026-01-01T07:00Z', '2026-01-01T07:01Z', '2026-01-01T07:11Z'], [100, 100, 100])
    assert c[-1] == 100
    assert coverage == pytest.approx(1 / 11)


@pytest.mark.parametrize('lux', [[-1, 1], [np.nan, 1], [np.inf, 1]])
def test_bad_lux(lux):
    with pytest.raises(ValueError):
        integrate(['2026-01-01T07:00Z', '2026-01-01T07:01Z'], lux)


def test_duplicate_timestamp():
    with pytest.raises(ValueError):
        integrate(['2026-01-01T07:00Z'] * 2, [100, 100])


def test_manual_contract(light):
    f = validate_light(light)
    assert daily_exposure(f).dose.iloc[0] == 10000
    assert f.target_reached.tolist() == [False, True]


@pytest.mark.parametrize('field,value', [('cumulative_lux_minutes', 42), ('minutes_after_waking', 99), ('target_reached', 'yes'), ('date', '2026-09-03')])
def test_reject_inconsistent_contract(light, field, value):
    light[field] = value
    with pytest.raises(ValueError):
        validate_light(light)


def test_overlap_rejected(light):
    other = light.copy()
    other.session_id = 'overlap'
    with pytest.raises(ValueError, match='overlap'):
        validate_light(pd.concat([light, other]))
