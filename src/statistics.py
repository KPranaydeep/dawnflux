"""Calendar windows, exposure bands and descriptive (non-causal) associations."""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from src.exposure import daily_exposure


def pair_days(readings, sleep):
    exposure = daily_exposure(readings, eligible_only=True)
    exposure['outcome_date'] = (pd.to_datetime(exposure.date) + pd.Timedelta(days=1)).dt.strftime('%Y-%m-%d')
    return exposure.merge(sleep, left_on='outcome_date', right_on='date', suffixes=('_exposure', '_sleep'))


def window_statistics(frame, as_of):
    rows = []
    dates = pd.to_datetime(frame.date)
    end = pd.Timestamp(as_of)
    for days in (7, 14, 28):
        subset = frame[(dates > end - pd.Timedelta(days=days)) & (dates <= end)]
        for metric in ('sleep_duration', 'sleep_score', 'sleep_regularity', 'dose'):
            if metric in subset:
                values = pd.to_numeric(subset[metric], errors='coerce').dropna()
                rows.append(dict(window_days=days, metric=metric, n=len(values),
                                 mean=values.mean(), median=values.median(),
                                 q25=values.quantile(.25), q75=values.quantile(.75)))
    return pd.DataFrame(rows)


def correlation(frame, x, y):
    values = frame[[x, y]].dropna()
    n = len(values)
    if n < 7 or values[x].nunique() < 2 or values[y].nunique() < 2:
        return {'n': n, 'rho': None, 'reason': 'Requires 7 pairs and variation in both measures.'}
    rho = float(spearmanr(values[x], values[y]).statistic)
    return {'n': n, 'rho': rho, 'reason': 'Spearman rank association; not causal evidence.'}


def exposure_bands(pairs, target):
    p = pairs.copy()
    p['band'] = pd.cut(p.dose, [-np.inf, .75 * target, 1.25 * target, np.inf],
                       labels=['Below 75%', '75–125%', 'Above 125%'], right=False)
    return p.groupby('band', observed=False).agg(n=('sleep_duration', 'count'),
        median_duration=('sleep_duration', 'median'), median_score=('sleep_score', 'median')).reset_index()


def rolling_sleep(frame):
    if frame.empty:
        return pd.DataFrame()
    data = frame.copy()
    data.index = pd.to_datetime(data.date)
    data = data.sort_index()[['sleep_duration', 'sleep_score', 'sleep_regularity']]
    return data.rolling('7D', min_periods=2).median()
