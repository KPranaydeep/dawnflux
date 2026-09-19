"""Canonical v1 contract. Reject invalid batches before any database write."""
from datetime import date, time
from zoneinfo import ZoneInfo
import re
import numpy as np
import pandas as pd
from src.exposure import integrate
from src.sleep import sleep_duration

LIGHT_COLUMNS = 'session_id date timestamp lux cumulative_lux_minutes wake_time session_start session_end minutes_after_waking target_lux_minutes target_reached measurement_quality'.split()
SLEEP_COLUMNS = 'date bedtime sleep_onset wake_time sleep_duration sleep_score sleep_regularity notes'.split()
DEFAULT_SETTINGS = dict(timezone='Asia/Kolkata', wake_time='07:00', sleep_target=8.0, initial_target=10000.0)


def validate_settings(settings):
    if set(settings) != set(DEFAULT_SETTINGS):
        raise ValueError('Settings must contain timezone, wake_time, sleep_target and initial_target.')
    s = dict(settings)
    try:
        ZoneInfo(s['timezone'])
        time.fromisoformat(s['wake_time'])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('Use an IANA timezone and HH:MM wake time.') from exc
    for field, low, high in [('sleep_target', 1, 16), ('initial_target', 1, 10000000)]:
        s[field] = float(s[field])
        if not np.isfinite(s[field]) or not low <= s[field] <= high:
            raise ValueError(f'{field} must be between {low} and {high}.')
    return s


def _base(frame, columns):
    if set(frame.columns) != set(columns):
        raise ValueError('Expected exactly these columns: ' + ', '.join(columns))
    f = frame[columns].copy().reset_index(drop=True)
    for value in f.date:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('date must be YYYY-MM-DD.')
        date.fromisoformat(value)
    return f


def _timestamp(value):
    t = pd.Timestamp(value)
    if pd.isna(t) or t.tzinfo is None:
        raise ValueError('Timestamps require an explicit timezone offset, e.g. 2026-09-10T07:00:00+05:30.')
    return t


def _numeric(f, name, low, high, nullable=False):
    v = pd.to_numeric(f[name], errors='raise')
    valid = v.isna() if nullable else pd.Series(False, index=v.index)
    if not (valid | (np.isfinite(v) & v.between(low, high))).all():
        raise ValueError(f'{name} must be finite and between {low} and {high}.')
    f[name] = v


def _boolean(value):
    if str(value).lower() not in ('true', 'false', '1', '0'):
        raise ValueError('target_reached must be true or false.')
    return str(value).lower() in ('true', '1')


def validate_light(frame):
    f = _base(frame, LIGHT_COLUMNS)
    if f.empty:
        return f
    if f[['timestamp', 'wake_time', 'session_start', 'session_end']].isna().any().any():
        raise ValueError('All light timestamps are required.')
    if not f.session_id.map(lambda s: isinstance(s, str) and 0 < len(s) <= 128).all():
        raise ValueError('session_id must be a nonempty string of at most 128 characters.')
    for c in ['lux', 'cumulative_lux_minutes', 'minutes_after_waking', 'target_lux_minutes']:
        _numeric(f, c, 1 if c == 'target_lux_minutes' else 0, 1e12)
    f['target_reached'] = f.target_reached.map(_boolean)
    if not f.measurement_quality.isin(['good', 'manual', 'gapped', 'poor']).all():
        raise ValueError('measurement_quality must be good, manual, gapped or poor.')
    intervals = []
    for sid, g in f.groupby('session_id'):
        for c in ['date', 'wake_time', 'session_start', 'session_end', 'minutes_after_waking', 'target_lux_minutes', 'measurement_quality']:
            if g[c].nunique(dropna=False) != 1:
                raise ValueError(f'Session {sid}: {c} must be constant across readings.')
        row = g.iloc[0]
        start, end, wake = map(_timestamp, [row.session_start, row.session_end, row.wake_time])
        if not wake <= start < end or end - start > pd.Timedelta(hours=24):
            raise ValueError('Sessions must start after waking and last >0 and ≤24 hours.')
        if start.date().isoformat() != row.date or wake.date().isoformat() != row.date:
            raise ValueError('Light date must equal the local wake and session-start date.')
        times = [_timestamp(x) for x in g.timestamp]
        order = np.argsort([t.value for t in times])
        g = g.iloc[order]
        times = [times[i] for i in order]
        if times[0] != start or times[-1] != end:
            raise ValueError('First/last reading must match session_start/session_end.')
        gap_limit = float('inf') if row.measurement_quality == 'manual' else 120
        cumulative, coverage = integrate(times, g.lux, gap_limit)
        if coverage < 1 and row.measurement_quality == 'good':
            raise ValueError('Gaps over 120 seconds require gapped or poor quality.')
        if not np.allclose(cumulative, g.cumulative_lux_minutes, rtol=1e-5, atol=.01):
            raise ValueError('Cumulative dose disagrees with the documented trapezoidal integration.')
        if not np.isclose((start - wake).total_seconds() / 60, row.minutes_after_waking, atol=.01):
            raise ValueError('minutes_after_waking disagrees with session_start minus wake_time.')
        if not np.array_equal(g.target_reached.to_numpy(), cumulative >= row.target_lux_minutes):
            raise ValueError('target_reached must agree with cumulative dose at each reading.')
        intervals.append((start, end, sid))
    intervals.sort()
    if any(b[0] < a[1] for a, b in zip(intervals, intervals[1:])):
        raise ValueError('Sessions overlap; importing would double-count exposure.')
    return f.sort_values(['date', 'session_id', 'timestamp']).reset_index(drop=True)


def validate_sleep(frame):
    f = _base(frame, SLEEP_COLUMNS)
    if f.date.duplicated().any():
        raise ValueError('Sleep contains duplicate wake dates.')
    _numeric(f, 'sleep_duration', .001, 24)
    _numeric(f, 'sleep_score', 0, 100, nullable=True)
    _numeric(f, 'sleep_regularity', 0, 100, nullable=True)
    for row in f.itertuples():
        onset, wake = map(_timestamp, [row.sleep_onset, row.wake_time])
        bed = onset if pd.isna(row.bedtime) else _timestamp(row.bedtime)
        if not bed <= onset < wake or wake - bed > pd.Timedelta(hours=24):
            raise ValueError('Require bedtime ≤ sleep onset < wake, within 24 hours.')
        if wake.date().isoformat() != row.date:
            raise ValueError('Sleep date is the local wake date.')
        if not np.isclose(sleep_duration(onset, wake), row.sleep_duration, atol=.01):
            raise ValueError('Sleep duration disagrees with timestamps (hours required).')
    f['notes'] = f.notes.fillna('').astype(str)
    return f
