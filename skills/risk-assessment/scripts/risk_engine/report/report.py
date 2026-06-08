"""Render engine artifacts into ``dashboard.json`` + a non-directional ``report.md``.

The report is *descriptive*: state, percentile, cross-channel agreement, and
historical analogues — never a directive. Rendered output is run through the
non-directional lint before it is returned, so a directive phrase fails loudly
rather than shipping.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from risk_engine import LAYERS
from .lint import assert_non_directional

_TEMPLATE_DIR = Path(__file__).with_name("templates")

# State bands for the 0-100 risk-off composite. Purely descriptive labels.
_BANDS = [
    (20, "calm / risk-on-leaning"),
    (40, "low stress"),
    (60, "mixed / neutral"),
    (80, "elevated stress"),
    (101, "high stress / risk-off-leaning"),
]


def _band(score: float | None) -> str:
    if score is None:
        return "insufficient data"
    for hi, label in _BANDS:
        if score < hi:
            return label
    return _BANDS[-1][1]


def build_dashboard(engine_out: dict[str, Any]) -> dict[str, Any]:
    """Compact machine-readable summary for dashboards/scorecards."""
    comp = engine_out["composite"]
    return {
        "as_of": engine_out.get("as_of"),
        "overall": comp["overall"],
        "band": _band(comp["overall"]),
        "agreement_pct": comp["agreement_pct"],
        "weighting": comp["weighting"],
        "layers": {k: v["score"] for k, v in comp["layers"].items()},
        "n_divergences": len(comp["divergence_flags"]),
        "n_provisional": len(comp["provisional"]),
        "n_missing": len(comp["missing"]),
        "contrarian_flags": comp["contrarian_flags"],
        "stale": [r["id"] for r in engine_out["indicators"] if r.get("stale")],
    }


def _analogue_rows(engine_out: dict[str, Any],
                   calibration: dict[str, Any]) -> dict[str, Any] | None:
    """Map current indicator buckets to their calibrated forward-return stats."""
    if not calibration:
        return None
    by_id = {r["id"]: r for r in engine_out["indicators"]}
    rows = []
    for ind_id, cal in calibration.get("indicators", {}).items():
        rec = by_id.get(ind_id)
        if not rec or rec.get("value_pct") is None or "buckets" not in cal:
            continue
        pct = rec["value_pct"]
        match = None
        for b in cal["buckets"]:
            lo, hi = b["value_pct_range"]
            if lo <= pct <= hi:
                match = b
                break
        match = match or (cal["buckets"][-1] if cal["buckets"] else None)
        if match:
            rows.append({"id": ind_id,
                         "bucket_range": f"{match['value_pct_range'][0]}–{match['value_pct_range'][1]}",
                         "n": match["n"], "mean_fwd_return": match["mean_fwd_return"],
                         "neg_hit_rate": match["neg_hit_rate"]})
    if not rows:
        return None
    return {"horizon": calibration.get("horizon", "?"),
            "benchmark": calibration.get("benchmark", "benchmark"), "rows": rows}


def render_report(engine_out: dict[str, Any],
                  calibration: dict[str, Any] | None = None,
                  template_dir: str | Path | None = None) -> str:
    """Render the Markdown brief; raises ``NonDirectionalError`` if it isn't clean."""
    env = Environment(
        loader=FileSystemLoader(str(template_dir or _TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        trim_blocks=True, lstrip_blocks=True,
    )
    tmpl = env.get_template("report.md.j2")
    comp = engine_out["composite"]

    by_layer = {ly: [r for r in engine_out["indicators"] if r["layer"] == ly]
                for ly in LAYERS}
    provenance = [{"id": r["id"],
                   "sources": sorted({p["source"] for p in r.get("provenance", [])
                                      if p.get("source")})}
                  for r in engine_out["indicators"]]

    text = tmpl.render(
        as_of=engine_out.get("as_of"),
        composite=comp,
        band=_band(comp["overall"]),
        layers_order=LAYERS,
        by_layer=by_layer,
        analogues=_analogue_rows(engine_out, calibration or {}),
        provenance=provenance,
    )
    assert_non_directional(text)
    return text
