# Market Risk Assessment Agent

A daily, **non-directional** risk/sentiment read on **SPX, NDX, and SMH**. It
presents cross-verified quantitative indicators (macro · sector · market · fear)
with percentiles, cross-channel agreement, and historical analogues — never a
buy/sell/hedge/timing call or price target. Docs:
[requirements.md](requirements.md) (the PRD) ·
[service-recommendation-sheet.md](service-recommendation-sheet.md) (data-stack pricing).

## Design principles
- **Numbers are computed in tested Python**, never by the LLM (reuses
  `research_hub.calculator`). The agent gathers data and writes narrative.
- **Every headline signal is cross-verified** across ≥2 independent channels; a
  lone source is flagged `provisional`; disagreeing sources raise a `divergence`.
- **Deterministic & reproducible**: identical `raw.json` ⇒ identical artifacts.
- **Non-directional by lint gate**: the report build fails on directive language.
- v1 decisions: **equal-weight composite**, **flat-JSON episode store** (no graph).

## Layout
```
skills/risk-assessment/
├── SKILL.md                    # the daily driver, read by the manager/skill runner
├── references/                 # this file, requirements.md (PRD), service-recommendation-sheet.md
└── scripts/risk_engine/        # exclusive to this skill — nothing outside imports it
    ├── registry/indicators.yaml   # the contract: 19-indicator seed set (single source of truth)
    ├── registry/load.py           # typed load + validation
    ├── adapters/
    │   ├── mcp_fetch_spec.py       # registry -> the FMP/AV/Massive calls the agent must run
    │   └── http_sources.py         # FRED / FearGreedChart / AAII (pure Python, injectable fetch)
    ├── engine/
    │   ├── normalize.py            # percentile rank + z-score/level display stat
    │   ├── crosscheck.py           # channel fusion -> agree | divergence | provisional
    │   ├── composite.py            # equal-weight layer scores on a 0-100 risk-off axis
    │   └── engine.py               # raw.json -> indicators.json + composite.json
    ├── calibrate/                  # episodes.py, calibrate.py, backfill.py (flat-JSON analogues)
    ├── report/                     # report.py + templates/report.md.j2 + lint.py (non-directional)
    ├── run_risk.py                 # CLI: bootstrap | run
    └── fetch_http.py               # CLI: merge FRED HTTP channels into raw.json
```
Generated run output is **not** stored in this repo — it's isolated in the sibling
**assets repo** at `equity_research_assets/risk-assessment/runs/<date>/` (see
`equity_research_assets/README.md`), the same isolation the equity-research skill
uses for its reports.

The agent persona is `agents/risk-assessment-analyst/risk-assessment-analyst.md`;
the daily driver is `skills/risk-assessment/SKILL.md`.

## Run it
`risk_engine` lives under this skill's `scripts/` dir (not on the default Python
path), so every invocation needs `PYTHONPATH=skills/risk-assessment/scripts`. Run
these from the **code repo root**; `RUN_DIR` points into the **assets repo**.
```bash
RUN_DIR=../equity_research_assets/risk-assessment/runs/2026-07-12

# 1. scaffold a run dir + the fetch spec
PYTHONPATH=skills/risk-assessment/scripts .venv/bin/python -m risk_engine.run_risk bootstrap --run-dir "$RUN_DIR" --date 2026-07-12

# 2. the agent fetches MCP channels and writes $RUN_DIR/raw/raw.json;
#    FRED HTTP channels can be auto-merged:
PYTHONPATH=skills/risk-assessment/scripts .venv/bin/python -m risk_engine.fetch_http --run-dir "$RUN_DIR"

# 3. score -> indicators.json, composite.json, dashboard.json, report.md (linted)
PYTHONPATH=skills/risk-assessment/scripts .venv/bin/python -m risk_engine.run_risk run --run-dir "$RUN_DIR"
```

## Raw contract (`runs/<date>/raw/raw.json`)
```json
{
  "as_of": "2026-07-12",
  "indicators": {
    "vix_level": {
      "channels": [
        {"source": "fmp",  "value": 15.03, "ts": "2026-07-11"},
        {"source": "fred", "value": 15.10, "ts": "2026-07-11"},
        {"source": "fgc",  "value": 15.00}
      ],
      "history": [ /* trailing consensus-quantity values, oldest..newest */ ]
    },
    "yield_curve_2s10s": {
      "channels": [
        {"source": "fmp",  "components": {"y10": 4.56, "y2": 4.21}},
        {"source": "fred", "value": 0.35}
      ],
      "history": [ /* ... */ ]
    }
  }
}
```
A channel is either a direct `value` or a `components` dict reduced by the
indicator's `formula`. Missing sources → null value (engine flags provisional).

## Tests
```bash
.venv/bin/python -m pytest tests/test_risk_*.py -q
```
Covers registry validation, normalize, cross-verification, composite orientation,
a golden-fixture engine run + reproducibility, episode labeling, calibration,
adapters, the FRED merge, and the non-directional lint gate.
