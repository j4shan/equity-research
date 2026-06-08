"""Deterministic topological sort for execution planning.

Planning skills must not hand-compute task order — LLM ordering of a dependency
graph is an error source, and a wrong order silently corrupts a whole run. This
module routes every plan DAG through one deterministic sorter so the produced
order (and the parallel-wave grouping) is reproducible and reviewable.

Built on the stdlib ``graphlib.TopologicalSorter``. Given a mapping of each task
to the tasks it depends on, it returns both a flat linear order and the DAG's
*generations* (waves) — batches of tasks with no dependency on one another that
may run in parallel. Like the calculator, it never raises to the caller: every
error path returns ``{"error": ...}``.
"""

from __future__ import annotations

from graphlib import CycleError, TopologicalSorter
from typing import Any

_MAX_NODES = 500


def sort(dependencies: dict[str, list[str]]) -> dict[str, Any]:
    """Topologically sort a task DAG into a linear order and parallel waves.

    ``dependencies`` maps ``task_id -> [prerequisite_task_ids]``. A prerequisite
    that is referenced but not itself a key is treated as a root task (graphlib
    semantics). Returns ``{"order", "waves", "roots", "node_count",
    "wave_count", "dependencies"}`` on success, or ``{"error": ...}`` — never
    raises.
    """
    if not isinstance(dependencies, dict) or not dependencies:
        return {"error": "dependencies must be a non-empty dict of "
                         "{task_id: [prerequisite_ids]}"}

    normalized: dict[str, list[str]] = {}
    seen: set[str] = set()
    for key, prereqs in dependencies.items():
        if not isinstance(key, str) or not key.strip():
            return {"error": f"task ids must be non-empty strings: {key!r}"}
        if not isinstance(prereqs, list):
            return {"error": f"prerequisites for {key!r} must be a list"}
        task = key.strip()
        clean_prereqs: list[str] = []
        for p in prereqs:
            if not isinstance(p, str) or not p.strip():
                return {"error": f"prerequisites for {task!r} must be "
                                 f"non-empty strings: {p!r}"}
            prereq = p.strip()
            if prereq == task:
                return {"error": f"task {task!r} depends on itself"}
            clean_prereqs.append(prereq)
        normalized[task] = clean_prereqs
        seen.add(task)
        seen.update(clean_prereqs)

    if len(seen) > _MAX_NODES:
        return {"error": f"too many tasks: {len(seen)} exceeds {_MAX_NODES}"}

    ts: TopologicalSorter[str] = TopologicalSorter(normalized)
    try:
        ts.prepare()
    except CycleError as exc:
        cycle = exc.args[1] if len(exc.args) > 1 else []
        return {"error": "cycle detected: " + " -> ".join(cycle)}

    waves: list[list[str]] = []
    order: list[str] = []
    while ts.is_active():
        ready = sorted(ts.get_ready())
        waves.append(ready)
        order.extend(ready)
        ts.done(*ready)

    return {
        "dependencies": normalized,
        "order": order,
        "waves": waves,
        "roots": waves[0] if waves else [],
        "node_count": len(order),
        "wave_count": len(waves),
    }
