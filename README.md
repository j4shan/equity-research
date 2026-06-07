# Equity Research

An AI-powered equity research skill using multi-agent workflows to collate company information into structured research reports and knowledge graphs.

## Overview

This project leverages:
- **Multi-agent workflows** — specialized agents for data gathering, analysis, and report synthesis
- **Financial Hub MCP** — market data, filings, and fundamentals via MCP tools
- **Knowledge graphs** — structured company and sector relationship graphs
- **Research reports** — automated generation of equity research notes

## Architecture

```
equity_research/
├── agents/          # Specialized research agents
├── mcp/             # MCP server configs and tool definitions
├── reports/         # Generated research report outputs
├── data/            # Processed/structured data (raw/ is gitignored)
└── knowledge_graph/ # Company and sector graph definitions
```

## Getting Started

```bash
# Set up Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure MCP (copy and fill in credentials)
cp mcp/config.example.json mcp/config.json
```

## Usage

Research reports and knowledge graphs are generated via Claude Code skills using multi-agent orchestration with Financial Hub MCP for live market data.
