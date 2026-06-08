"""Condition forward returns on an indicator's historical state.

For a given indicator we bucket its historical ``value_pct`` into quantile bins
and measure the distribution of subsequent ``horizon``-day benchmark returns per
bin. The output answers the only question the report is allowed to make: *when
this indicator has been in this state before, what tended to follow* — a
distribution and hit-rate, never a directive.
"""

from __future__ import annotations

from typing import Any

from ..engine.calc import calc


def forward_returns(prices: list[dict[str, Any]], horizon: int) -> list[dict[str, Any]]:
    """Per-date forward return over ``horizon`` observations.

    ``prices`` oldest..newest; returns list aligned to each date that HAS a full
    forward window: ``[{"date", "fwd_return"}]`` with fwd_return in percent.
    """
    pts = [(p["date"], float(p["close"])) for p in prices if p.get("close") is not None]
    out = []
    for i in range(len(pts) - horizon):
        d, c0 = pts[i]
        c1 = pts[i + horizon][1]
        out.append({"date": d,
                    "fwd_return": round(calc("100 * (c1 - c0) / c0",
                                             {"c1": c1, "c0": c0}), 4)})
    return out


def _quantile_edges(values: list[float], n_buckets: int) -> list[float]:
    s = sorted(values)
    m = len(s)
    return [s[min(m - 1, (m * k) // n_buckets)] for k in range(1, n_buckets)]


def _bucket_of(value: float, edges: list[float]) -> int:
    for b, e in enumerate(edges):
        if value <= e:
            return b
    return len(edges)


def calibrate_indicator(observations: list[dict[str, Any]],
                        n_buckets: int = 5) -> dict[str, Any]:
    """Bucket an indicator's history and summarize forward returns per bucket.

    ``observations`` = ``[{"date", "value_pct", "fwd_return"}, ...]`` (already
    joined; see ``backfill.build_panel``). Returns per-bucket count, value_pct
    range, mean/median forward return, and hit-rate of NEGATIVE forward returns.
    """
    obs = [o for o in observations
           if o.get("value_pct") is not None and o.get("fwd_return") is not None]
    if len(obs) < n_buckets * 2:
        return {"error": "insufficient observations for calibration",
                "n_obs": len(obs)}

    edges = _quantile_edges([o["value_pct"] for o in obs], n_buckets)
    buckets: list[dict[str, Any]] = [{"idx": b, "rets": [], "pcts": []}
                                     for b in range(n_buckets)]
    for o in obs:
        b = _bucket_of(o["value_pct"], edges)
        buckets[b]["rets"].append(o["fwd_return"])
        buckets[b]["pcts"].append(o["value_pct"])

    summary = []
    for b in buckets:
        rets, pcts = b["rets"], b["pcts"]
        if not rets:
            continue
        neg = sum(1 for r in rets if r < 0)
        summary.append({
            "bucket": b["idx"],
            "value_pct_range": [round(min(pcts), 2), round(max(pcts), 2)],
            "n": len(rets),
            "mean_fwd_return": round(calc("mean(r)", {"r": rets}), 4),
            "median_fwd_return": round(calc("median(r)", {"r": rets}), 4),
            "neg_hit_rate": round(calc("100 * neg / n", {"neg": neg, "n": len(rets)}), 1),
        })
    return {"n_obs": len(obs), "n_buckets": n_buckets,
            "bucket_edges": [round(e, 2) for e in edges], "buckets": summary}
