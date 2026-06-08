"""Tests for the risk-agent indicator registry loader + transform parsing."""

import pytest

from risk_engine import LAYERS
from risk_engine.registry import (
    RegistryError,
    load_registry,
    parse_transform,
)
from risk_engine.registry.load import _build


def test_registry_loads_and_is_well_formed():
    reg = load_registry()
    assert len(reg) >= 18
    ids = [i.id for i in reg]
    assert len(ids) == len(set(ids))  # unique
    assert {i.layer for i in reg} <= set(LAYERS)
    # every indicator has at least one channel; multi-channel unless flagged single
    for ind in reg:
        assert ind.channels
        assert ind.single_channel == (len(ind.channels) < 2)


def test_seed_set_spans_all_four_layers():
    by_layer = {ly: 0 for ly in LAYERS}
    for ind in load_registry():
        by_layer[ind.layer] += 1
    assert all(v > 0 for v in by_layer.values()), by_layer


def test_parse_transform_units():
    assert parse_transform("percentile_252d") == ("percentile", 252)
    assert parse_transform("zscore_260w") == ("zscore", 1300)   # 260 * 5
    assert parse_transform("percentile_120m") == ("percentile", 2520)  # 120 * 21
    with pytest.raises(RegistryError):
        parse_transform("bogus")


def test_duplicate_id_rejected(tmp_path):
    import yaml
    rec = {"id": "x", "layer": "fear", "refresh_class": "daily",
           "direction": "risk_off_when_high", "transform": "percentile_10d",
           "channels": [{"source": "fmp", "call": "c"}]}
    p = tmp_path / "dup.yaml"
    p.write_text(yaml.safe_dump([rec, rec]))
    with pytest.raises(RegistryError, match="duplicate"):
        load_registry(p)


def test_malformed_records_rejected():
    with pytest.raises(RegistryError):
        _build({"id": "x", "layer": "nope", "refresh_class": "daily",
                "direction": "risk_off_when_high", "transform": "percentile_10d",
                "channels": [{"source": "fmp", "call": "c"}]}, 0)
    with pytest.raises(RegistryError):
        _build({"id": "x", "layer": "fear", "refresh_class": "daily",
                "direction": "sideways", "transform": "percentile_10d",
                "channels": [{"source": "fmp", "call": "c"}]}, 0)
    with pytest.raises(RegistryError):
        _build({"id": "x", "layer": "fear", "refresh_class": "daily",
                "direction": "risk_off_when_high", "transform": "percentile_10d",
                "channels": [{"source": "unknown_src", "call": "c"}]}, 0)
