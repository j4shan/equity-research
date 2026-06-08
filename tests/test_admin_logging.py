"""Tests for the runtime tracing/logging control on the MCP server."""

import os
import tempfile

# Point server state at throwaway paths before importing it (import has side effects).
os.environ.setdefault("RESEARCH_HUB_DB", os.path.join(tempfile.mkdtemp(), "tb.db"))
os.environ.setdefault("RESEARCH_HUB_ASSETS_DIR", tempfile.mkdtemp())

from research_hub import server  # noqa: E402


def test_logging_defaults_to_off():
    server.admin_set_logging("off")  # normalize in case other tests ran first
    state = server.admin_get_logging()
    assert state["logging_level"] == "off"
    assert state["tracing_enabled"] is False


def test_toggle_reports_previous_and_restores():
    server.admin_set_logging("off")
    res = server.admin_set_logging("info")
    assert res["previous"] == "off"
    assert res["current"] == "info"
    assert res["tracing_enabled"] is True
    assert server.admin_get_logging()["tracing_enabled"] is True
    # restore
    back = server.admin_set_logging("off")
    assert back["previous"] == "info" and back["current"] == "off"
    assert server.admin_get_logging()["tracing_enabled"] is False


def test_invalid_level_rejected():
    res = server.admin_set_logging("verbose")
    assert "error" in res
    # state unchanged
    assert server.admin_get_logging()["logging_level"] in server.admin_get_logging()["levels"]
