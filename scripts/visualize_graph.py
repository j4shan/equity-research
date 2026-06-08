#!/usr/bin/env python3
"""Render the sector knowledge graph to an interactive HTML network (pyvis).

Reads ``<run-dir>/knowledge_graph.json`` (node-link JSON produced by the Research
Hub ``graph_snapshot``) and writes ``<run-dir>/graph.html``.

Edge color encodes the ecological relation type; edge width encodes weight; node
size encodes degree; the primary node is highlighted.

Usage:
    python scripts/visualize_graph.py --run-dir <RUN_DIR>
    python scripts/visualize_graph.py --graph path/to/knowledge_graph.json --out graph.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyvis.network import Network

RELATION_COLORS = {
    "competition": "#e63946",   # red — rivalry
    "collaboration": "#2a9d8f",  # teal — partnership
    "dependency": "#e9a000",     # amber — reliance
    "symbiosis": "#6a4c93",      # purple — mutualism
}
ROLE_COLORS = {
    "primary": "#1d3557",
    "peer": "#457b9d",
    "supplier": "#8d99ae",
    "customer": "#a8dadc",
    "partner": "#83c5be",
}


def _load_graph(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"graph json not found: {path}")
    return json.loads(path.read_text())


def build_network(graph: dict) -> Network:
    net = Network(
        height="780px", width="100%", directed=True,
        bgcolor="#ffffff", font_color="#1d3557", notebook=False,
        cdn_resources="in_line",
    )
    net.barnes_hut(gravity=-12000, central_gravity=0.3, spring_length=160)

    # degree for sizing
    deg: dict[str, int] = {}
    for e in graph.get("edges", []):
        deg[e["source"]] = deg.get(e["source"], 0) + 1
        deg[e["target"]] = deg.get(e["target"], 0) + 1

    for n in graph.get("nodes", []):
        ticker = n["ticker"]
        role = n.get("role", "peer")
        size = 18 + 6 * deg.get(ticker, 0)
        findings = n.get("findings", {})
        if isinstance(findings, str):
            try:
                findings = json.loads(findings)
            except json.JSONDecodeError:
                findings = {}
        title_lines = [f"<b>{ticker}</b> — {n.get('name','')}",
                       f"role: {role}", f"sector: {n.get('sector','')}"]
        for role_key in ("fundamentals", "technical", "sentiment"):
            f = findings.get(role_key) if isinstance(findings, dict) else None
            if isinstance(f, dict) and "score" in f:
                title_lines.append(f"{role_key} score: {f['score']:+.2f}")
        net.add_node(
            ticker, label=ticker, size=size,
            color=ROLE_COLORS.get(role, "#457b9d"),
            borderWidth=3 if role == "primary" else 1,
            title="<br>".join(title_lines),
        )

    for e in graph.get("edges", []):
        rel = e.get("relation", "competition")
        w = float(e.get("weight", 0.5) or 0.5)
        net.add_edge(
            e["source"], e["target"],
            color=RELATION_COLORS.get(rel, "#999999"),
            width=1 + 6 * w,
            title=f"{rel} (w={w:.2f}, conf={float(e.get('confidence',0) or 0):.2f})"
                  f"<br>{e.get('evidence','')}",
            arrows="to",
        )
    net.set_options('{"interaction": {"hover": true, "tooltipDelay": 80}}')
    return net


def _legend_html() -> str:
    items = "".join(
        f'<span style="display:inline-block;margin:0 10px;">'
        f'<span style="display:inline-block;width:14px;height:14px;background:{c};'
        f'vertical-align:middle;border-radius:2px;"></span> {r}</span>'
        for r, c in RELATION_COLORS.items()
    )
    return (
        '<div style="font-family:system-ui;padding:10px 16px;border-bottom:1px solid #eee;">'
        '<b>Sector Knowledge Graph</b> &nbsp; edge color = relation, width = strength &nbsp;|&nbsp; '
        + items + "</div>"
    )


def render(graph_path: Path, out_path: Path) -> Path:
    graph = _load_graph(graph_path)
    net = build_network(graph)
    html = net.generate_html(notebook=False)
    html = html.replace("<body>", "<body>" + _legend_html(), 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", help="run folder containing knowledge_graph.json")
    ap.add_argument("--graph", help="explicit path to knowledge_graph.json")
    ap.add_argument("--out", help="explicit output html path")
    args = ap.parse_args()

    if args.run_dir:
        run = Path(args.run_dir)
        graph_path = Path(args.graph) if args.graph else run / "knowledge_graph.json"
        out_path = Path(args.out) if args.out else run / "graph.html"
    elif args.graph:
        graph_path = Path(args.graph)
        out_path = Path(args.out) if args.out else graph_path.with_name("graph.html")
    else:
        raise SystemExit("provide --run-dir or --graph")

    out = render(graph_path, out_path)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
