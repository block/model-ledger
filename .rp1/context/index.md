# model-ledger - Knowledge Base

**Type**: Single Project
**Languages**: Python
**Version**: 0.7.2+
**Updated**: 2026-04-16

## Project Summary

model-ledger is an open-source (Apache-2.0) model inventory and governance framework for ML model lifecycle tracking. It provides an event-sourced, append-only audit trail for model registration, change detection, dependency tracing, and regulatory compliance validation (SR 11-7, EU AI Act, NIST AI RMF), exposed through a tool-shaped API for AI agent integration via MCP, REST, and CLI.

## Quick Reference

| Aspect | Value |
|--------|-------|
| Entry Point | `src/model_ledger/sdk/ledger.py` (Ledger class) |
| Key Pattern | Event-sourced append-only log with content-addressed snapshots |
| Tech Stack | Python 3.10+, Pydantic, FastMCP, FastAPI, Typer, SQLite/Snowflake |

## KB File Manifest

**Progressive Loading**: Load files on-demand based on your task.

| File | Lines | Load For |
|------|-------|----------|
| architecture.md | ~200 | System design, layer interactions, data flows, deployment |
| modules.md | ~167 | Component breakdown, module responsibilities, dependency graph |
| patterns.md | ~66 | Code conventions, naming, error handling, testing idioms |
| concept_map.md | ~123 | Domain terminology, MRM concepts, entity relationships |

## Task-Based Loading

| Task | Files to Load |
|------|---------------|
| Code review | `patterns.md` |
| Bug investigation | `architecture.md`, `modules.md` |
| Feature implementation | `modules.md`, `patterns.md` |
| Strategic analysis | ALL files |

## How to Load

```
Read: .rp1/context/{filename}
```

## Project Structure

```
src/model_ledger/
├── core/           # Domain models (ModelRef, Snapshot, Tag, enums, exceptions)
├── sdk/            # Ledger + Inventory SDKs (business logic)
├── tools/          # 6 agent tool functions + Pydantic I/O schemas
├── backends/       # 5 storage backends (SQLite, Snowflake, HTTP, JSON, Memory)
├── connectors/     # 4 source connectors (SQL, REST, GitHub, Prefect)
├── graph/          # DataNode/DataPort graph primitives
├── mcp/            # FastMCP server (6 tools + 3 resources)
├── rest/           # FastAPI REST API
├── scanner/        # Platform scanner framework
├── validate/       # SR 11-7, EU AI Act, NIST AI RMF profiles
├── introspect/     # ML model metadata extraction (sklearn, xgboost, lightgbm)
├── adapters/       # SQL parsing, table discovery, cron translation
├── export/         # Audit pack export (HTML/JSON/Markdown)
├── cli/            # Typer CLI
└── datasets/       # Demo/sample data
```

## Navigation

- **[architecture.md](architecture.md)**: System design, layer diagram, data flows, deployment
- **[modules.md](modules.md)**: 14 modules, 37 components, dependency graph
- **[patterns.md](patterns.md)**: Naming, types, errors, testing, extension mechanisms
- **[concept_map.md](concept_map.md)**: MRM domain concepts, terminology, boundaries
