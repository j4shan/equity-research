# Data Schemas — analyst artifacts

Each worker writes one JSON file into the run folder's `data/`. Keep findings
distilled (no raw API dumps). All scores are in [-1, +1] (bearish→bullish).
Provenance strings use `alpha_vantage:<TOOL>` or `massive:<endpoint>`.

## data/fundamentals.json
```json
{
  "ticker": "NVDA",
  "score": 0.62,
  "valuation": {"pe": 60.1, "ps": 28.0, "ev_ebitda": 45.0, "peg": 1.1, "vs_peers": "premium"},
  "growth": {"revenue_yoy": 1.22, "eps_yoy": 1.68, "fwd_rev_growth": 0.55},
  "profitability": {"gross_margin": 0.75, "op_margin": 0.62, "roe": 0.91, "roic": 0.55},
  "health": {"current_ratio": 4.1, "debt_to_equity": 0.25, "fcf_margin": 0.45},
  "earnings_quality": {"surprise_streak": 6, "notes": "consistent beats"},
  "highlights": ["..."], "risks": ["..."]
}
```

## data/technical.json
```json
{
  "ticker": "NVDA",
  "score": 0.40,
  "trend": {"vs_sma50": "above", "vs_sma200": "above", "adx": 31, "cross": "golden"},
  "momentum": {"rsi14": 64, "macd_hist": 1.8, "stoch": 80},
  "volatility": {"bb_width": 0.12, "atr_pct": 0.03},
  "volume": {"obv_trend": "rising"},
  "levels": {"support": [tactical], "resistance": [tactical]},
  "signals": [{"name": "RSI", "value": 64, "read": "bullish-not-overbought"}],
  "highlights": ["..."], "risks": ["..."]
}
```

## data/sentiment.json  (Alpha Vantage signals)
```json
{
  "ticker": "NVDA",
  "score": 0.55,
  "news": {"avg_sentiment": 0.28, "trend": "rising", "n_articles": 120},
  "narrative": {"top_keywords": ["AI", "data-center", "record revenue"]},
  "insider": {"net_buys": 2, "net_sells": 5, "net_value_usd": -1.2e7},
  "institutional_holdings": {"trend": "rising", "pct_held": 0.66},
  "put_call_ratio": {"latest": 0.72, "trend": "falling"},
  "co_mentions": ["AMD", "TSM", "MSFT"],
  "highlights": ["..."], "risks": ["..."]
}
```
(Alpha Vantage exposes news sentiment (`NEWS_SENTIMENT`), insider transactions,
institutional holdings, and put/call ratios. The `institutional_holdings` and
`put_call_ratio` fields are optional — omit when unavailable.)

## data/relationships.json
```json
{
  "primary": "NVDA",
  "nodes": [
    {"ticker": "NVDA", "name": "NVIDIA", "sector": "Technology", "role": "primary", "market_cap": 3.0e12},
    {"ticker": "AMD",  "name": "AMD",    "sector": "Technology", "role": "peer"},
    {"ticker": "TSM",  "name": "TSMC",   "sector": "Technology", "role": "supplier"}
  ],
  "edges": [
    {"source": "NVDA", "target": "AMD", "relation": "competition", "direction": "NVDA->AMD",
     "weight": 0.9, "confidence": 0.8, "evidence": "same AI-accelerator market",
     "summaries": ["2026-06: MI300 undercuts H100 on price; NVDA holds software edge."]},
    {"source": "NVDA", "target": "AMD", "relation": "collaboration", "direction": "NVDA->AMD",
     "weight": 0.3, "confidence": 0.6, "evidence": "co-members of open interconnect consortium",
     "summaries": ["2026-06: both back UALink open standard vs proprietary lock-in."]},
    {"source": "NVDA", "target": "TSM", "relation": "dependency", "direction": "NVDA->TSM",
     "weight": 0.95, "confidence": 0.9, "evidence": "leading-edge fab outsourced to TSMC",
     "summaries": ["2026-06: sole foundry for Blackwell; no second source qualified."]}
  ],
  "moat": {
    "rating": "wide",
    "trend": "stable",
    "sources": [
      {"type": "switching_costs", "strength": 0.9, "evidence": "CUDA ecosystem; inbound dependency edges from hyperscalers"},
      {"type": "network_effects", "strength": 0.7, "evidence": "developer base compounds platform value"},
      {"type": "intangibles",     "strength": 0.6, "evidence": "architecture IP, pricing power at 75% gross margin"}
    ],
    "graph_evidence": "3 weighted inbound dependency edges; symbiosis with MSFT; contested by 2 competition edges",
    "biggest_threat": "custom silicon by hyperscale customers erodes switching costs",
    "verdict": "3-5 sentence justification…"
  },
  "out_of_universe": ["ASML — lithography supplier mentioned in news; not in seeded universe, not researched"]
}
```

- Edge identity = `(source, target, relation)`; relations are **not mutually
  exclusive** (competition + collaboration can co-exist across segments).
- `summaries` is **append-only across runs** (merge-update pattern) — each run adds
  one finalized, self-contained entry; prefix with a date for readability.
- `out_of_universe`: companies surfaced by the study but absent from the graph —
  recorded, **not researched, no node created**.
- `relation ∈ {competition, collaboration, dependency, symbiosis}` ·
  `role ∈ {primary, peer, supplier, customer, partner}` ·
  `moat.rating ∈ {wide, narrow, none}` · `moat.trend ∈ {widening, stable, eroding}` ·
  `moat.sources[].type ∈ {intangibles, switching_costs, network_effects, cost_advantage, efficient_scale}` ·
  weights/strengths/confidence in [0,1].
See `references/relationship-taxonomy.md` for definitions, inference rules, and
the moat framework.

## data/review.json  (adversarial reviewer)
```json
{
  "ticker": "NVDA",
  "verdict": "upheld_with_revisions",
  "score_recomputation": {"expected": 0.54, "found": 0.54, "match": true,
                          "band_expected": "Strong Buy", "band_found": "Strong Buy"},
  "challenges": [
    {"id": "C1", "severity": "major", "type": "omission",
     "target_claim": "supply-chain risk manageable",
     "evidence": "relationships.json shows 0.95-weight dependency on TSM with no mitigation discussed",
     "suggested_fix": "add single-foundry concentration to key risks"}
  ],
  "spot_checks": [
    {"claim": "gross margin 75%", "source": "alpha_vantage:COMPANY_OVERVIEW", "result": "confirmed"}
  ],
  "no_material_challenges": false
}
```

- `verdict ∈ {upheld, upheld_with_revisions, rejected}` ·
  `severity ∈ {blocker, major, minor}` ·
  `type ∈ {data_error, logic_gap, inconsistency, omission, overreach}`.
- A composite/band mismatch in `score_recomputation` is an automatic **blocker**.
- **Publish-with-flag:** `rejected` never blocks publication — the report carries a
  prominent rejection banner and an Adversarial Review section instead.
