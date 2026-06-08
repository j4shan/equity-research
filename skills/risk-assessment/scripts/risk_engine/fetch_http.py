#!/usr/bin/env python3
"""Fetch the Python-callable (HTTP) channels and merge them into ``raw.json``.

The agent handles the MCP channels; this handles the deterministic HTTP ones. Only
FRED ``series <ID>`` calls are fully automated here (a clean, well-specified API);
FearGreedChart/AAII payloads vary by endpoint and are left to the agent to parse
from ``fear_greed_chart`` / ``aaii_sentiment``. Missing key or a dead source
degrades to a null channel value (the engine marks it provisional/missing) — never
an exception that sinks the run.

Usage:
    python -m risk_engine.fetch_http --run-dir DIR
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from .adapters.http_sources import fred_series, history_values, latest

HttpGet = Callable[[str], str]


def _fred_series_id(call: str) -> str | None:
    parts = call.split()
    if len(parts) >= 2 and parts[0] == "series":
        return parts[1]
    return None


def merge_fred_channels(run_dir: Path, *, http_get: HttpGet | None = None,
                        api_key: str | None = None) -> dict[str, Any]:
    """Fill FRED channel values (and history where empty) into ``raw/raw.json``.

    Reads ``fetch_spec.json`` for the HTTP call list, starts from an existing
    ``raw/raw.json`` (or the bootstrap template), fetches each FRED series, and
    writes the merged ``raw/raw.json``. Returns a per-indicator status map.
    """
    spec = json.loads((run_dir / "fetch_spec.json").read_text())
    raw_path = run_dir / "raw" / "raw.json"
    template = run_dir / "raw" / "raw.template.json"
    raw = json.loads((raw_path if raw_path.exists() else template).read_text())
    indicators = raw.setdefault("indicators", {})

    status: dict[str, Any] = {}
    for call in spec.get("http_calls", []):
        if call["source"] != "fred":
            continue
        sid = _fred_series_id(call["call"])
        if not sid:
            continue
        res = fred_series(sid, api_key=api_key, http_get=http_get)
        ind_id = call["indicator_id"]
        node = indicators.setdefault(ind_id, {"channels": [], "history": []})

        # set/append the fred channel value
        val = latest(res)
        found = False
        for ch in node.setdefault("channels", []):
            if ch.get("source") == "fred":
                ch["value"] = val
                ch["ts"] = res.get("date")
                found = True
        if not found:
            node["channels"].append({"source": "fred", "value": val,
                                     "ts": res.get("date"), "call": call["call"]})
        # seed history from FRED only when nothing better is present
        if not node.get("history") and "error" not in res:
            node["history"] = history_values(res)
        status[ind_id] = {"series": sid, "value": val,
                          "error": res.get("error")}

    raw_path.write_text(json.dumps(raw, indent=2) + "\n")
    return status


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args(argv)
    status = merge_fred_channels(Path(args.run_dir))
    ok = sum(1 for s in status.values() if not s.get("error"))
    print(f"FRED merge: {ok}/{len(status)} channels filled "
          f"-> {Path(args.run_dir) / 'raw' / 'raw.json'}")
    for ind_id, s in status.items():
        if s.get("error"):
            print(f"  ! {ind_id} ({s['series']}): {s['error']}")


if __name__ == "__main__":
    main()
