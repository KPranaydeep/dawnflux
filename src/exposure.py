"""Transparent light integration; lux·minutes is not a biological dose metric."""
import numpy as np
import pandas as pd


def integrate(timestamps, lux, max_gap_seconds=120):
    """Trapezoidal integral; exclude long gaps rather than invent exposure."""
    t = pd.to_datetime(timestamps, utc=True)
    values = np.asarray(lux, dtype=float)
    if len(t) != len(values) or len(t) < 2:
        raise ValueError("A session needs at least two paired readings.")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Lux must be finite and nonnegative.")
    seconds = np.diff(t.as_unit('ns').astype('int64')) / 1e9
    if (seconds <= 0).any():
        raise ValueError("Readings must have unique, increasing timestamps.")
    valid = seconds <= max_gap_seconds
    increments = (values[:-1] + values[1:]) / 2 * seconds / 60
    cumulative = np.r_[0, np.cumsum(np.where(valid, increments, 0))]
    return cumulative, float(seconds[valid].sum() / seconds.sum())


def manual_session(session_id, wake, start, duration_minutes, average_lux, target):
    """Two synthetic endpoints, explicitly marked manual, never sensor readings."""
    end = start + pd.Timedelta(minutes=duration_minutes)
    dose = average_lux * duration_minutes
    return pd.DataFrame([dict(session_id=session_id, date=start.date().isoformat(),
        timestamp=t.isoformat(), lux=average_lux, cumulative_lux_minutes=c,
        wake_time=wake.isoformat(), session_start=start.isoformat(), session_end=end.isoformat(),
        minutes_after_waking=(start - wake).total_seconds() / 60,
        target_lux_minutes=target, target_reached=c >= target, measurement_quality='manual')
        for t, c in [(start, 0.0), (end, dose)]])


def summarize_sessions(readings):
    columns = ['session_id', 'date', 'dose', 'minutes_after_waking', 'measurement_quality', 'target_reached']
    if readings.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for sid, group in readings.groupby('session_id', sort=False):
        g = group.sort_values('timestamp')
        last = g.iloc[-1]
        rows.append(dict(session_id=sid, date=last['date'], dose=float(last.cumulative_lux_minutes),
                         minutes_after_waking=float(last.minutes_after_waking),
                         measurement_quality=last.measurement_quality,
                         target_reached=bool(last.target_reached)))
    return pd.DataFrame(rows, columns=columns)


def daily_exposure(readings, eligible_only=False):
    sessions = summarize_sessions(readings)
    if eligible_only:
        sessions = sessions[sessions.measurement_quality.isin(['good', 'manual'])]
    if sessions.empty:
        return pd.DataFrame(columns=['date', 'dose', 'minutes_after_waking'])
    # Dose is additive across non-overlapping sessions. Timing is the first session.
    return sessions.groupby('date', as_index=False).agg(dose=('dose', 'sum'),
                                                       minutes_after_waking=('minutes_after_waking', 'min'))
