# MCP Setup Guide

The project uses **three MCP servers**:

| Server | Type | Purpose | Auth |
|--------|------|---------|------|
| `research_hub` | local **stdio** (`.venv` Python) | shared in-memory knowledge graph + durable task board | none (local) |
| `Massive` | **claude.ai connector** | market data gateway (discover → call → SQL) | managed by claude.ai |
| `Alpha Vantage` | **claude.ai connector** | fundamentals, indicators, news, insiders, macro | managed by claude.ai |

Only `research_hub` is declared in the repo's [`.mcp.json`](../.mcp.json). **Massive**
and **Alpha Vantage** are connected once at the **claude.ai** level (Settings →
Connectors); they need no `.mcp.json` entry, no `claude mcp add`, and no API keys in
this repo.

---

## Prerequisites

```bash
cd /Users/michaelsj/Documents/Workspace/equity_research
uv pip install -r requirements.txt --python .venv   # research_hub deps (mcp, networkx, …)
```

Sanity-check the local server starts and registers its tools:

```bash
.venv/bin/python -c "import asyncio; from research_hub import server; \
print(len(asyncio.run(server.mcp.list_tools())), 'tools')"   # → 26 tools
```

---

## The local `research_hub` server

Declared in `.mcp.json` and auto-detected when you open the project in Claude Code.
On first use, approve the project's MCP server when prompted. Verify:

```
/mcp        # research_hub → connected, with graph_*/workflow_*/calc_evaluate/plan_toposort tools
```

If auto-detect misses it (e.g. running outside the repo root), add it with absolute
paths:

```bash
claude mcp add-json research_hub --scope project '{
  "type": "stdio",
  "command": "/Users/michaelsj/Documents/Workspace/equity_research/.venv/bin/python",
  "args": ["-m", "research_hub.server"],
  "cwd": "/Users/michaelsj/Documents/Workspace/equity_research",
  "env": {
    "PYTHONPATH": "/Users/michaelsj/Documents/Workspace/equity_research",
    "RESEARCH_HUB_ASSETS_DIR": "/Users/michaelsj/Documents/Workspace/equity_research_assets"
  }
}'
```

---

## The data connectors (Massive & Alpha Vantage)

These are connected in **claude.ai** (Settings → Connectors), not in this repo. Once
connected, their tools are available to the session and subagents as
`mcp__claude_ai_Massive__*` and `mcp__claude_ai_Alpha_Vantage__*`. Verify with a
cheap call:

```
Alpha Vantage:  mcp__claude_ai_Alpha_Vantage__MARKET_STATUS   (or PING → "pong")
Massive:        mcp__claude_ai_Massive__search_endpoints("daily aggregates")
```

---

## Deploy the subagents (one-time)

The analysts/manager/reviewer must be installed to `~/.claude/agents/`:

```bash
bash scripts/deploy_agents.sh        # symlink (live-edits); --copy to copy; --uninstall to remove
```

---

## Verify end-to-end

In a Claude Code session at the repo root:

1. `/mcp` → `research_hub` is **connected**.
2. Ask Claude to call `graph_stats` (research_hub) → `{"nodes": …, "edges": …}`.
3. Ask Claude to call `plan_toposort({"a": [], "b": ["a"]})` → `waves: [["a"], ["b"]]`.
4. Confirm a data tool responds: `SYMBOL_SEARCH` for "Apple" → `AAPL`.

---

## Configuration reference (`research_hub` env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `RESEARCH_HUB_ASSETS_DIR` | `../equity_research_assets` (from the package location) | assets repo root |
| `RESEARCH_HUB_DB` | `<assets>/.research_hub/taskboard.db` | durable task board |
| `RESEARCH_HUB_SNAPSHOT` | `<assets>/graph_snapshots/latest.graphml` | graph snapshot reloaded on startup |

The server computes sensible defaults from its own file location, so the env vars
are optional overrides.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `research_hub` fails to start; `ModuleNotFoundError: research_hub` | Launched from the wrong directory. Ensure `cwd` **and/or** `PYTHONPATH` is the repo root. |
| `research_hub` fails to start with `ENOENT` | `.mcp.json` uses `${HOME}`-based paths; ensure `.venv/bin/python` exists (re-run the `uv pip install`). Avoid the VS Code-only `${workspaceFolder}` variable. |
| `research_hub` python not found | Re-run `uv pip install -r requirements.txt --python .venv`; confirm `.venv/bin/python` exists. |
| Alpha Vantage / Massive tools missing | Reconnect the connector in **claude.ai → Settings → Connectors**, then retry. |
| Alpha Vantage tool calls return a rate-limit error | Be economical; batch/bulk work belongs on Massive (`store_as` + `query_data`). |
| `research_hub` server not detected | Confirm you opened the folder containing `.mcp.json`; check `claude mcp list`. |
