"""Conservative, inspectable experimental suggestion, never a prescription."""
import numpy as np
import pandas as pd


def estimate_target(pairs, initial_target, sleep_target, as_of):
    """Anchor every estimate to the user's initial target: no rerun ratcheting.

    Use last 28 outcome dates; require 21 pairs, >=7 successful nights, exposure
    variation and >=5 nights in each half of dose distribution. Suggest the
    median successful dose only when success direction agrees in both 14-day
    halves. Maximum update is 10% of initial target. Timing-confounded contrasts
    (>30 min median timing difference) never update.
    """
    result = dict(target=float(initial_target), confidence='Insufficient data', n=0,
                  reason='Need 21 paired days in the last 28 calendar days.', candidate=None)
    if pairs.empty:
        return result
    end = pd.Timestamp(as_of)
    dates = pd.to_datetime(pairs.outcome_date)
    p = pairs[(dates > end - pd.Timedelta(days=28)) & (dates <= end)].copy()
    result['n'] = len(p)
    if len(p) < 21:
        return result
    result['confidence'] = 'Low — observational'
    success = p.sleep_duration.between(sleep_target - .5, sleep_target + 1)
    if success.sum() < 7 or p.dose.nunique() < 4:
        result['reason'] = 'Need 7 nights near the sleep target and at least 4 distinct doses.'
        return result
    candidate = float(p.loc[success, 'dose'].median())
    result['candidate'] = candidate
    lower, upper = p[p.dose <= p.dose.median()], p[p.dose > p.dose.median()]
    if min(len(lower), len(upper)) < 5 or abs(lower.minutes_after_waking.median() - upper.minutes_after_waking.median()) > 30:
        result['reason'] = 'Dose groups are unbalanced or differ in timing by more than 30 minutes.'
        return result
    direction = np.sign(candidate - initial_target)
    for recent in (False, True):
        half = p[(pd.to_datetime(p.outcome_date) > end - pd.Timedelta(days=14)) == recent]
        low, high = half[half.dose <= p.dose.median()], half[half.dose > p.dose.median()]
        if min(len(low), len(high)) < 3:
            result['reason'] = 'Each 14-day half needs at least 3 nights in each dose group.'
            return result
        advantage = (high.sleep_duration.between(sleep_target - .5, sleep_target + 1).mean()
                     - low.sleep_duration.between(sleep_target - .5, sleep_target + 1).mean())
        if direction == 0 or direction * advantage < .2:
            result['reason'] = 'The two 14-day halves do not show a consistent ≥20-point success-rate difference.'
            return result
    result['target'] = float(np.clip(candidate, initial_target * .9, initial_target * 1.1))
    result['reason'] = 'Consistent descriptive signal in both halves; suggestion capped at ±10% of initial target. Confounding remains.'
    return result
