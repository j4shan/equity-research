# Equity Research — Project Requirements Specification

**Version:** 1.0 · **Date:** 2026-06-08 · **Status:** Implemented
**Repo (code):** `j4shan/equity-research` · **Assets repo:** `../equity_research_assets` (separate git)

This document consolidates every requirement raised during project inception and
design, assigns each a stable ID, and records verification status against the
implemented code.

---

## 1. Project Setup & Environment

| ID | Requirement | Source |
|----|-------------|--------|
| PROJ-1 | Initialize git version control | initial request |
| PROJ-2 | Add a `.gitignore` | initial request |
| PROJ-3 | Create a GitHub project (public, per clarification) | initial request |
| PROJ-4 | Push the first commit | initial request |
| ENV-1 | Create a `.venv` virtual environment | follow-up |
| ENV-2 | Use Python 3.12 | follow-up |
| ENV-3 | Use `uv` as the installer/venv manager | follow-up |

## 2. Vision

> Develop an **equity research skill** using a **multi-agent workflow** and a
> **financial-data MCP** to collate company information into **research reports**
> and **knowledge graphs**.

## 3. Core Functionality

| ID | Requirement |
|----|-------------|
| FUNC-1 | **Concurrent & collaborative** group of agents operating under distinct roles |
| FUNC-2 | Roles cover **fundamentals**, **technical**, and **sentiment** analysis |
| KG-1 | A **dedicated agent** analyzes company relationships within a sector |
| KG-2 | Identify **competition, collaboration, dependency, symbiotic** relationships |
| KG-3 | Model the sector as an **ecosystem of organisms** (ecological framing) |

## 4. Code Structure

| ID | Requirement |
|----|-------------|
| STRUCT-1 | A `SKILL.md` in a directory following the **Agent Skill open standard** (with examples, scripts, resources, etc.) |
| STRUCT-2 | An **output folder** persisting generated research reports and **serialized knowledge graphs** |
| STRUCT-3 | A **powerful visualization tool** (custom or library) for diagrams, graphs, plots |

## 5. Infrastructure & Platform

| ID | Requirement |
|----|-------------|
| INFRA-1 | **In-memory graph (networkx)** for low-latency relationship access |
| INFRA-2 | Agent-generated assets (reports, charts, visuals) **version-controlled in a separate sibling directory** of the project root |
| INFRA-3 | A **workflow scheduling system** to queue, track, and distribute research requests |
| INFRA-4 | A **manager agent delegates tasks to worker sub-agents** |
| INFRA-5 | **Observability**: a lightweight workflow-management tool tracking **task lifecycle**, callable by agents **via tool calling** |
| INFRA-6 | **Recurring/cron scheduling** in addition to the on-demand durable queue (design decision) |
| INFRA-7 | A run **begins by generating an execution plan** (`RUN_DIR/plan.md`) via the general-purpose **execution-planning** skill; the manager then executes it wave by wave |
| INFRA-8 | Task ordering into parallel waves is computed by the deterministic **`plan_toposort`** research_hub tool — never hand-ordered |

## 6. Agent Source Control

| ID | Requirement |
|----|-------------|
| AGENT-1 | Manager and worker agents authored as **Claude subagent templates** |
| AGENT-2 | Agent definitions **deployed to `~/.claude/agents/`** |
| AGENT-3 | Agent templates are **source-controlled** in the repo |

## 7. Data Source

| ID | Requirement |
|----|-------------|
| DATA-1 | Subagents must use the **Massive MCP** and **Alpha Vantage MCP** as the preferred financial data tools |
| DATA-2 | Both are **claude.ai-level connectors** — no repo-local registration, no API keys, no OAuth in this repo |
| DATA-3 | Fetch **historical OHLCV** via Alpha Vantage `TIME_SERIES_DAILY_ADJUSTED` (bulk/cross-sectional pulls via Massive) |
| DATA-4 | Fetch the **latest price quote** via Alpha Vantage `GLOBAL_QUOTE` |

## 8. Confirmed Design Decisions

| ID | Decision |
|----|----------|
| DEC-1 | Visualization stack: **networkx + pyvis + plotly** |
| DEC-2 | Report output: **Markdown (source of record) + interactive HTML** |
| DEC-3 | Input model: **single ticker, auto-discover peers** (batch/watchlist also supported) |
| DEC-4 | Graph serialization: **JSON + GraphML** (from the live in-memory graph) |
| DEC-5 | Assets repo: **`../equity_research_assets`**, its **own local git repo** |
| DEC-6 | Delegation: **main-thread manager + worker subagents** (subagents can't nest-spawn) |
| DEC-7 | Scheduling: **durable queue + recurring cron** |

---

## 8b. Later Additions (post-v1.0)

| ID | Requirement |
|----|-------------|
| MOAT-1 | `relationship-analyst` conducts a **comprehensive moat assessment** of the primary ticker (sources scored with evidence; rating wide/narrow/none; trend; biggest threat), grounded in graph position + fundamentals |
| EDGE-1 | Final graph data model: ticker → node, relationship → **directed edge**; edge identity = `(source, target, relation)`; relations **not mutually exclusive** |
| EDGE-2 | **Merge-update pattern**: re-asserting an edge refreshes scalars and **appends** the run's finalized summary to the edge's `summaries: list[text]` |
| EDGE-3 | Agents do **not** research/create nodes for out-of-universe companies (enforced by `graph_add_edge`; mentions recorded under `out_of_universe`) |
| MODEL-1 | Per-agent model + effort pinned in frontmatter: Opus at high/medium (manager high, relationship medium), Sonnet workers at high minimum |
| ADV-1 | An **adversarial-review agent** cross-checks the manager's conclusions at the end of the workflow (task role `review`; opus/high; graph read-only) |
| ADV-2 | Review includes mechanical recomputation of derived figures, claim–evidence tracing, live Alpha Vantage/Massive spot-checks, consistency & omission hunting |
| ADV-3 | **Publish-with-flag**: a `rejected` verdict never blocks publication — the report ships with a prominent rejection banner and a contested rating |

## 9. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | Concurrency must be **race-free** (shared graph/board mutations serialized) |
| NFR-2 | Workflow state must be **durable** and **resumable** across sessions |
| NFR-3 | Reports must be **self-contained / shareable** while keeping the version-controlled repo lean |
| NFR-4 | Outputs labelled **"not investment advice"** |
| NFR-5 | Unit + script tests covering the graph store, task board, and render pipeline |

---

## 10. Out of Scope / User-Activated

- Connecting the **Massive** and **Alpha Vantage** connectors in claude.ai (Settings
  → Connectors) is a one-time user action.
- Registering the actual recurring cron job is user-triggered via the
  Claude Code `/schedule` skill (the project provides the helper + capability).
- Committing/pushing the implementation beyond the initial scaffold awaits explicit
  user approval.
