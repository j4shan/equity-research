"""Tests for the deterministic topological sort behind plan_toposort."""

from research_hub.toposort import sort


def test_diamond_dag_order_and_waves():
    r = sort({"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"]})
    assert r["waves"] == [["a"], ["b", "c"], ["d"]]
    assert r["order"] == ["a", "b", "c", "d"]
    assert r["roots"] == ["a"]
    assert r["node_count"] == 4
    assert r["wave_count"] == 3
    # every task appears after all of its prerequisites
    pos = {t: i for i, t in enumerate(r["order"])}
    assert pos["b"] > pos["a"] and pos["c"] > pos["a"]
    assert pos["d"] > pos["b"] and pos["d"] > pos["c"]


def test_linear_chain_is_one_task_per_wave():
    r = sort({"a": [], "b": ["a"], "c": ["b"]})
    assert r["waves"] == [["a"], ["b"], ["c"]]
    assert r["wave_count"] == 3


def test_independent_tasks_share_one_wave():
    r = sort({"a": [], "b": [], "c": []})
    assert r["waves"] == [["a", "b", "c"]]
    assert r["wave_count"] == 1


def test_prerequisite_not_a_key_becomes_root():
    # "seed" is only referenced, never a key
    r = sort({"work": ["seed"]})
    assert r["roots"] == ["seed"]
    assert r["waves"] == [["seed"], ["work"]]
    assert r["node_count"] == 2


def test_within_wave_ordering_is_deterministic_alphabetical():
    r = sort({"z": [], "m": [], "a": []})
    assert r["waves"][0] == ["a", "m", "z"]


def test_ids_are_stripped():
    r = sort({" a ": [], "b": [" a "]})
    assert r["order"] == ["a", "b"]


def test_cycle_is_returned_not_raised():
    r = sort({"a": ["b"], "b": ["a"]})
    assert "error" in r
    assert "cycle" in r["error"]
    assert "a" in r["error"] and "b" in r["error"]


def test_three_node_cycle_reports_nodes():
    r = sort({"a": ["c"], "b": ["a"], "c": ["b"]})
    assert "error" in r
    for node in ("a", "b", "c"):
        assert node in r["error"]


def test_self_dependency_rejected():
    assert "error" in sort({"a": ["a"]})


def test_empty_and_bad_inputs_rejected():
    assert "error" in sort({})
    assert "error" in sort({"": []})
    assert "error" in sort({"a": "not-a-list"})
    assert "error" in sort({"a": [1]})
    assert "error" in sort({"a": [""]})


def test_too_many_nodes_rejected():
    big = {f"t{i}": [] for i in range(501)}
    assert "error" in sort(big)
