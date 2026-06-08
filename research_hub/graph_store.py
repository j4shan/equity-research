"""In-memory knowledge graph backed by networkx.

A single instance of :class:`GraphStore` lives inside the MCP server process and
is therefore shared by the manager (main thread) and every worker subagent.
Because the server processes tool calls serially, mutations are naturally
serialized — agents never need their own locks.

Persistence: the live graph is snapshotted to GraphML + JSON in the assets repo
and reloaded on startup so it survives across sessions and scheduled runs.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

import networkx as nx

from .schemas import Edge, Node, RELATION_TYPES


class GraphStore:
    """Thread-safe wrapper around a directed multigraph of company relationships."""

    def __init__(self) -> None:
        # MultiDiGraph: directed (relationships have direction) and multi
        # (two firms can both compete AND collaborate — distinct edges).
        self._g = nx.MultiDiGraph()
        self._lock = threading.RLock()

    # --- mutation --------------------------------------------------------

    def upsert_node(self, node: Node) -> dict[str, Any]:
        """Create or update a node, merging findings rather than clobbering."""
        with self._lock:
            t = node.ticker
            if self._g.has_node(t):
                existing = self._g.nodes[t]
                attrs = node.as_attrs()
                # Merge findings dicts so concurrent analysts don't overwrite.
                merged = dict(existing.get("findings", {}))
                merged.update(attrs.get("findings", {}))
                attrs["findings"] = merged
                # Don't let blank fields erase populated ones.
                for k, v in list(attrs.items()):
                    if v in ("", None) and existing.get(k) not in ("", None):
                        attrs[k] = existing[k]
                self._g.nodes[t].update(attrs)
            else:
                self._g.add_node(t, **node.as_attrs())
            return self.get_node(t)

    def set_node_attrs(
        self, ticker: str, analyst_role: str, findings: dict[str, Any]
    ) -> dict[str, Any]:
        """Attach one analyst's findings to a node under its role key."""
        t = ticker.upper().strip()
        with self._lock:
            if not self._g.has_node(t):
                self._g.add_node(t, **Node(ticker=t).as_attrs())
            node_findings = dict(self._g.nodes[t].get("findings", {}))
            node_findings[analyst_role] = findings
            self._g.nodes[t]["findings"] = node_findings
            return self.get_node(t)

    def add_edge(self, edge: Edge) -> dict[str, Any]:
        """Merge-update a typed relationship.

        Edge identity = (source, target, relation); the relation is the
        multigraph key, so non-exclusive relations (competition AND
        collaboration between the same pair) coexist as distinct edges.
        Re-asserting an existing identity refreshes the scalar attrs
        (weight/confidence/evidence) and APPENDS the run's finalized
        summaries to the edge's ``summaries`` list — nothing is clobbered.

        Both endpoints must already exist in the graph: agents do not create
        nodes for companies that surface in relationship study but are outside
        the seeded universe.
        """
        with self._lock:
            missing = [t for t in (edge.source, edge.target)
                       if not self._g.has_node(t)]
            if missing:
                return {"error": f"unknown node(s) {missing}: edges may only "
                                 "connect companies already in the graph; do "
                                 "not create nodes for out-of-universe tickers"}
            attrs = edge.as_attrs()
            new_summaries = [s for s in attrs.pop("summaries", []) if s]
            key = edge.relation
            if self._g.has_edge(edge.source, edge.target, key):
                existing = self._g[edge.source][edge.target][key]
                merged = list(existing.get("summaries", []))
                merged.extend(new_summaries)
                existing.update(attrs)
                existing["summaries"] = merged
            else:
                self._g.add_edge(edge.source, edge.target, key=key,
                                 **attrs, summaries=new_summaries)
            return {
                "source": edge.source,
                "target": edge.target,
                "relation": key,
                **dict(self._g[edge.source][edge.target][key]),
            }

    # --- queries (low-latency relationship access) -----------------------

    def get_node(self, ticker: str) -> dict[str, Any]:
        t = ticker.upper().strip()
        with self._lock:
            if not self._g.has_node(t):
                return {}
            return {"ticker": t, **dict(self._g.nodes[t])}

    def neighbors(self, ticker: str, relation: Optional[str] = None) -> list[dict]:
        """Outgoing + incoming neighbors, optionally filtered by relation."""
        t = ticker.upper().strip()
        with self._lock:
            if not self._g.has_node(t):
                return []
            out = []
            for u, v, data in self._g.out_edges(t, data=True):
                if relation is None or data.get("relation") == relation:
                    out.append({"direction": "out", "neighbor": v, **data})
            for u, v, data in self._g.in_edges(t, data=True):
                if relation is None or data.get("relation") == relation:
                    out.append({"direction": "in", "neighbor": u, **data})
            return out

    def query_edges(self, relation: Optional[str] = None) -> list[dict]:
        with self._lock:
            edges = []
            for u, v, data in self._g.edges(data=True):
                if relation is None or data.get("relation") == relation:
                    edges.append({"source": u, "target": v, **data})
            return edges

    def get_subgraph(self, tickers: Optional[list[str]] = None) -> dict[str, Any]:
        """Return a node-link JSON view (full graph or an induced subgraph)."""
        with self._lock:
            g = self._g
            if tickers:
                wanted = {t.upper().strip() for t in tickers}
                g = self._g.subgraph([n for n in self._g.nodes if n in wanted])
            return _to_node_link(g)

    def centrality(self, kind: str = "degree") -> dict[str, float]:
        """Rank systemic importance. kind in {degree, eigenvector, betweenness}."""
        with self._lock:
            if self._g.number_of_nodes() == 0:
                return {}
            try:
                if kind == "eigenvector":
                    scores = nx.eigenvector_centrality(self._g, max_iter=500)
                elif kind == "betweenness":
                    scores = nx.betweenness_centrality(self._g)
                else:
                    scores = nx.degree_centrality(self._g)
            except nx.NetworkXException:
                scores = nx.degree_centrality(self._g)
            return {k: round(v, 4) for k, v in sorted(
                scores.items(), key=lambda kv: kv[1], reverse=True)}

    def shortest_path(self, source: str, target: str) -> list[str]:
        s, t = source.upper().strip(), target.upper().strip()
        with self._lock:
            try:
                return nx.shortest_path(self._g.to_undirected(as_view=True), s, t)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return []

    def stats(self) -> dict[str, Any]:
        with self._lock:
            by_rel = {r: 0 for r in RELATION_TYPES}
            for _, _, data in self._g.edges(data=True):
                rel = data.get("relation")
                if rel in by_rel:
                    by_rel[rel] += 1
            return {
                "nodes": self._g.number_of_nodes(),
                "edges": self._g.number_of_edges(),
                "edges_by_relation": by_rel,
            }

    # --- persistence -----------------------------------------------------

    def snapshot(self, graphml_path: str, json_path: Optional[str] = None) -> dict:
        """Serialize the live graph to GraphML (+ optional node-link JSON)."""
        with self._lock:
            gpath = Path(graphml_path)
            gpath.parent.mkdir(parents=True, exist_ok=True)
            # GraphML can't hold nested dicts/lists; flatten findings and edge
            # summaries to JSON strings.
            g = self._g.copy()
            for _, attrs in g.nodes(data=True):
                if isinstance(attrs.get("findings"), dict):
                    attrs["findings"] = json.dumps(attrs["findings"])
                for k, v in list(attrs.items()):
                    if v is None:
                        attrs[k] = ""
            for _, _, attrs in g.edges(data=True):
                if isinstance(attrs.get("summaries"), list):
                    attrs["summaries"] = json.dumps(attrs["summaries"])
            nx.write_graphml(g, gpath)
            out = {"graphml": str(gpath), "nodes": self._g.number_of_nodes(),
                   "edges": self._g.number_of_edges()}
            if json_path:
                jpath = Path(json_path)
                jpath.parent.mkdir(parents=True, exist_ok=True)
                jpath.write_text(json.dumps(_to_node_link(self._g), indent=2))
                out["json"] = str(jpath)
            return out

    def load_snapshot(self, graphml_path: str) -> dict:
        """Replace the live graph with a previously saved GraphML snapshot."""
        path = Path(graphml_path)
        with self._lock:
            if not path.exists():
                return {"loaded": False, "reason": "no snapshot"}
            g = nx.read_graphml(path)
            # Re-hydrate findings / edge summaries from JSON strings.
            for _, attrs in g.nodes(data=True):
                f = attrs.get("findings")
                if isinstance(f, str) and f:
                    try:
                        attrs["findings"] = json.loads(f)
                    except json.JSONDecodeError:
                        attrs["findings"] = {}
            for _, _, attrs in g.edges(data=True):
                s = attrs.get("summaries")
                if isinstance(s, str):
                    try:
                        attrs["summaries"] = json.loads(s) if s else []
                    except json.JSONDecodeError:
                        attrs["summaries"] = []
            # Rebuild keyed by relation: GraphML doesn't reliably preserve
            # multigraph keys, and merge-update identity depends on key=relation.
            rebuilt = nx.MultiDiGraph()
            rebuilt.add_nodes_from(g.nodes(data=True))
            for u, v, attrs in g.edges(data=True):
                rebuilt.add_edge(u, v, key=attrs.get("relation"), **attrs)
            self._g = rebuilt
            return {"loaded": True, **self.stats()}

    def clear(self) -> None:
        with self._lock:
            self._g.clear()


def _to_node_link(g: nx.Graph) -> dict[str, Any]:
    """Stable node-link JSON used by viz scripts and the JSON snapshot."""
    return {
        "nodes": [{"ticker": n, **dict(attrs)} for n, attrs in g.nodes(data=True)],
        "edges": [
            {"source": u, "target": v, **dict(data)}
            for u, v, data in g.edges(data=True)
        ],
    }
