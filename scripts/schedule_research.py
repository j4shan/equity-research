#!/usr/bin/env python3
"""Manage the research watchlist and seed batch runs for (scheduled) execution.

The recurring cron *trigger* itself is registered through the Claude Code
scheduling system (CronCreate / the /schedule skill) — see
``references/orchestration.md``. This script does the deterministic parts:

  * maintain the watchlist file the scheduled run reads, and
  * enqueue a batch run (4 analyst tasks per ticker) onto the durable task board,
    which a scheduled session then dispatches.

Usage:
  python scripts/schedule_research.py --list
  python scripts/schedule_research.py --add NVDA AMD TSM
  python scripts/schedule_research.py --remove TSM
  python scripts/schedule_research.py --enqueue [--label "daily watchlist"]
  python scripts/schedule_research.py --suggest-cron "0 22 * * 1-5"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # allow `research_hub` import when run as a file

from research_hub.schemas import WORKFLOW_ROLES  # noqa: E402
from research_hub.task_board import TaskBoard  # noqa: E402


def _assets_dir() -> Path:
    env = os.environ.get("RESEARCH_HUB_ASSETS_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (REPO_ROOT.parent / "equity_research_assets").resolve()


def _state_dir() -> Path:
    d = _assets_dir() / ".research_hub"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _watchlist_path() -> Path:
    return _state_dir() / "watchlist.json"


def _db_path() -> str:
    return os.environ.get("RESEARCH_HUB_DB", str(_state_dir() / "taskboard.db"))


def load_watchlist() -> list[str]:
    p = _watchlist_path()
    if p.exists():
        return json.loads(p.read_text()).get("tickers", [])
    return []


def save_watchlist(tickers: list[str]) -> None:
    uniq = sorted({t.upper().strip() for t in tickers if t.strip()})
    _watchlist_path().write_text(json.dumps({"tickers": uniq}, indent=2))


def enqueue_batch(label: str) -> dict:
    tickers = load_watchlist()
    if not tickers:
        raise SystemExit("watchlist is empty; add tickers with --add first")
    board = TaskBoard(_db_path())
    run_id = board.create_run(label=label or "watchlist batch")
    tasks = []
    for ticker in tickers:
        for role in WORKFLOW_ROLES:
            t = board.enqueue_task(run_id, ticker, role)
            tasks.append((t["task_id"], ticker, role))
    board.close()
    return {"run_id": run_id, "tickers": tickers, "n_tasks": len(tasks)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--add", nargs="+", metavar="TICKER")
    ap.add_argument("--remove", nargs="+", metavar="TICKER")
    ap.add_argument("--enqueue", action="store_true")
    ap.add_argument("--label", default="")
    ap.add_argument("--suggest-cron", metavar="CRON")
    args = ap.parse_args()

    if args.add:
        save_watchlist(load_watchlist() + args.add)
        print("watchlist:", load_watchlist())
    if args.remove:
        rm = {t.upper() for t in args.remove}
        save_watchlist([t for t in load_watchlist() if t not in rm])
        print("watchlist:", load_watchlist())
    if args.list or (not any([args.add, args.remove, args.enqueue, args.suggest_cron])):
        print("watchlist:", load_watchlist())
    if args.enqueue:
        result = enqueue_batch(args.label)
        print(json.dumps(result, indent=2))
    if args.suggest_cron:
        wl = ",".join(load_watchlist()) or "<watchlist>"
        print("\nRegister this recurring run via the Claude Code /schedule skill:")
        print(f"  cron:   {args.suggest_cron}")
        print(f"  prompt: Use the equity-research skill to refresh research for {wl} "
              "(load the graph snapshot first, then run the full workflow per ticker).")


if __name__ == "__main__":
    main()
