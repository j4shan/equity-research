"""Engine driver: raw channel readings -> indicators.json + composite.json.

Deterministic and reproducible: identical ``raw`` input yields identical output.
The raw contract (produced by the fetch layer / the agent) is::

    {
      "as_of": "2026-07-12",
      "indicators": {
        "<indicator_id>": {
          "channels": [
            {"source": "fmp",  "value": 15.03, "ts": "2026-07-11", "call": "..."},
            {"source": "fgc",  "components": {"vix": 15.0, "vix3m": 16.9}, "ts": "..."}
          ],
          "history": [ ...trailing consensus-quantity values, oldest..newest... ]
        }
      }
    }

A channel is either a direct ``value`` (already the indicator's quantity) or a
``components`` dict reduced by the record's ``formula`` via ``calc_evaluate``.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..registry import Indicator, load_registry
from .calc import CalcError, calc
from .composite import build_composite
from .crosscheck import cross_check
from .normalize import normalize

_SHORT_HISTORY_PENALTY = 0.8
# How stale (days) a refresh class may be before we flag it.
_STALENESS_LIMIT = {"daily": 4, "weekly": 10, "monthly": 40}


def _channel_scalar(ind: Indicator, ch: dict[str, Any]) -> float | None:
    """Reduce one raw channel to the indicator's scalar quantity."""
    if ch.get("value") is not None:
        return float(ch["value"])
    comps = ch.get("components")
    if comps and ind.formula:
        try:
            return calc(ind.formula, {k: float(v) for k, v in comps.items()})
        except (CalcError, TypeError, ValueError):
            return None
    return None


def _staleness_days(as_of: str | None, channels: list[dict[str, Any]]) -> int | None:
    """Age in days of the freshest channel timestamp relative to ``as_of``."""
    if not as_of:
        return None
    try:
        ref = date.fromisoformat(as_of)
    except ValueError:
        return None
    ages = []
    for ch in channels:
        ts = ch.get("ts")
        if not ts:
            continue
        try:
            ages.append((ref - date.fromisoformat(str(ts)[:10])).days)
        except ValueError:
            continue
    return min(ages) if ages else None


def _score_indicator(ind: Indicator, raw: dict[str, Any],
                     as_of: str | None) -> dict[str, Any]:
    channels = raw.get("channels", []) if raw else []
    history = raw.get("history", []) if raw else []

    scalars = []
    for ch in channels:
        scalars.append({"source": ch.get("source"), "value": _channel_scalar(ind, ch)})

    cc = cross_check(scalars, tolerance=ind.tolerance)
    nz = normalize(cc["consensus"], history, ind.method, ind.window)

    confidence = cc["confidence"]
    if confidence and not nz["history_sufficient"]:
        confidence = round(calc("c * p", {"c": confidence, "p": _SHORT_HISTORY_PENALTY}), 4)

    stale_days = _staleness_days(as_of, channels)
    limit = _STALENESS_LIMIT.get(ind.refresh_class)
    is_stale = stale_days is not None and limit is not None and stale_days > limit

    return {
        "id": ind.id,
        "layer": ind.layer,
        "refresh_class": ind.refresh_class,
        "direction": ind.direction,
        "contrarian": ind.contrarian,
        "transform": ind.transform,
        "value": nz["value"],
        "value_pct": nz["value_pct"],
        "stat_method": nz["stat_method"],
        "stat_value": nz["stat_value"],
        "n_obs": nz["n_obs"],
        "history_sufficient": nz["history_sufficient"],
        "cross_check": cc["status"],
        "confidence": confidence,
        "consensus": cc["consensus"],
        "n_channels": cc["n_channels"],
        "channel_values": cc["channel_values"],
        "divergence": cc["divergence"],
        "provisional": cc["status"] == "provisional" or ind.single_channel,
        "staleness_days": stale_days,
        "stale": is_stale,
        "thresholds": ind.thresholds,
        "provenance": [
            {"source": ch.get("source"), "call": ch.get("call"), "ts": ch.get("ts")}
            for ch in channels
        ],
    }


def run_engine(raw_doc: dict[str, Any],
               registry: list[Indicator] | None = None) -> dict[str, Any]:
    """Score every registry indicator against ``raw_doc``; return both artifacts.

    Returns ``{"as_of", "indicators": [...], "composite": {...}}``. Indicators are
    emitted in registry order so the output is stable/reproducible.
    """
    registry = registry if registry is not None else load_registry()
    as_of = raw_doc.get("as_of")
    raw_indicators = raw_doc.get("indicators", {})

    scored = [_score_indicator(ind, raw_indicators.get(ind.id, {}), as_of)
              for ind in registry]
    composite = build_composite(scored)

    return {"as_of": as_of, "indicators": scored, "composite": composite}
