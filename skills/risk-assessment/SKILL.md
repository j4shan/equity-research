---
name: risk-assessment
description: This skill should be used when the user asks to "assess market risk", "run the risk agent", "how fearful/complacent is the market", "give me the daily risk read", "risk dashboard for SPX/NDX/SMH", or wants a cross-verified macro/sector/market/fear indicator read on the US equity indices and semiconductors. It runs a deterministic Python engine (`risk_engine`, bundled in this skill's `scripts/`) over data gathered from the FMP, Alpha Vantage, and Massive MCPs plus FRED/FearGreedChart HTTP adapters, cross-verifying every headline signal across ≥2 independent channels, and writes a NON-DIRECTIONAL risk brief (state + percentile + agreement + historical analogues — never buy/sell/hedge/timing/price-target) into the sibling assets repo. Also use for scheduled daily risk runs.
version: 0.1.0
allowed-tools: [Read, Write, Bash, TodoWrite, Glob, Grep, mcp__research_hub__calc_evaluate, mcp__claude_ai_FMP__quote, mcp__claude_ai_FMP__economics, mcp__claude_ai_FMP__marketPerformance, mcp__claude_ai_FMP__technicalIndicators, mcp__claude_ai_FMP__commitmentOfTraders, mcp__claude_ai_FMP__indexes, mcp__claude_ai_Alpha_Vantage__RSI, mcp__claude_ai_Alpha_Vantage__ATR, mcp__claude_ai_Alpha_Vantage__SMA, mcp__claude_ai_Alpha_Vantage__GLOBAL_QUOTE, mcp__claude_ai_Alpha_Vantage__CPI, mcp__claude_ai_Alpha_Vantage__HISTORICAL_PUT_CALL_RATIO, mcp__claude_ai_Massive__search_endpoints, mcp__claude_ai_Massive__call_api, mcp__claude_ai_Massive__query_data, mcp__claude_ai_Massive__workspace]
---

# Market Risk Assessment (daily, non-directional)

You are the daily driver for the **risk-assessment agent**. You produce a
cross-verified read on the *state* of risk sentiment for **SPX, NDX, and SMH** —
macro, sector, market, and fear/complacency layers.

> **Output is research tooling, NOT investment advice.** You present indicator
> state, percentiles vs. history, cross-channel agreement, and historical
> analogues. You **never** issue a buy/sell/hedge/long/short/timing call or a
> price target. The engine's non-directional lint gate enforces this — if it
> fails, fix the language, never weaken the lint.

> **Numerical discipline.** Every number is computed by the tested engine
> (`risk_engine`, which reuses `research_hub.calculator`). You gather raw
> data and write narrative; you do not do arithmetic yourself.

## Architecture (why the split)
MCP tools (FMP / Alpha Vantage / Massive) are callable only from this session;
FRED / FearGreedChart are plain HTTP and callable by Python. So: **you** fetch the
MCP channels, the **Python engine** does everything deterministic
(normalize → cross-verify → composite → report). See
`references/requirements.md` (PRD) and `references/README.md`. The engine package
(`scripts/risk_engine/`) is exclusive to this skill — nothing outside
`skills/risk-assessment/` imports it.

## Prerequisites (check once)
- Deps installed (`pyyaml`, `jinja2` — in `requirements.txt`); engine import works:
  `PYTHONPATH=skills/risk-assessment/scripts .venv/bin/python -c "import risk_engine, yaml, jinja2"`.
- FMP, Alpha Vantage, Massive connected at claude.ai (no keys in repo). Verify with
  a cheap call (e.g. `mcp__claude_ai_FMP__quote` on `^VIX`).
- A free **FRED** API key in `FRED_API_KEY` for the macro cross-checks (optional —
  those channels degrade to `provisional` without it).

## Workflow

### 1. Bootstrap the run
- `RUN_DIR = ../equity_research_assets/risk-assessment/runs/<YYYY-MM-DD>/` — the
  sibling **assets repo**, not this code repo (mirrors how equity-research reports
  are isolated from code; see `equity_research_assets/README.md`).
- `bash -c 'PYTHONPATH=skills/risk-assessment/scripts .venv/bin/python -m risk_engine.run_risk bootstrap --run-dir "RUN_DIR" --date "<date>"'`
- `Read RUN_DIR/fetch_spec.json` — the exact `mcp_calls` (you run) and `http_calls`
  (Python runs), each tagged with its `indicator_id`, `refresh_class`, and `dest`.

### 2. Respect the tiered refresh cadence
Not everything is re-fetched daily. Use each call's `refresh_class`:
- **daily** — VIX, term structure, curve, credit, breadth, RSI/ATR, put/call.
- **weekly** — sector P/E, COT positioning, NFCI/STLFSI.
- **monthly** — CPI trend.
Reuse a recent cached channel value (and its `history`) when it is within its
refresh window; only the daily set must be fresh every run. Stale channels beyond
tolerance are flagged `stale` by the engine.

### 3. Fetch the channels
- **MCP** (`mcp_calls`): call the FMP/AV/Massive tools named in `tool_hint`. Collect
  `components` for formula indicators (e.g. `{y10, y2}`, `{smh, spy}`) and a
  **trailing history** series per indicator (the transform window, ~252 daily obs)
  so the engine can percentile-rank. **Alpha Vantage is capped at 25 req/day** —
  prefer FMP/FRED on overlapping channels; batch AV.
- **HTTP** (`http_calls`): run FRED / FearGreedChart via the Python adapters, e.g.
  `bash -c 'PYTHONPATH=skills/risk-assessment/scripts .venv/bin/python -m risk_engine.fetch_http --run-dir "RUN_DIR"'`
  (or inline `from risk_engine.adapters.http_sources import fred_series`).

### 4. Write the raw contract
Write `RUN_DIR/raw/raw.json` (shape in `raw/raw.template.json`): per indicator a
`channels` list (`{source, value}` or `{source, components}`) + a `history` list.
Leave a channel `value` null when a source was unavailable — the engine
cross-verifies what's present and marks single-channel indicators `provisional`.

### 5. Run the engine
`bash -c 'PYTHONPATH=skills/risk-assessment/scripts .venv/bin/python -m risk_engine.run_risk run --run-dir "RUN_DIR"'`
→ writes `indicators.json`, `composite.json`, `dashboard.json`, and a lint-checked
`report.md`. If `calibration.json` is present, the report includes historical
analogues.

### 6. Add narrative & report back
- `Read` the artifacts and append interpretation to `report.md`: elevated layers,
  **cross-channel divergences** (they cap confidence — always surface them),
  **contrarian extremes** (e.g. VIX complacency, crowded COT positioning), and what
  the **historical analogues** show *followed* comparable states. Every claim traces
  to an artifact value. Keep it non-directional.
- Optionally render HTML: `.venv/bin/python scripts/assemble_report.py --run-dir "RUN_DIR"`.
- Summarize the `dashboard.json` (overall reading, per-layer scores, agreement %,
  divergence/provisional/stale flags) and link `report.md`.

## Calibration (periodic, not daily)
Quarterly, refresh the historical analogues: pull multi-year vintages, then
`risk_engine.calibrate` labels correction/recovery episodes and computes
per-indicator conditional forward-return distributions into `calibration.json`.
This is what lets the report cite analogues instead of asserting a forecast. It is
a flat-JSON store (no knowledge graph).

## Standalone worker
For a one-shot run you can instead invoke the deployed agent directly:
`risk-assessment-analyst` (see `agents/risk-assessment-analyst/`, deploy via
`scripts/deploy_agents.sh`).

## Scheduling (recurring)
For a recurring daily read, register the run with the Claude Code scheduling
system (CronCreate / the scheduling skill). Confirm cadence with the user first.
