"""Tests for the safe arithmetic evaluator behind calc_evaluate."""

from research_hub.calculator import evaluate


def test_basic_arithmetic():
    assert evaluate("2 + 3 * 4")["result"] == 14
    assert evaluate("(1 + 2) ** 2 / 3")["result"] == 3
    assert evaluate("-7 % 3")["result"] == 2


def test_variables_and_growth_rate():
    r = evaluate("(rev1 - rev0) / rev0", {"rev1": 60922, "rev0": 26974})
    assert abs(r["result"] - 1.2586) < 1e-3


def test_list_functions():
    assert evaluate("mean(pes)", {"pes": [60.1, 45.0, 22.0, 24.0]})["result"] == 37.775
    assert evaluate("median([1, 2, 3, 4, 5])")["result"] == 3
    assert evaluate("max(xs) - min(xs)", {"xs": [3, 9, 1]})["result"] == 8
    assert evaluate("round(std([2, 4, 4, 4, 5, 5, 7, 9]), 4)")["result"] == 2.0


def test_errors_are_returned_not_raised():
    assert "error" in evaluate("1 / 0")
    assert "error" in evaluate("unknown_var + 1")
    assert "error" in evaluate("")
    assert "error" in evaluate("mean([])")


def test_unsafe_constructs_rejected():
    for expr in [
        "__import__('os').system('true')",
        "(1).__class__",
        "[x for x in [1]]",
        "open('/etc/passwd')",
        "'a' + 'b'",
        "min(1, 2, key=abs)",
    ]:
        assert "error" in evaluate(expr), expr


def test_bad_variables_rejected():
    assert "error" in evaluate("x", {"x": "not-a-number"})
    assert "error" in evaluate("x", {"x": [1, "two"]})
    assert "error" in evaluate("x", {"x": True})


def test_non_finite_guard():
    assert "error" in evaluate("10.0 ** 400")
