---
title: Installation
description: Install model-ledger and just the extras you need — SDK core is tiny; surfaces and backends are opt-in.
---

# Installation

model-ledger requires **Python 3.10+**. The core is deliberately tiny (`httpx` +
`pydantic` only); everything else is an opt-in extra, so you install just the surfaces
and backends you use.

```bash
pip install model-ledger          # core: SDK + dependency graph + connectors
# or
uv add model-ledger
```

## Extras

| Install | Adds | For |
|---|---|---|
| `model-ledger` | SDK, graph, SQL/REST/GitHub connectors | the core library |
| `model-ledger[mcp]` | MCP server (`model-ledger mcp`) | AI agents — Claude, Goose, Cursor |
| `model-ledger[rest-api]` | FastAPI app (`model-ledger serve`) | frontends, dashboards |
| `model-ledger[cli]` | Typer + Rich CLI | terminal use |
| `model-ledger[snowflake]` | Snowflake backend | production storage |
| `model-ledger[introspect-sklearn]` | scikit-learn introspector | extract algorithm/features from fitted models |
| `model-ledger[introspect-xgboost]` | XGBoost introspector | " |
| `model-ledger[introspect-lightgbm]` | LightGBM introspector | " |
| `model-ledger[excel]` | openpyxl | spreadsheet import/export |
| `model-ledger[all]` | Snowflake + pandas + httpx | the common production set |

Combine them: `pip install "model-ledger[mcp,rest-api,snowflake]"`.

## Which extra for which surface

- **Python SDK** — core install is enough.
- **Talk to it from an agent** — `[mcp]`, then `claude mcp add model-ledger -- model-ledger mcp` (see the [Agent guide](guides/agents.md)).
- **Serve it over HTTP** — `[rest-api]`, then `model-ledger serve` (see [Backends](guides/backends.md)).
- **From the terminal** — `[cli]` (see the [CLI guide](guides/cli.md)).

Next: the [60-second quickstart](quickstart.md).
