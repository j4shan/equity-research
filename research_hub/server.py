"""Research Hub MCP server.

A single long-running stdio MCP process that holds the shared in-memory
knowledge graph and the durable task board. Because every Claude subagent in a
session connects to this same process, it is the shared-memory substrate that
isolated subagents otherwise lack.

Run directly:   python -m research_hub.server
Registered via the repo's .mcp.json so the session + subagents can call its
``graph_*`` and ``workflow_*`` tools.

Configuration (env vars):
    RESEARCH_HUB_ASSETS_DIR  assets repo root (default: ../equity_research_assets)
    RESEARCH_HUB_DB          task board sqlite path (default: <assets>/.research_hub/taskboard.db)
    RESEARCH_HUB_SNAPSHOT    graph snapshot path  (default: <assets>/graph_snapshots/latest.graphml)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from . import calculator, toposort
from .graph_store import GraphStore
from .schemas import ANALYST_ROLES, Edge, Node
from .task_board import TaskBoard


# --- configuration -----------------------------------------------------------

def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _assets_dir() -> Path:
    env = os.environ.get("RESEARCH_HUB_ASSETS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (_repo_root().parent / "equity_research_assets").resolve()


ASSETS = _assets_dir()
DB_PATH = os.environ.get(
    "RESEARCH_HUB_DB", str(ASSETS / ".research_hub" / "taskboard.db")
)
SNAPSHOT_PATH = os.environ.get(
    "RESEARCH_HUB_SNAPSHOT", str(ASSETS / "graph_snapshots" / "latest.graphml")
)

# --- tracing & logging control ----------------------------------------------
# The server's own request tracing / logging is OFF by default so a research run
# stays quiet. It is controllable at runtime (admin_* tools) so the skill can
# temporarily disable any active tracing for the duration of a run and restore it.
# Levels map onto Python logging for our logger and the noisy mcp/uvicorn ones.

_TRACE_LOGGERS = ("research_hub", "mcp", "uvicorn", "uvicorn.access", "asyncio")
_LOG_LEVELS = {
    "off": logging.CRITICAL + 10,  # effectively silent
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}
# Default OFF; honour RESEARCH_HUB_LOG if the operator opted in.
_log_level_name = os.environ.get("RESEARCH_HUB_LOG", "off").lower()
if _log_level_name not in _LOG_LEVELS:
    _log_level_name = "off"


def _apply_logging(level_name: str) -> None:
    """Set our + library logger levels; 'off' silences tracing entirely."""
    level = _LOG_LEVELS[level_name]
    for name in _TRACE_LOGGERS:
        logging.getLogger(name).setLevel(level)
    # Hard-disable everything below CRITICAL when fully off.
    logging.disable(logging.CRITICAL if level_name == "off" else logging.NOTSET)


_apply_logging(_log_level_name)

mcp = FastMCP("research_hub")
GRAPH = GraphStore()
BOARD = TaskBoard(DB_PATH)

# Best-effort: warm the graph from the last snapshot so scheduled/new sessions
# resume with prior relationship knowledge.
try:
    GRAPH.load_snapshot(SNAPSHOT_PATH)
except Exception:  # noqa: BLE001 - snapshot is optional on first run
    pass


# === Graph tools =============================================================

@mcp.tool()
def graph_upsert_node(
    ticker: str,
    name: str = "",
    sector: str = "",
    industry: str = "",
    role: str = "peer",
    market_cap: Optional[float] = None,
) -> dict[str, Any]:
    """Create or update a company node. Merges with any existing node (findings
    are preserved). ``role`` is one of primary|peer|supplier|customer|partner."""
    node = Node(ticker=ticker, name=name, sector=sector, industry=industry,
                role=role, market_cap=market_cap)
    return GRAPH.upsert_node(node)


@mcp.tool()
def graph_set_node_attrs(
    ticker: str, analyst_role: str, findings: dict[str, Any]
) -> dict[str, Any]:
    """Attach one analyst's findings to a node, keyed by analyst_role
    (fundamentals|technical|sentiment|relationship). Used by workers to write
    their results back onto the shared graph."""
    if analyst_role not in ANALYST_ROLES:
        return {"error": f"analyst_role must be one of {ANALYST_ROLES}"}
    return GRAPH.set_node_attrs(ticker, analyst_role, findings)


@mcp.tool()
def graph_add_edge(
    source: str,
    target: str,
    relation: str,
    weight: float = 0.5,
    confidence: float = 0.5,
    evidence: str = "",
    summary: str = "",
) -> dict[str, Any]:
    """Merge-update a typed, directed relationship edge.

    Edge identity = (source, target, relation); relation is one of
    competition|collaboration|dependency|symbiosis and relations are NOT mutually
    exclusive (the same pair may hold competition AND collaboration edges).
    Re-asserting an existing identity refreshes weight/confidence/evidence and
    APPENDS ``summary`` (this run's finalized relationship summary) to the edge's
    ``summaries`` list. Both endpoints must already exist in the graph — do not
    research or create nodes for companies outside the seeded universe; edges to
    unknown tickers are rejected."""
    try:
        edge = Edge(source=source, target=target, relation=relation,
                    weight=weight, confidence=confidence, evidence=evidence,
                    summaries=[summary] if summary else [])
    except ValueError as exc:
        return {"error": str(exc)}
    return GRAPH.add_edge(edge)


@mcp.tool()
def graph_neighbors(ticker: str, relation: Optional[str] = None) -> list[dict]:
    """List a node's relationships (in + out), optionally filtered by relation type."""
    return GRAPH.neighbors(ticker, relation)


@mcp.tool()
def graph_query_edges(relation: Optional[str] = None) -> list[dict]:
    """All edges in the graph, optionally filtered by relation type."""
    return GRAPH.query_edges(relation)


@mcp.tool()
def graph_get_subgraph(tickers: Optional[list[str]] = None) -> dict[str, Any]:
    """Node-link JSON for the whole graph (or the induced subgraph over ``tickers``).
    Workers call this to see the peer universe and compute relative metrics."""
    return GRAPH.get_subgraph(tickers)


@mcp.tool()
def graph_centrality(kind: str = "degree") -> dict[str, float]:
    """Rank nodes by systemic importance. kind: degree|eigenvector|betweenness."""
    return GRAPH.centrality(kind)


@mcp.tool()
def graph_shortest_path(source: str, target: str) -> list[str]:
    """Shortest relationship path between two companies (undirected view)."""
    return GRAPH.shortest_path(source, target)


@mcp.tool()
def graph_stats() -> dict[str, Any]:
    """Node/edge counts and a breakdown of edges by relation type."""
    return GRAPH.stats()


@mcp.tool()
def graph_snapshot(
    graphml_path: Optional[str] = None, json_path: Optional[str] = None
) -> dict[str, Any]:
    """Persist the live graph to GraphML (+ JSON) in the assets repo so it
    survives across sessions and feeds the visualization scripts."""
    gpath = graphml_path or SNAPSHOT_PATH
    jpath = json_path or str(Path(gpath).with_suffix(".json"))
    return GRAPH.snapshot(gpath, jpath)


@mcp.tool()
def graph_load_snapshot(graphml_path: Optional[str] = None) -> dict[str, Any]:
    """Replace the live graph with a saved GraphML snapshot (resume prior runs)."""
    return GRAPH.load_snapshot(graphml_path or SNAPSHOT_PATH)


# === Workflow tools ==========================================================

@mcp.tool()
def workflow_create_run(label: str = "", meta: str = "") -> dict[str, str]:
    """Open a new research run and return its run_id."""
    return {"run_id": BOARD.create_run(label, meta)}


@mcp.tool()
def workflow_enqueue_task(
    run_id: str, ticker: str, role: str, priority: int = 5
) -> dict[str, Any]:
    """Queue one analysis task (role x ticker) under a run."""
    return BOARD.enqueue_task(run_id, ticker, role, priority)


@mcp.tool()
def workflow_next_task(run_id: Optional[str] = None) -> dict[str, Any]:
    """Peek the highest-priority queued task without claiming it."""
    return BOARD.next_task(run_id)


@mcp.tool()
def workflow_claim_task(task_id: str, worker: str) -> dict[str, Any]:
    """Claim a queued task (queued -> claimed). ``worker`` identifies the agent."""
    return BOARD.claim_task(task_id, worker)


@mcp.tool()
def workflow_start_task(task_id: str) -> dict[str, Any]:
    """Mark a task running and stamp the start time (bumps attempt count)."""
    return BOARD.start_task(task_id)


@mcp.tool()
def workflow_complete_task(task_id: str, result_ref: str = "") -> dict[str, Any]:
    """Mark a task done; ``result_ref`` points to the produced artifact."""
    return BOARD.complete_task(task_id, result_ref)


@mcp.tool()
def workflow_fail_task(task_id: str, error: str, retry: bool = True) -> dict[str, Any]:
    """Mark a task failed; if ``retry`` and attempts remain, requeue it."""
    return BOARD.fail_task(task_id, error, retry)


@mcp.tool()
def workflow_get_task(task_id: str) -> dict[str, Any]:
    """Fetch one task's full record."""
    return BOARD.get_task(task_id)


@mcp.tool()
def workflow_list_tasks(
    run_id: Optional[str] = None, status: Optional[str] = None
) -> list[dict]:
    """List tasks, optionally filtered by run_id and/or status."""
    return BOARD.list_tasks(run_id, status)


@mcp.tool()
def workflow_get_run(run_id: str) -> dict[str, Any]:
    """Status board for a run: per-state counts, completion flag, avg duration.
    The manager polls this to know when fan-out is finished."""
    return BOARD.get_run(run_id)


@mcp.tool()
def workflow_render_run_log(run_id: str, fmt: str = "markdown") -> dict[str, str]:
    """Render the task lifecycle as a markdown or html table (observability).
    fmt: markdown|html."""
    return {"run_id": run_id, "fmt": fmt,
            "table": BOARD.render_run_log(run_id, fmt)}


# === Calculator ==============================================================

@mcp.tool()
def calc_evaluate(
    expression: str, variables: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Deterministically evaluate an arithmetic expression. ALL agents must
    delegate numerical calculation here (ratios, growth rates, margins, averages,
    z-scores) — never do arithmetic mentally.

    Supports + - * / // % **, parentheses, named variables (numbers or lists of
    numbers), list literals, and functions: abs, round, min, max, sum, len, sqrt,
    log, log10, exp, floor, ceil, mean, median, std.

    Examples:
      calc_evaluate("(rev1 - rev0) / rev0", {"rev1": 60922, "rev0": 26974})
      calc_evaluate("mean(pes)", {"pes": [60.1, 45.0, 22.0, 24.0]})

    Returns {"result": ...} or {"error": ...}."""
    return calculator.evaluate(expression, variables)


# === Planning ================================================================

@mcp.tool()
def plan_toposort(dependencies: dict[str, list[str]]) -> dict[str, Any]:
    """Topologically sort a task dependency graph into an execution order AND
    parallel waves. Use when building an execution plan: pass every task mapped
    to the list of task ids it depends on. Tasks in the same wave have no
    dependency on one another and may run in parallel; wave N+1 starts only after
    wave N completes. Never hand-compute task order — route it through here.

    Args:
      dependencies: {"task_id": ["prereq_id", ...]}. Tasks with no prerequisites
        use []. A prereq that is not itself a key becomes a root task.

    Examples:
      plan_toposort({"seed": [], "fundamentals": ["seed"], "technical": ["seed"],
                     "synthesis": ["fundamentals", "technical"]})
      -> {"order": ["seed","fundamentals","technical","synthesis"],
          "waves": [["seed"], ["fundamentals","technical"], ["synthesis"]],
          "roots": ["seed"], "node_count": 4, "wave_count": 3, ...}

    Returns {"order", "waves", "roots", "node_count", "wave_count",
    "dependencies"} or {"error": "cycle detected: a -> b -> a"} for cyclic or
    invalid input."""
    return toposort.sort(dependencies)


# === Admin: tracing & logging ================================================

@mcp.tool()
def admin_get_logging() -> dict[str, Any]:
    """Report the server's tracing/logging state. `tracing_enabled` is False when
    logging is 'off' (the default). Use before a run to capture the prior state."""
    return {"logging_level": _log_level_name,
            "tracing_enabled": _log_level_name != "off",
            "levels": list(_LOG_LEVELS)}


@mcp.tool()
def admin_set_logging(level: str) -> dict[str, Any]:
    """Set the server's tracing/logging level: off|error|warn|info|debug.
    `off` disables tracing entirely. Returns previous + current state so the skill
    can temporarily disable tracing for a run and restore it afterward."""
    global _log_level_name
    level = (level or "").lower()
    if level not in _LOG_LEVELS:
        return {"error": f"level must be one of {list(_LOG_LEVELS)}"}
    previous = _log_level_name
    _apply_logging(level)
    _log_level_name = level
    return {"previous": previous, "current": level,
            "tracing_enabled": level != "off"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
