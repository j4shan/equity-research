"""Composite the per-indicator results into layer sub-scores + an overall read.

**v1 weighting decision (locked): equal-weight.** Within a layer, indicators are
combined by an equal weight scaled only by each indicator's cross-verification
confidence (a divergent/provisional signal counts less, but no indicator is hand-
tuned up or down). Across layers, the overall is the equal-weight mean of the
present layer scores. Calibration-derived weights are deliberately deferred to
avoid overfitting a short history; revisit post-calibration.

All scores are 0-100 on a single *risk-off* axis: 100 = maximally risk-off/stress,
0 = maximally risk-on/calm. This is a STATE percentile, never a directive.
"""

from __future__ import annotations

from typing import Any

from risk_engine import LAYERS
from .calc import calc

# Contrarian extremes worth surfacing (percentile of the raw quantity).
_COMPLACENCY_PCT = 10.0   # e.g. VIX in its bottom decile -> complacency tell
_EUPHORIA_PCT = 90.0      # e.g. put/call in its top decile the other way


def _risk_score(value_pct: float, direction: str) -> float:
    """Orient a 0-100 percentile onto the risk-off axis."""
    if direction == "risk_off_when_high":
        return value_pct
    return calc("100 - p", {"p": value_pct})


def build_composite(indicators: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate scored indicator records into ``composite.json`` content."""
    layers: dict[str, Any] = {}
    for layer in LAYERS:
        recs = [r for r in indicators
                if r["layer"] == layer and r.get("value_pct") is not None
                and r.get("confidence")]
        if not recs:
            layers[layer] = {"score": None, "n": 0, "confidence": None,
                             "contributors": []}
            continue
        weighted, wsum, contributors = [], [], []
        for r in recs:
            rscore = _risk_score(r["value_pct"], r["direction"])
            w = r["confidence"]
            weighted.append(calc("s * w", {"s": rscore, "w": w}))
            wsum.append(w)
            contributors.append({"id": r["id"], "risk_score": round(rscore, 2),
                                 "weight": w, "status": r["cross_check"]})
        score = calc("sum(num) / sum(den)", {"num": weighted, "den": wsum})
        mean_conf = calc("mean(w)", {"w": wsum})
        layers[layer] = {"score": round(score, 2), "n": len(recs),
                         "confidence": round(mean_conf, 4),
                         "contributors": contributors}

    present = [ly["score"] for ly in layers.values() if ly["score"] is not None]
    overall = round(calc("mean(s)", {"s": present}), 2) if present else None

    scored = [r for r in indicators
              if r.get("cross_check") not in (None, "missing")]
    agree = [r for r in scored if r["cross_check"] == "agree"]
    agreement = round(calc("100 * a / n", {"a": len(agree), "n": len(scored)}), 1) \
        if scored else None

    divergences = [{"id": r["id"], "layer": r["layer"],
                    "divergence": r.get("divergence")}
                   for r in indicators if r.get("cross_check") == "divergence"]
    provisional = [r["id"] for r in indicators
                   if r.get("cross_check") == "provisional"]
    missing = [r["id"] for r in indicators if r.get("cross_check") == "missing"]

    flags = []
    for r in indicators:
        if not r.get("contrarian") or r.get("value_pct") is None:
            continue
        p = r["value_pct"]
        if p <= _COMPLACENCY_PCT:
            flags.append({"id": r["id"], "kind": "complacency",
                          "value_pct": p, "note": "raw quantity in its low extreme"})
        elif p >= _EUPHORIA_PCT:
            flags.append({"id": r["id"], "kind": "capitulation_or_fear",
                          "value_pct": p, "note": "raw quantity in its high extreme"})

    return {
        "weighting": "equal_weight_v1",
        "axis": "risk_off_0_100",
        "layers": layers,
        "overall": overall,
        "agreement_pct": agreement,
        "n_indicators": len(indicators),
        "n_scored": len(scored),
        "divergence_flags": divergences,
        "provisional": provisional,
        "missing": missing,
        "contrarian_flags": flags,
    }
