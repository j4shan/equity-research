"""Cross-verify a single indicator across its independent data channels.

This is the product's core promise: no headline signal ships on one source. Given
the per-channel scalar readings of the SAME quantity (after any formula reduction),
we compute a consensus, decide whether the channels AGREE within tolerance, and
assign a confidence. A lone channel is emitted ``provisional``; disagreeing
channels raise a ``DIVERGENCE`` flag instead of being silently averaged away.
"""

from __future__ import annotations

from typing import Any

from .calc import calc

# Confidence anchors (deterministic, not learned in v1).
_CONF_AGREE = 0.90
_CONF_DIVERGENCE = 0.45
_CONF_PROVISIONAL = 0.50
_SHORT_HISTORY_PENALTY = 0.8


def cross_check(channels: list[dict[str, Any]], tolerance: float = 0.05,
                history_sufficient: bool = True) -> dict[str, Any]:
    """Fuse channel readings into a consensus + agreement verdict.

    ``channels`` is a list of ``{"source": str, "value": float|None, ...}``.
    Returns status in {agree, divergence, provisional, missing}, the consensus
    (median of present channels), a confidence in [0, 1], and — when channels
    disagree — a populated ``divergence`` block.
    """
    present = [c for c in channels if c.get("value") is not None]
    sources = [c["source"] for c in present]
    values = [float(c["value"]) for c in present]
    n = len(present)

    if n == 0:
        return {"status": "missing", "consensus": None, "confidence": 0.0,
                "n_channels": 0, "sources": [], "divergence": None,
                "channel_values": []}

    channel_values = [{"source": s, "value": round(v, 6)}
                      for s, v in zip(sources, values)]

    if n == 1:
        conf = _CONF_PROVISIONAL * (_SHORT_HISTORY_PENALTY if not history_sufficient else 1.0)
        return {"status": "provisional", "consensus": round(values[0], 6),
                "confidence": round(conf, 4), "n_channels": 1, "sources": sources,
                "divergence": None, "channel_values": channel_values}

    consensus = calc("median(v)", {"v": values})
    lo, hi = min(values), max(values)
    spread = calc("hi - lo", {"hi": hi, "lo": lo})
    denom = abs(consensus) if consensus else max(abs(hi), abs(lo), 1e-9)
    rel_spread = calc("spread / denom", {"spread": spread, "denom": denom})

    if rel_spread <= tolerance:
        status, conf, divergence = "agree", _CONF_AGREE, None
    else:
        status, conf = "divergence", _CONF_DIVERGENCE
        divergence = {
            "rel_spread": round(rel_spread, 4),
            "tolerance": tolerance,
            "abs_spread": round(spread, 6),
            "values": channel_values,
        }

    if not history_sufficient:
        conf = calc("c * p", {"c": conf, "p": _SHORT_HISTORY_PENALTY})

    return {"status": status, "consensus": round(consensus, 6),
            "confidence": round(conf, 4), "n_channels": n, "sources": sources,
            "divergence": divergence, "channel_values": channel_values}
