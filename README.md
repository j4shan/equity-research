# Equity Research

An AI-powered equity research **Agent Skill** that runs a **manager→worker
multi-agent workflow** to produce rated research reports and sector **knowledge
graphs**. A team of role-specialized analysts works concurrently on
**fundamentals, technical, and sentiment**; a dedicated **relationship analyst**
maps the sector as an ecosystem (competition / collaboration / dependency /
symbiosis). Market data comes from the **Massive** and **Alpha Vantage** MCP servers.

## How it works

```
                    ┌─────────────────── main thread (MANAGER) ───────────────────┐
  "research NVDA" → │  intake → plan → seed graph → dispatch workers (parallel)    │
                    │        → monitor → graph-aware synthesis → render → commit   │
                    └───────────────┬───────────────────────────────┬─────────────┘
            spawns in parallel      │                               │ reads/writes via tools
        ┌───────────────┬───────────┴───────────┬───────────────┐   │
   fundamentals     technical              sentiment      relationship   (WORKER subagents)
        └──────┬────────┴───────────┬───────────┴───────┬───────┘   │
               ▼                     ▼                   ▼           ▼
        ┌───────────────────────  Research Hub MCP  ───────────────────────┐
        │  in-memory networkx graph  +  durable SQLite task board          │
        │  (one shared process — the substrate isolated subagents lack)    │
        └──────────────────────────────────────────────────────────────────┘
```

**Why one MCP server?** Claude Code subagents are isolated processes and can't
share a live Python object. An MCP server registered in `.mcp.json` is a single
long-running process shared by the main thread *and* every subagent — so it
becomes the shared **in-memory knowledge graph** (low-latency relationship
queries) and the durable **task board** (queue, lifecycle, observability).

## Layout

```
research_hub/            # custom MCP server: shared graph + task board
  graph_store.py         #   in-memory networkx + GraphML/JSON snapshot
  task_board.py          #   SQLite queue + lifecycle FSM (resumable)
  calculator.py          #   deterministic arithmetic behind calc_evaluate
  toposort.py            #   deterministic task-DAG sort behind plan_toposort
  server.py              #   graph_*, workflow_*, calc_evaluate, plan_toposort tools
agents/                  # Claude subagent templates (deployed to ~/.claude/agents/)
  <agent-name>/<agent-name>.md   #   one directory per agent: equity-research-manager,
                                  #   {fundamentals,technical,sentiment,relationship}-analyst,
                                  #   adversarial-reviewer, risk-assessment-analyst
skills/execution-planning/  # general-purpose planning skill (objective tracker + task DAG)
skills/equity-research/  # the Agent Skill
  SKILL.md               #   manager workflow (entry point)
  references/            #   analysis framework, relationship taxonomy, data-tool cheatsheet, orchestration
  templates/             #   report skeleton + data schemas
  examples/              #   sample report
skills/risk-assessment/  # the Agent Skill (non-directional market risk read)
  SKILL.md               #   daily-driver workflow (entry point)
  references/            #   PRD (requirements.md), README.md, service-recommendation-sheet.md
  scripts/risk_engine/   #   deterministic engine — exclusive to this skill
scripts/                 # deploy_agents.sh, visualize_graph.py, plot_charts.py,
                         #   assemble_report.py, schedule_research.py
tests/                   # unit + script smoke tests
.mcp.json                # registers the research_hub MCP server

../equity_research_assets/          # SEPARATE git repo — version-controlled outputs
  equity-research/runs/<TICKER>_<DATE>/   # report.md/html, data/*.json,
                                            #   knowledge_graph.{json,graphml}, graph.html, charts/
  risk-assessment/runs/<DATE>/            # fetch_spec.json, raw/raw.json, indicators.json,
                                            #   composite.json, dashboard.json, report.md/html
  graph_snapshots/latest.graphml
```

## Setup

```bash
# 1. Dependencies (Python 3.12)
uv pip install -r requirements.txt --python .venv

# 2. Deploy the subagent templates to ~/.claude/agents/
bash scripts/deploy_agents.sh           # use --copy to copy instead of symlink

# 3. The research_hub MCP server is registered in .mcp.json (auto-detected).
#    Massive + Alpha Vantage are claude.ai connectors — connect them once in
#    claude.ai → Settings → Connectors. See project_metadata/mcp-setup.md.
```

## Usage

In Claude Code:

- **Single company:** "research NVDA" / "build an equity research report for AAPL"
- **Sector map:** "map the semiconductor sector around NVDA"
- **Batch / watchlist:** "research NVDA, AMD, and TSM"
- **Recurring:** ask to schedule a daily watchlist refresh (uses
  `scripts/schedule_research.py` + Claude Code scheduling)

The skill seeds the peer universe, dispatches the four analysts in parallel,
synthesizes a rating with graph-level risk reasoning, and writes the report +
interactive graph to the assets repo.

## Develop / test

```bash
.venv/bin/python -m pytest tests/ -q                       # unit + script tests
.venv/bin/python tests/fixtures/make_fixture_run.py /tmp/run/NVDA_2026-06-08
.venv/bin/python scripts/visualize_graph.py --run-dir /tmp/run/NVDA_2026-06-08
.venv/bin/python scripts/plot_charts.py     --run-dir /tmp/run/NVDA_2026-06-08
.venv/bin/python scripts/assemble_report.py --run-dir /tmp/run/NVDA_2026-06-08
```

> Research tooling, **not investment advice**.
