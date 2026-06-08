# Data Tool Cheatsheet — Massive & Alpha Vantage

Financial data comes from two MCP servers, both connected at the **claude.ai
level** (no API keys, no OAuth, no `.mcp.json` entry). If a server's tools are
missing, reconnect the connector in claude.ai settings.

## The two providers

- **Alpha Vantage** — one tool per signal, called directly by name. In this
  environment tools appear as `mcp__claude_ai_Alpha_Vantage__<TOOL>` (e.g.
  `mcp__claude_ai_Alpha_Vantage__COMPANY_OVERVIEW`). **First choice for
  company-level signals** (fundamentals, indicators, news, insiders). Uses plain
  US symbols like `AAPL` — no exchange suffix.
- **Massive** — a discovery-based REST gateway with **4 meta-tools**
  (`mcp__claude_ai_Massive__*`): `search_endpoints` (natural-language endpoint
  discovery; use `detail="more"` for params) → `call_api` (fetch; pass
  `store_as` to save a table and get a `workspace` handle) → `query_data` (SQL
  over stored tables) → `workspace`. **First choice for screening, bulk /
  cross-sectional work, market microstructure, and anything Alpha Vantage
  lacks.** Prefer `store_as` + `query_data` over pulling large payloads into
  context.

## Signal → tool map

### Fundamentals (Alpha Vantage)
| Need | Tool |
|---|---|
| Company profile, sector/industry, valuation ratios | `COMPANY_OVERVIEW` |
| Income statement / balance sheet / cash flow | `INCOME_STATEMENT`, `BALANCE_SHEET`, `CASH_FLOW` |
| Earnings history & estimates | `EARNINGS`, `EARNINGS_ESTIMATES`, `EARNINGS_CALL_TRANSCRIPT` |
| Dividends / splits | `DIVIDENDS`, `SPLITS` |
| Bulk peer fundamentals / cross-sectional comparison | **Massive** (`call_api` → `store_as` → `query_data`) |

### Technical (Alpha Vantage)
| Need | Tool |
|---|---|
| Historical OHLCV (split/dividend-adjusted) | `TIME_SERIES_DAILY_ADJUSTED` |
| Intraday bars | `TIME_SERIES_INTRADAY` |
| Latest price quote | `GLOBAL_QUOTE` |
| SMA / EMA / RSI / MACD / BBANDS / ADX / ATR / OBV / STOCH / VWAP | one tool each, same names |
| Support / resistance | **no direct tool** — compute classic pivots from recent high/low/close via `calc_evaluate` (or Massive analytics functions) |

### Sentiment (Alpha Vantage)
| Need | Tool |
|---|---|
| News articles + polarity + topics (one call) | `NEWS_SENTIMENT` |
| Insider buys/sells | `INSIDER_TRANSACTIONS` |
| Smart-money positioning | `INSTITUTIONAL_HOLDINGS` |
| Options-market sentiment | `HISTORICAL_PUT_CALL_RATIO`, `REALTIME_PUT_CALL_RATIO` |

> `NEWS_SENTIMENT` returns articles, per-article polarity, and topic tags in a
> single call — it replaces the old separate news / sentiment / word-weight tools.

### Relationships / peer discovery
| Need | Tool |
|---|---|
| Resolve name → symbol | `SYMBOL_SEARCH` (Alpha Vantage) |
| Sector/industry of a company | `COMPANY_OVERVIEW` (Alpha Vantage) |
| Find peers by sector/industry/market-cap | **Massive** (reference/related-companies endpoints, or a SQL screen over a stored table) |
| Index / ETF constituents (peer basket) | `ETF_PROFILE`, `INDEX_CATALOG`, `INDEX_DATA` (Alpha Vantage) |
| Co-mentioned companies | `NEWS_SENTIMENT` (Alpha Vantage) |

### Macro (context, Alpha Vantage)
`CPI`, `REAL_GDP`, `TREASURY_YIELD`, `FEDERAL_FUNDS_RATE`, `UNEMPLOYMENT`,
`INFLATION`, plus calendars `EARNINGS_CALENDAR`, `IPO_CALENDAR`, `MARKET_STATUS`.

## Conventions & etiquette
- Symbols are plain (`AAPL`, `NVDA`); use `SYMBOL_SEARCH` when unsure.
- Be economical — Alpha Vantage is rate-limited. Request only what the analysis
  needs, and reach for Massive `store_as` + `query_data` for anything bulk rather
  than pulling large payloads into context.
- Distill results into the run folder; never dump raw payloads into the graph.
- Provenance strings use `alpha_vantage:<TOOL>` or `massive:<endpoint>`.
