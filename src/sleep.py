"""Sleep duration and a clearly labelled day-to-day regularity proxy."""
import numpy as np
import pandas as pd


def clock_distance(a, b):
    """Shortest clock-time difference in minutes, correctly wrapping midnight."""
    def minute(x):
        x = pd.Timestamp(x)
        return x.hour * 60 + x.minute + x.second / 60
    delta = abs(minute(a) - minute(b))
    return min(delta, 1440 - delta)


def sleep_duration(onset, wake):
    hours = (pd.Timestamp(wake) - pd.Timestamp(onset)).total_seconds() / 3600
    if not 0 < hours <= 24:
        raise ValueError('Sleep duration must be greater than 0 and at most 24 hours.')
    return hours


def add_regularity(frame):
    """0–100 proxy: 100 - mean onset/wake clock shift in minutes, clipped.

    Only consecutive wake dates qualify. This is NOT the validated Sleep
    Regularity Index, which requires continuous sleep/wake state measurements.
    """
    result = frame.sort_values('date').copy()
    scores = [np.nan] * len(result)
    for i in range(1, len(result)):
        previous, current = result.iloc[i - 1], result.iloc[i]
        if (pd.Timestamp(current.date) - pd.Timestamp(previous.date)).days == 1:
            shift = (clock_distance(current.sleep_onset, previous.sleep_onset)
                     + clock_distance(current.wake_time, previous.wake_time)) / 2
            scores[i] = max(0.0, 100 - shift)
    result['sleep_regularity'] = scores
    return result
