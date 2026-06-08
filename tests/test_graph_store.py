"""Unit tests for the in-memory knowledge graph."""

from pathlib import Path

from research_hub.graph_store import GraphStore
from research_hub.schemas import Edge, Node


def make_graph() -> GraphStore:
    g = GraphStore()
    g.upsert_node(Node("NVDA", name="NVIDIA", sector="Tech", role="primary"))
    g.upsert_node(Node("AMD", name="AMD", sector="Tech", role="peer"))
    g.upsert_node(Node("TSM", name="TSMC", sector="Tech", role="supplier"))
    g.add_edge(Edge("NVDA", "AMD", "competition", weight=0.9, confidence=0.8,
                    evidence="same GPU market"))
    g.add_edge(Edge("NVDA", "TSM", "dependency", weight=0.95, confidence=0.9,
                    evidence="fab outsourcing"))
    return g


def test_nodes_and_edges():
    g = make_graph()
    s = g.stats()
    assert s["nodes"] == 3
    assert s["edges"] == 2
    assert s["edges_by_relation"]["competition"] == 1
    assert s["edges_by_relation"]["dependency"] == 1


def test_findings_merge_not_clobber():
    g = make_graph()
    g.set_node_attrs("NVDA", "fundamentals", {"score": 0.6})
    g.set_node_attrs("NVDA", "technical", {"score": 0.4})
    node = g.get_node("NVDA")
    assert node["findings"]["fundamentals"]["score"] == 0.6
    assert node["findings"]["technical"]["score"] == 0.4


def test_neighbors_and_filter():
    g = make_graph()
    deps = g.neighbors("NVDA", relation="dependency")
    assert [n["neighbor"] for n in deps] == ["TSM"]
    alln = g.neighbors("NVDA")
    assert {n["neighbor"] for n in alln} == {"AMD", "TSM"}


def test_centrality_ranks_primary_first():
    g = make_graph()
    c = g.centrality("degree")
    assert max(c, key=c.get) == "NVDA"


def test_snapshot_roundtrip_preserves_relations(tmp_path: Path):
    g = make_graph()
    g.set_node_attrs("NVDA", "sentiment", {"score": 0.5})
    gpath = tmp_path / "g.graphml"
    jpath = tmp_path / "g.json"
    g.snapshot(str(gpath), str(jpath))
    assert gpath.exists() and jpath.exists()

    g2 = GraphStore()
    res = g2.load_snapshot(str(gpath))
    assert res["loaded"] is True
    assert g2.stats()["edges_by_relation"]["dependency"] == 1
    # findings survive the round-trip (re-hydrated from JSON string)
    assert g2.get_node("NVDA")["findings"]["sentiment"]["score"] == 0.5


def test_invalid_relation_rejected():
    g = GraphStore()
    try:
        g.add_edge(Edge("A", "B", "frenemy"))
    except ValueError:
        return
    raise AssertionError("expected ValueError for invalid relation")


def test_edge_to_unknown_node_rejected():
    g = make_graph()
    res = g.add_edge(Edge("NVDA", "ASML", "dependency"))
    assert "error" in res and "ASML" in res["error"]
    assert g.get_node("ASML") == {}  # no node was created


def test_relations_not_mutually_exclusive():
    g = make_graph()
    g.add_edge(Edge("NVDA", "AMD", "collaboration", weight=0.3,
                    evidence="open interconnect consortium"))
    rels = {e["relation"] for e in g.query_edges()
            if e["source"] == "NVDA" and e["target"] == "AMD"}
    assert rels == {"competition", "collaboration"}


def test_merge_update_appends_summaries_and_refreshes_scalars():
    g = make_graph()
    g.add_edge(Edge("NVDA", "AMD", "competition", weight=0.9,
                    summaries=["run1: GPU rivalry"]))
    merged = g.add_edge(Edge("NVDA", "AMD", "competition", weight=0.95,
                             confidence=0.9, evidence="AI accelerators",
                             summaries=["run2: MI300 vs H100"]))
    assert merged["weight"] == 0.95
    assert merged["evidence"] == "AI accelerators"
    assert merged["summaries"] == ["run1: GPU rivalry", "run2: MI300 vs H100"]
    # still one competition edge for the pair
    comp = [e for e in g.query_edges("competition")
            if e["source"] == "NVDA" and e["target"] == "AMD"]
    assert len(comp) == 1


def test_summaries_survive_snapshot_and_merge_after_reload(tmp_path: Path):
    g = make_graph()
    g.add_edge(Edge("NVDA", "AMD", "competition", summaries=["run1"]))
    gpath = tmp_path / "g.graphml"
    g.snapshot(str(gpath))

    g2 = GraphStore()
    g2.load_snapshot(str(gpath))
    merged = g2.add_edge(Edge("NVDA", "AMD", "competition", summaries=["run2"]))
    assert merged["summaries"] == ["run1", "run2"]
    comp = [e for e in g2.query_edges("competition")
            if e["source"] == "NVDA" and e["target"] == "AMD"]
    assert len(comp) == 1  # identity preserved across the GraphML round-trip
