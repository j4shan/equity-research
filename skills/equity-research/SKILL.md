---
name: equity-research
description: This skill should be used when the user asks to "research <ticker>", "do equity research", "analyze a stock", "build a research report", "map a sector", "build a sector knowledge graph", or wants fundamentals + technical + sentiment analysis of a company plus a relationship/competition map of its peers. It runs a manager→worker multi-agent workflow over the Massive and Alpha Vantage MCP servers and a shared in-memory knowledge graph. It first invokes the execution-planning skill to generate an execution plan (RUN_DIR/plan.md), then executes it — writing a multi-dimensional research report (Markdown + interactive HTML — synthesis only, no buy/sell recommendation) and a serialized graph (JSON + GraphML) to the assets repo. Also use for batch/watchlist research and recurring scheduled research runs.
version: 0.1.0
allowed-tools: [Task, Skill, Read, Write, Bash, TodoWrite, Glob, Grep, mcp__research_hub__calc_evaluate, mcp__research_hub__plan_toposort, mcp__claude_ai_Alpha_Vantage__SYMBOL_SEARCH, mcp__claude_ai_Alpha_Vantage__COMPANY_OVERVIEW, mcp__claude_ai_Alpha_Vantage__ETF_PROFILE, mcp__claude_ai_Alpha_Vantage__NEWS_SENTIMENT, mcp__claude_ai_Alpha_Vantage__GLOBAL_QUOTE, mcp__claude_ai_Massive__search_endpoints, mcp__claude_ai_Massive__call_api, mcp__claude_ai_Massive__query_data, mcp__claude_ai_Massive__workspace, mcp__research_hub__workflow_create_run, mcp__research_hub__workflow_enqueue_task, mcp__research_hub__workflow_list_tasks, mcp__research_hub__workflow_get_run, mcp__research_hub__workflow_render_run_log, mcp__research_hub__graph_upsert_node, mcp__research_hub__graph_get_subgraph, mcp__research_hub__graph_query_edges, mcp__research_hub__graph_neighbors, mcp__research_hub__graph_centrality, mcp__research_hub__graph_stats, mcp__research_hub__graph_snapshot, mcp__research_hub__graph_load_snapshot, mcp__research_hub__admin_get_logging, mcp__research_hub__admin_set_logging]
---

# Equity Research (multi-agent)

You are the **manager** in the main thread. You coordinate four worker subagents
through the **Research Hub** MCP (shared in-memory knowledge graph + durable task
board) to produce a rated equity research report and a sector knowledge graph.

> Output is research tooling, **not investment advice** — always state this.

## Prerequisites (check once)
- Deps installed: `uv pip install -r requirements.txt --python .venv` (idempotent).
- Subagents deployed: `bash scripts/deploy_agents.sh` (symlinks the 6 agents —
  manager, 4 analysts, adversarial reviewer — to `~/.claude/agents/`).
- The `research_hub` MCP server is registered (`.mcp.json`), and the **Massive**
  and **Alpha Vantage** MCP servers are connected at the claude.ai level (no API
  keys or OAuth in this repo). Verify with a cheap call — e.g.
  `mcp__claude_ai_Alpha_Vantage__MARKET_STATUS` and
  `mcp__claude_ai_Massive__search_endpoints("daily aggregates")`. If either
  server's tools are missing, reconnect the connector in claude.ai settings — see
  `project_metadata/mcp-setup.md`.

## Reference material (read as needed)
- `references/orchestration.md` — the manager/worker pattern and tool surfaces.
- `references/analysis-framework.md` — metrics, thresholds, scoring, rating bands.
- `references/relationship-taxonomy.md` — the 4 ecological relation types + rules.
- `references/data-tool-cheatsheet.md` — signal→tool map for Massive + Alpha Vantage.
- `templates/report-template.md`, `templates/data-schemas.md`.

> **Tracing/logging:** off by default. Only if explicitly debugging, call
> `admin_set_logging("debug")` to activate, then `admin_set_logging("off")` when done.

> **Numerical discipline:** delegate ALL numerical calculation (ratios, growth,
> averages, deltas) to `calc_evaluate` — never do arithmetic mentally. This applies
> to the manager and every worker.

> **No recommendation:** this workflow synthesizes evidence across dimensions.
> It never produces a composite score, rating band, or buy/sell recommendation.

## Workflow

### 1. Intake & run folder
- Resolve the request to a primary `TICKER` (or a list for a watchlist/batch).
- `RUN_DIR = ../equity_research_assets/equity-research/runs/<TICKER>_<YYYY-MM-DD>/`;
  create it with `data/` and `charts/` subfolders.
- `graph_load_snapshot()` to resume prior relationship knowledge (best-effort).
- `workflow_create_run(label="<TICKER> <date>")` → `run_id`.
- Enqueue four tasks per ticker:
  `workflow_enqueue_task(run_id, TICKER, role)` for
  `fundamentals`, `technical`, `sentiment`, `relationship`. Record the `task_id`s.

### 2. Generate the execution plan
Invoke the **execution-planning** skill to produce the plan that governs this run:
```
Skill(skill="execution-planning", args="objective=<the research request> output=RUN_DIR/plan.md subagents=fundamentals-analyst,technical-analyst,sentiment-analyst,relationship-analyst,adversarial-reviewer")
```
The plan writes `RUN_DIR/plan.md` with an Objective Tracker, a `plan_toposort`-computed
**Waves** table, and a **Task Assignment** table. Those two tables now govern the rest
of this workflow: **the remaining steps describe *how* to do each task; the plan's
waves decide *when*.** Execute wave by wave and update the plan's Objective Tracker as
each task reaches `done`/`failed`. (For a single ticker the plan mirrors the default
shape below; a watchlist produces a larger DAG.)

### 3. Seed the graph (fix the peer universe before fan-out)
- `SYMBOL_SEARCH(TICKER)` → resolve to the plain symbol; `COMPANY_OVERVIEW` → name,
  sector, industry, market cap.
- Discover peers: use **Massive** (`search_endpoints` → `call_api` with `store_as`,
  then `query_data` for a sector/market-cap SQL screen) and/or `ETF_PROFILE` holdings
  of a sector ETF + `NEWS_SENTIMENT` co-mentions; keep top 6–8.
- `graph_upsert_node` for the primary (role=primary) and each peer. This **fixes
  the node universe**: workers assert edges only among these nodes and never
  create nodes for companies outside it (`graph_add_edge` enforces this).

### 4. Dispatch workers **in parallel**
Launch all four workers in a **single message with multiple `Task` calls** (true
concurrency). Give each its `run_id`, `ticker`, `task_id`, and the absolute `RUN_DIR`.

```
Task(subagent_type="fundamentals-analyst", prompt="run_id=… ticker=… task_id=… run_dir=…")
Task(subagent_type="technical-analyst",    prompt="run_id=… ticker=… task_id=… run_dir=…")
Task(subagent_type="sentiment-analyst",    prompt="run_id=… ticker=… task_id=… run_dir=…")
Task(subagent_type="relationship-analyst", prompt="run_id=… ticker=… task_id=… run_dir=…")
```

Each worker reads peers from the graph, gathers data via Alpha Vantage / Massive,
writes its findings back to the graph + a `data/<role>.json`, and closes its task.

### 5. Monitor
- `workflow_get_run(run_id)` until `complete`. If a task is `failed` after retries,
  note the gap and proceed (don't block the whole report on one analyst).
- Mark each finished task `done` in `plan.md`'s Objective Tracker.

### 6. Graph-aware synthesis
- Read enriched nodes via `graph_get_subgraph()`.
- `graph_centrality("eigenvector")` → most systemic peers.
- Walk `dependency` edges (`graph_neighbors`) to propagate risk from weak
  suppliers/customers to the primary.
- Identify competitive blocs vs alliances (`competition` vs `symbiosis`/`collaboration`).
- Read the **moat assessment** from the primary node's `findings.relationship.moat`
  (rating/trend/sources/biggest threat) — it qualifies the durability of the
  fundamentals findings and belongs in the synthesis.
- **Synthesize — do not recommend.** Present the three dimension scores side by
  side (never blended into a composite), state where they converge and conflict,
  fold in graph-level risk, and map catalysts/risks (see `analysis-framework.md`).
  No rating band, no buy/sell language. Any derived number goes through
  `calc_evaluate`.
- Write the result as a **draft** `report.md` — it is not final until it survives
  adversarial review.

### 6b. Adversarial review (cross-check the conclusions)
- `workflow_enqueue_task(run_id, TICKER, "review")` → `task_id`.
- Spawn the reviewer:
  `Task(subagent_type="adversarial-reviewer", prompt="run_id=… ticker=… task_id=… run_dir=… draft=RUN_DIR/report.md")`.
  It re-verifies every derived figure via `calc_evaluate`, traces load-bearing
  claims, spot-checks data against Alpha Vantage/Massive live, and writes
  `data/review.json` with a verdict + challenges.
- **Resolve each challenge exactly once** (no ping-pong): *accept* (revise the
  draft) or *rebut* (with cited evidence). One review round by default; a second
  round only if resolving a **blocker** changed the rating.
- **Publish-with-flag policy:** a `rejected` verdict never blocks publication.
  Instead, flag it prominently — prepend a banner directly under the report title:
  `> ⚠️ **ADVERSARIAL REVIEW: REJECTED** — <one-line reason>. See §Adversarial Review.`
  and mark the contested conclusions as such in the synthesis.
- Add an **Adversarial Review** section to the report: verdict, material
  challenges, and how each was resolved (accepted revision or rebuttal).

### 7. Render & persist
- Serialize the graph into the run folder **and** update the cumulative snapshot:
  - `graph_snapshot(graphml_path="RUN_DIR/knowledge_graph.graphml", json_path="RUN_DIR/knowledge_graph.json")`
  - `graph_snapshot()` (default path → `graph_snapshots/latest.graphml`).
- Write `report.md` from `templates/report-template.md` filled with the synthesis;
  append `workflow_render_run_log(run_id)` as the Run Log section.
- Then render visuals + HTML from the repo root with `.venv`:
```
.venv/bin/python scripts/visualize_graph.py  --run-dir "RUN_DIR"   # graph.html (pyvis)
.venv/bin/python scripts/plot_charts.py       --run-dir "RUN_DIR"  # charts/*.html (plotly)
.venv/bin/python scripts/assemble_report.py   --run-dir "RUN_DIR"  # report.html from report.md
```
- Commit the run folder + updated snapshot to the assets repo:
  `git -C ../equity_research_assets add -A && git -C ../equity_research_assets commit -m "research: <TICKER> <date>"`.

### 8. Report back
Summarize the rating, the key drivers, the most important relationships/risks, and
link the generated `report.html` and `graph.html`.

## Batch / watchlist
Enqueue tasks for every ticker up front, then dispatch workers per ticker (respect
a sane concurrency cap, e.g. 2–3 tickers in flight). The graph accumulates across
tickers, producing a richer sector ecosystem.

## Scheduling (recurring)
For recurring research (e.g. daily watchlist), use `scripts/schedule_research.py`
and the Claude Code scheduling system — see `references/orchestration.md`. Confirm
cadence + watchlist with the user before creating a schedule.
