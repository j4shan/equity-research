#!/usr/bin/env python3
"""Deterministic driver for a daily risk-assessment run.

Two subcommands mirror the agent hand-off:

  bootstrap --run-dir DIR [--date YYYY-MM-DD]
      Create the run-dir skeleton and write ``fetch_spec.json`` (the MCP + HTTP
      calls the agent must make) and a ``raw/raw.template.json`` scaffold.

  run --run-dir DIR
      Read ``raw/raw.json`` (produced by the agent + HTTP adapters), run the
      engine, and write ``indicators.json``, ``composite.json``, ``dashboard.json``
      and a non-directional ``report.md``. Optionally reads ``calibration.json``.

All arithmetic is deterministic (research_hub.calculator); the same ``raw.json``
always yields the same artifacts.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from .adapters import build_fetch_spec
from .engine import run_engine
from .registry import load_registry
from .report import build_dashboard, render_report


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=False) + "\n")


def bootstrap(run_dir: Path, as_of: str) -> None:
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    registry = load_registry()
    spec = build_fetch_spec(registry)
    spec["as_of"] = as_of
    _write_json(run_dir / "fetch_spec.json", spec)

    template = {"as_of": as_of, "indicators": {
        ind.id: {"channels": [{"source": ch.source, "call": ch.call,
                               "value": None} for ch in ind.channels],
                 "history": []}
        for ind in registry}}
    _write_json(run_dir / "raw" / "raw.template.json", template)
    print(f"bootstrapped {run_dir} — {len(registry)} indicators, "
          f"{len(spec['mcp_calls'])} MCP calls, {len(spec['http_calls'])} HTTP calls")


def run(run_dir: Path) -> None:
    raw_path = run_dir / "raw" / "raw.json"
    if not raw_path.exists():
        raise SystemExit(f"missing {raw_path} — run bootstrap and fetch first")
    raw_doc = json.loads(raw_path.read_text())

    engine_out = run_engine(raw_doc, load_registry())
    _write_json(run_dir / "indicators.json", engine_out["indicators"])
    _write_json(run_dir / "composite.json", engine_out["composite"])
    _write_json(run_dir / "dashboard.json", build_dashboard(engine_out))

    cal_path = run_dir / "calibration.json"
    calibration = json.loads(cal_path.read_text()) if cal_path.exists() else None

    report_md = render_report(engine_out, calibration)  # raises if directional
    (run_dir / "report.md").write_text(report_md)

    comp = engine_out["composite"]
    print(f"run complete: overall={comp['overall']} "
          f"agreement={comp['agreement_pct']}% "
          f"divergences={len(comp['divergence_flags'])} "
          f"provisional={len(comp['provisional'])} -> {run_dir/'report.md'}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bootstrap", help="scaffold a run dir + fetch spec")
    b.add_argument("--run-dir", required=True)
    b.add_argument("--date", default=date.today().isoformat())

    r = sub.add_parser("run", help="score raw.json -> artifacts + report")
    r.add_argument("--run-dir", required=True)

    args = ap.parse_args(argv)
    run_dir = Path(args.run_dir)
    if args.cmd == "bootstrap":
        bootstrap(run_dir, args.date)
    else:
        run(run_dir)


if __name__ == "__main__":
    main()
