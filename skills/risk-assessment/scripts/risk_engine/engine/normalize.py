"""Normalize a raw indicator reading against its trailing history.

``value_pct`` is ALWAYS a 0-100 percentile rank of the current value within the
trailing window — this is the uniform quantity the composite orients and blends.
The record's ``transform`` selects an extra display statistic (percentile / z-score
/ level) surfaced in the report but not used for orientation.
"""

from __future__ import annotations

from typing import Any

from .calc import calc


def percentile_rank(value: float, history: list[float]) -> float | None:
    """Rank of ``value`` within ``history`` as a 0-100 percentile.

    Uses the mid-rank convention (ties count as half) so identical repeated
    values map to the middle of their tie band, not the top or bottom.
    """
    hist = [h for h in history if h is not None]
    if not hist:
        return None
    n = len(hist)
    below = sum(1 for h in hist if h < value)
    equal = sum(1 for h in hist if h == value)
    return round(calc("100 * (below + 0.5 * equal) / n",
                      {"below": below, "equal": equal, "n": n}), 4)


def normalize(value: float | None, history: list[float], method: str,
              window: int) -> dict[str, Any]:
    """Return the normalized view of one indicator reading.

    ``history`` should be the trailing series (oldest..newest, current excluded).
    It is trimmed to the last ``window`` observations.
    """
    if value is None:
        return {"value": None, "value_pct": None, "stat_method": method,
                "stat_value": None, "window": window, "n_obs": 0,
                "history_sufficient": False}

    hist = [h for h in (history or []) if h is not None][-window:]
    n_obs = len(hist)
    value_pct = percentile_rank(value, hist) if hist else None

    if method == "level" or not hist:
        stat_value = round(float(value), 6)
    elif method == "zscore":
        if n_obs >= 2:
            mean = calc("mean(h)", {"h": hist})
            sd = calc("std(h)", {"h": hist})
            stat_value = round(calc("(v - mean) / sd",
                                    {"v": value, "mean": mean, "sd": sd}), 4) \
                if sd else 0.0
        else:
            stat_value = 0.0
    else:  # percentile
        stat_value = value_pct

    # A short history makes the percentile unreliable; flag it so cross-check can
    # discount confidence rather than pretend precision.
    sufficient = n_obs >= max(30, window // 4)
    return {
        "value": round(float(value), 6),
        "value_pct": value_pct,
        "stat_method": method,
        "stat_value": stat_value,
        "window": window,
        "n_obs": n_obs,
        "history_sufficient": sufficient,
    }
