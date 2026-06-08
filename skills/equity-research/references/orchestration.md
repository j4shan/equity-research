# Orchestration — Manager / Worker over a Task Board

## Components

- **Research Hub MCP** (`research_hub`): one long-running process shared by the
  main thread and all subagents. Holds the **in-memory networkx graph** and the
  **durable SQLite task board**. This shared process is what lets isolated
  subagents collaborate on one live graph and one queue.
- **Manager**: the skill orchestrator in the **main thread** (logic mirrored by the
  `equity-research-manager` subagent template). Subagents cannot reliably spawn
  further subagents, so the actual parallel fan-out happens in the main thread.
- **Workers**: `fundamentals-analyst`, `technical-analyst`, `sentiment-analyst`,
  `relationship-analyst` subagents.
- **Adversarial reviewer**: `adversarial-reviewer` subagent — red-teams the
  manager's draft conclusions after synthesis (task role `review`). Read-only on
  the graph; verifies against primary sources, not the manager's narrative.

## Task lifecycle (FSM)

```
queued ──claim──▶ claimed ──start──▶ running ──complete──▶ done
   ▲                                   │
   └──────────── fail (retry) ─────────┤──fail (no retry)──▶ failed
```

Tools: `workflow_create_run`, `workflow_enqueue_task`, `workflow_next_task`,
`workflow_claim_task`, `workflow_start_task`, `workflow_complete_task`,
`workflow_fail_task`, `workflow_get_task`, `workflow_list_tasks`,
`workflow_get_run`, `workflow_render_run_log`. Bounded retry (MAX_ATTEMPTS=3).

## Graph tools

`graph_upsert_node`, `graph_set_node_attrs`, `graph_add_edge`, `graph_neighbors`,
`graph_query_edges`, `graph_get_subgraph`, `graph_centrality`,
`graph_shortest_path`, `graph_stats`, `graph_snapshot`, `graph_load_snapshot`.

Writes are serialized by the single server process — no agent-side locking.

## Tracing & logging

The Research Hub server's tracing/logging is **off by default** — runs stay quiet
and there is nothing to disable. Activate it only when explicitly debugging:

- `admin_get_logging` → `{logging_level, tracing_enabled}`.
- `admin_set_logging(level)` → `off|error|warn|info|debug`; returns `{previous, current}`.
  Set `"debug"` to trace, `"off"` when done.

Operators can pre-set the startup level with the `RESEARCH_HUB_LOG` env var (default
`off`). **Claude Code session telemetry** (`CLAUDE_CODE_ENABLE_TELEMETRY`, `OTEL_*`,
`ANTHROPIC_LOG`) is separate, read at process start, and is never enabled by the skill.

## Manager loop

1. **Intake** — `workflow_create_run`; for each (ticker × analyst role) call
   `workflow_enqueue_task`.
2. **Plan** — invoke the `execution-planning` skill to write `RUN_DIR/plan.md`
   (objective tracker + `plan_toposort` waves + task assignment); execute the
   remaining steps wave by wave per that plan.
3. **Seed** — discover peers, `graph_upsert_node` for primary + peers (fix the
   node universe before fan-out).
4. **Dispatch** — spawn the 4 worker subagents **in parallel** (one message,
   multiple `Agent` calls), passing each its `run_id`, `ticker`, and `task_id`(s).
5. **Monitor** — poll `workflow_get_run(run_id)` until `complete`; retry/skip
   failed tasks.
6. **Reduce** — graph-aware synthesis (centrality, risk propagation), build the
   rating, write the **draft** report.
7. **Adversarial review** — enqueue a `review` task; spawn `adversarial-reviewer`
   on the draft. It recomputes the composite (0.45/0.25/0.30 → band), traces
   load-bearing claims to artifacts/edges, spot-checks Alpha Vantage/Massive live, and writes
   `data/review.json` (verdict: upheld | upheld_with_revisions | rejected).
   The manager resolves each challenge exactly once — accept (revise) or rebut
   (with evidence); one round by default, a second only if a blocker changed the
   rating. **Publish-with-flag:** `rejected` never blocks publication — the report
   ships with a prominent rejection banner and the rating marked contested.
8. **Publish** — render viz + HTML, `graph_snapshot`, write + commit assets
   (report includes the Adversarial Review section).

## Worker contract

```
claim_task(task_id, worker) → start_task(task_id)
  → read peers via graph_get_subgraph (for relative metrics)
  → gather data via the Alpha Vantage and Massive MCPs (call tools directly by name)
  → graph_set_node_attrs(ticker, role, findings)   # + graph_add_edge for relationship role
  → write data/<role>.json into the run folder
  → complete_task(task_id, result_ref) | fail_task(task_id, error)
```

## Concurrency & safety

- One MCP process ⇒ graph + board mutations are serialized; race-free by design.
- Each worker owns its own `data/<role>.json` (no shared-file writes).
- Board is durable (SQLite) ⇒ interrupted runs are resumable: re-dispatch tasks
  still in `queued`/`claimed`.

## Scheduling (recurring)

`scripts/schedule_research.py` plus Claude Code scheduling (CronCreate / `/schedule`)
register routines, e.g. a **daily watchlist refresh**:

```
cron fires → new session → skill runs as manager
  → graph_load_snapshot (resume prior relationship knowledge)
  → enqueue watchlist tasks → workers → report → commit assets
```

Cadence and watchlist are confirmed with the user when a schedule is created.
A run is idempotent per (ticker, date): re-runs overwrite that day's folder.
