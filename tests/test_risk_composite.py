"""Tests for the equal-weight composite and its orientation onto the risk axis."""

from risk_engine.engine.composite import build_composite


def _rec(id, layer, value_pct, direction, cross="agree", conf=0.9, **extra):
    r = {"id": id, "layer": layer, "value_pct": value_pct, "direction": direction,
         "cross_check": cross, "confidence": conf, "contrarian": False,
         "divergence": None}
    r.update(extra)
    return r


def test_orientation_high_vs_low():
    inds = [
        _rec("a", "fear", 80, "risk_off_when_high"),   # -> risk 80
        _rec("b", "macro", 80, "risk_off_when_low"),   # -> risk 20
    ]
    comp = build_composite(inds)
    assert comp["layers"]["fear"]["score"] == 80.0
    assert comp["layers"]["macro"]["score"] == 20.0
    assert comp["overall"] == 50.0  # equal-weight mean of present layers


def test_confidence_weighting_within_layer():
    inds = [
        _rec("a", "fear", 100, "risk_off_when_high", conf=0.9),
        _rec("b", "fear", 0, "risk_off_when_high", conf=0.45),
    ]
    comp = build_composite(inds)
    # (100*0.9 + 0*0.45) / (0.9+0.45) = 66.67
    assert comp["layers"]["fear"]["score"] == 66.67


def test_agreement_excludes_missing():
    inds = [
        _rec("a", "fear", 50, "risk_off_when_high", cross="agree"),
        _rec("b", "fear", 50, "risk_off_when_high", cross="divergence", conf=0.45),
        _rec("c", "macro", None, "risk_off_when_high", cross="missing", conf=0.0),
    ]
    comp = build_composite(inds)
    # 1 agree out of 2 scored (missing excluded) -> 50%
    assert comp["agreement_pct"] == 50.0
    assert comp["n_scored"] == 2


def test_contrarian_extreme_flagged():
    inds = [_rec("vix", "fear", 5.0, "risk_off_when_high", contrarian=True)]
    comp = build_composite(inds)
    assert comp["contrarian_flags"][0]["kind"] == "complacency"


def test_empty_layer_scores_none():
    comp = build_composite([_rec("a", "fear", 50, "risk_off_when_high")])
    assert comp["layers"]["sector"]["score"] is None
    assert comp["layers"]["sector"]["n"] == 0
