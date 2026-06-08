"""Data models and controlled vocabularies for the Research Hub.

These dataclasses define the shape of the knowledge-graph nodes/edges and the
workflow tasks. They are intentionally lightweight (stdlib only) so they can be
imported by the MCP server, the unit tests, and the visualization scripts alike.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# --- Controlled vocabularies -------------------------------------------------

#: Ecological relationship types for sector knowledge graphs.
RELATION_TYPES = ("competition", "collaboration", "dependency", "symbiosis")

#: Role a company plays relative to the primary research subject.
NODE_ROLES = ("primary", "peer", "supplier", "customer", "partner")

#: Analyst roles dispatched by the manager (these write findings to the graph).
ANALYST_ROLES = ("fundamentals", "technical", "sentiment", "relationship")

#: All workflow task roles: analysts + the adversarial reviewer (graph read-only,
#: cross-checks the manager's draft conclusions before publication).
WORKFLOW_ROLES = (*ANALYST_ROLES, "review")

#: Task lifecycle states. queued -> claimed -> running -> done | failed.
TASK_STATES = ("queued", "claimed", "running", "done", "failed")

#: Terminal states a task can no longer leave (except failed -> queued retry).
TERMINAL_STATES = ("done", "failed")


def now_ts() -> float:
    """Wall-clock seconds; single source of truth for timestamps."""
    return time.time()


def new_id(prefix: str) -> str:
    """Short, collision-resistant id with a human-readable prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# --- Knowledge graph ---------------------------------------------------------


@dataclass
class Node:
    """A company (or other entity) in the sector ecosystem graph."""

    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    role: str = "peer"  # one of NODE_ROLES
    market_cap: Optional[float] = None
    # Per-analyst findings attach here, keyed by analyst role, e.g.
    # {"fundamentals": {...}, "technical": {...}, "sentiment": {...}}.
    findings: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.ticker = self.ticker.upper().strip()
        if self.role not in NODE_ROLES:
            raise ValueError(
                f"role {self.role!r} not in {NODE_ROLES}"
            )

    def as_attrs(self) -> dict[str, Any]:
        """networkx node-attribute dict (graph keys on ticker separately)."""
        d = asdict(self)
        d.pop("ticker", None)
        return d


@dataclass
class Edge:
    """A typed, directed, weighted, evidenced relationship between two nodes.

    Edge identity is the triple (source, target, relation). Relations are NOT
    mutually exclusive: A and B can hold both a competition and a collaboration
    edge (different business segments). Re-asserting an existing identity is a
    merge-update: scalar attrs refresh to the latest values and each finalized
    relationship summary is appended to ``summaries`` (incremental agent output).
    """

    source: str
    target: str
    relation: str  # one of RELATION_TYPES
    weight: float = 0.5  # strength, 0..1
    confidence: float = 0.5  # analyst certainty, 0..1
    evidence: str = ""  # short justification / data citation
    summaries: list[str] = field(default_factory=list)  # appended per agent run

    def __post_init__(self) -> None:
        self.source = self.source.upper().strip()
        self.target = self.target.upper().strip()
        if self.relation not in RELATION_TYPES:
            raise ValueError(
                f"relation {self.relation!r} not in {RELATION_TYPES}"
            )
        self.weight = _clamp01(self.weight)
        self.confidence = _clamp01(self.confidence)

    def as_attrs(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("source", None)
        d.pop("target", None)
        return d


# --- Workflow ----------------------------------------------------------------


@dataclass
class Task:
    """A single unit of research work distributed to a worker subagent."""

    run_id: str
    ticker: str
    role: str  # one of ANALYST_ROLES (or "synthesis")
    task_id: str = field(default_factory=lambda: new_id("task"))
    status: str = "queued"
    priority: int = 5  # lower = higher priority
    attempts: int = 0
    worker: str = ""  # identifier the claiming agent supplied
    result_ref: str = ""  # path/URI to the produced artifact
    error: str = ""
    created_at: float = field(default_factory=now_ts)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    def duration(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return round(self.finished_at - self.started_at, 3)
        return None


def _clamp01(x: float) -> float:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, x))
