"""Durable task board backed by SQLite.

Implements the workflow queue + lifecycle FSM that the manager and workers
coordinate through. SQLite gives durability (tasks survive across sessions and
scheduled runs) and queryability (observability), while a process-level lock
serializes transitions so concurrent worker tool-calls can't corrupt state.

Lifecycle:  queued -> claimed -> running -> done | failed
            failed -> queued   (bounded retry)
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from .schemas import (
    TASK_STATES,
    TERMINAL_STATES,
    Task,
    new_id,
    now_ts,
)

MAX_ATTEMPTS = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    label       TEXT,
    created_at  REAL,
    meta        TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id     TEXT PRIMARY KEY,
    run_id      TEXT,
    ticker      TEXT,
    role        TEXT,
    status      TEXT,
    priority    INTEGER,
    attempts    INTEGER,
    worker      TEXT,
    result_ref  TEXT,
    error       TEXT,
    created_at  REAL,
    started_at  REAL,
    finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
"""

_COLUMNS = [
    "task_id", "run_id", "ticker", "role", "status", "priority", "attempts",
    "worker", "result_ref", "error", "created_at", "started_at", "finished_at",
]


class TaskBoard:
    """SQLite-backed queue + lifecycle tracker."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._lock = threading.RLock()
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the MCP server may dispatch across threads;
        # the RLock makes our own access serial regardless.
        self._con = sqlite3.connect(db_path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.executescript(_SCHEMA)
            self._con.commit()

    # --- runs ------------------------------------------------------------

    def create_run(self, label: str = "", meta: str = "") -> str:
        run_id = new_id("run")
        with self._lock:
            self._con.execute(
                "INSERT INTO runs(run_id, label, created_at, meta) VALUES(?,?,?,?)",
                (run_id, label, now_ts(), meta),
            )
            self._con.commit()
        return run_id

    # --- task creation ---------------------------------------------------

    def enqueue_task(
        self, run_id: str, ticker: str, role: str, priority: int = 5
    ) -> dict[str, Any]:
        task = Task(run_id=run_id, ticker=ticker.upper().strip(), role=role,
                    priority=priority)
        with self._lock:
            self._con.execute(
                f"INSERT INTO tasks({','.join(_COLUMNS)}) "
                f"VALUES({','.join('?' * len(_COLUMNS))})",
                self._task_row(task),
            )
            self._con.commit()
        return self.get_task(task.task_id)

    # --- lifecycle transitions ------------------------------------------

    def next_task(self, run_id: Optional[str] = None) -> dict[str, Any]:
        """Peek the highest-priority queued task (does not claim it)."""
        q = "SELECT * FROM tasks WHERE status='queued'"
        params: tuple = ()
        if run_id:
            q += " AND run_id=?"
            params = (run_id,)
        q += " ORDER BY priority ASC, created_at ASC LIMIT 1"
        with self._lock:
            row = self._con.execute(q, params).fetchone()
        return dict(row) if row else {}

    def claim_task(self, task_id: str, worker: str) -> dict[str, Any]:
        return self._transition(
            task_id, allowed=("queued",), new="claimed",
            sets={"worker": worker},
        )

    def start_task(self, task_id: str) -> dict[str, Any]:
        return self._transition(
            task_id, allowed=("claimed", "queued"), new="running",
            sets={"started_at": now_ts()}, bump_attempts=True,
        )

    def complete_task(self, task_id: str, result_ref: str = "") -> dict[str, Any]:
        return self._transition(
            task_id, allowed=("running", "claimed"), new="done",
            sets={"finished_at": now_ts(), "result_ref": result_ref, "error": ""},
        )

    def fail_task(self, task_id: str, error: str, retry: bool = True) -> dict[str, Any]:
        """Mark failed; optionally requeue if attempts remain."""
        with self._lock:
            cur = self.get_task(task_id)
            if not cur:
                return {}
            if retry and cur["attempts"] < MAX_ATTEMPTS:
                return self._transition(
                    task_id, allowed=("running", "claimed", "queued"),
                    new="queued",
                    sets={"error": error, "started_at": None, "worker": ""},
                )
            return self._transition(
                task_id, allowed=("running", "claimed", "queued"),
                new="failed",
                sets={"finished_at": now_ts(), "error": error},
            )

    # --- observability ---------------------------------------------------

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._con.execute(
                "SELECT * FROM tasks WHERE task_id=?", (task_id,)
            ).fetchone()
        return dict(row) if row else {}

    def list_tasks(
        self, run_id: Optional[str] = None, status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        q, params = "SELECT * FROM tasks", []
        clauses = []
        if run_id:
            clauses.append("run_id=?")
            params.append(run_id)
        if status:
            clauses.append("status=?")
            params.append(status)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY priority ASC, created_at ASC"
        with self._lock:
            rows = self._con.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Status board: per-state counts, durations, completion flag."""
        tasks = self.list_tasks(run_id=run_id)
        counts = {s: 0 for s in TASK_STATES}
        for t in tasks:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
        done = sum(counts[s] for s in TERMINAL_STATES)
        durations = [
            round(t["finished_at"] - t["started_at"], 3)
            for t in tasks
            if t.get("started_at") and t.get("finished_at")
        ]
        return {
            "run_id": run_id,
            "total": len(tasks),
            "counts": counts,
            "complete": len(tasks) > 0 and done == len(tasks),
            "avg_duration": round(sum(durations) / len(durations), 3) if durations else None,
            "tasks": tasks,
        }

    def render_run_log(self, run_id: str, fmt: str = "markdown") -> str:
        """Human-readable lifecycle table for the report's observability section."""
        tasks = self.list_tasks(run_id=run_id)
        headers = ["task_id", "ticker", "role", "status", "attempts",
                   "duration(s)", "result_ref", "error"]

        def row_vals(t: dict) -> list[str]:
            dur = ""
            if t.get("started_at") and t.get("finished_at"):
                dur = f"{t['finished_at'] - t['started_at']:.2f}"
            return [
                t["task_id"], t["ticker"], t["role"], t["status"],
                str(t["attempts"]), dur, t.get("result_ref", "") or "",
                (t.get("error", "") or "")[:60],
            ]

        if fmt == "html":
            head = "".join(f"<th>{h}</th>" for h in headers)
            body = "".join(
                "<tr>" + "".join(f"<td>{c}</td>" for c in row_vals(t)) + "</tr>"
                for t in tasks
            )
            return f"<table class='run-log'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

        lines = ["| " + " | ".join(headers) + " |",
                 "|" + "|".join(["---"] * len(headers)) + "|"]
        for t in tasks:
            lines.append("| " + " | ".join(row_vals(t)) + " |")
        return "\n".join(lines)

    # --- internals -------------------------------------------------------

    def _transition(
        self, task_id: str, allowed: tuple[str, ...], new: str,
        sets: Optional[dict] = None, bump_attempts: bool = False,
    ) -> dict[str, Any]:
        sets = sets or {}
        with self._lock:
            cur = self.get_task(task_id)
            if not cur:
                return {"error": f"task {task_id} not found"}
            if cur["status"] not in allowed:
                return {
                    "error": f"illegal transition {cur['status']} -> {new}",
                    "task_id": task_id, "status": cur["status"],
                }
            fields = {"status": new, **sets}
            if bump_attempts:
                fields["attempts"] = cur["attempts"] + 1
            assignments = ", ".join(f"{k}=?" for k in fields)
            self._con.execute(
                f"UPDATE tasks SET {assignments} WHERE task_id=?",
                (*fields.values(), task_id),
            )
            self._con.commit()
        return self.get_task(task_id)

    @staticmethod
    def _task_row(task: Task) -> tuple:
        return (
            task.task_id, task.run_id, task.ticker, task.role, task.status,
            task.priority, task.attempts, task.worker, task.result_ref,
            task.error, task.created_at, task.started_at, task.finished_at,
        )

    def close(self) -> None:
        with self._lock:
            self._con.close()
