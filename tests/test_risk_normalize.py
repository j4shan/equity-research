"""Tests for normalization (percentile rank + display statistics)."""

from risk_engine.engine.normalize import normalize, percentile_rank


def test_percentile_rank_midrank():
    assert percentile_rank(15.1, [10, 12, 14, 16, 18]) == 60.0
    assert percentile_rank(5, [10, 20, 30]) == 0.0
    assert percentile_rank(40, [10, 20, 30]) == 100.0
    # tie -> mid-rank (half credit for equals)
    assert percentile_rank(20, [10, 20, 20, 30]) == 50.0


def test_percentile_rank_empty_history():
    assert percentile_rank(5, []) is None


def test_normalize_percentile_value_pct_is_uniform_quantity():
    out = normalize(15.1, [10, 12, 14, 16, 18], "percentile", 252)
    assert out["value"] == 15.1
    assert out["value_pct"] == 60.0
    assert out["stat_value"] == 60.0
    assert out["n_obs"] == 5
    assert out["history_sufficient"] is False   # 5 < max(30, 63)


def test_normalize_history_sufficient_threshold():
    hist = list(range(70))
    out = normalize(35, hist, "percentile", 252)
    assert out["n_obs"] == 70 and out["history_sufficient"] is True


def test_normalize_zscore_stat():
    out = normalize(10, [2, 4, 4, 4, 5, 5, 7, 9], "zscore", 252)
    # population std of that set is 2.0, mean 5.0 -> z = (10-5)/2 = 2.5
    assert out["stat_value"] == 2.5
    assert out["value_pct"] == 100.0  # 10 above all history


def test_normalize_missing_value():
    out = normalize(None, [1, 2, 3], "percentile", 252)
    assert out["value_pct"] is None and out["n_obs"] == 0
