"""Research Hub — shared in-memory knowledge graph + durable task board.

Exposed to Claude agents as a single long-running MCP server so that isolated
subagents share one live networkx graph and one SQLite-backed task queue.
"""

__version__ = "0.1.0"
