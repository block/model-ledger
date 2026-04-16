# PRD: model-ledger (Main Surface)

**Charter**: [Project Charter](../../context/charter.md)
**Version**: 1.0.0
**Status**: Complete
**Created**: 2026-04-16

## Surface Overview

model-ledger is a cross-platform model inventory and governance framework. It discovers models across all platforms (ML registries, ETL schedulers, REST APIs, GitHub repos), maps dependency graphs via automatic port matching, tracks every change as an immutable content-addressed event, validates regulatory compliance (SR 11-7, EU AI Act, NIST AI RMF), and exposes everything through a tool-shaped API for AI agents (MCP), frontends (REST), scripts (Python SDK), and operators (CLI).

Unlike single-platform model registries (MLflow, SageMaker, W&B), model-ledger provides a unified, cross-platform view of every deployed model, its dependencies, governance status, and change history -- as one connected graph.

## Scope

### In Scope

- Model registration with content-addressed identity (ModelRef, Snapshot, Tag)
- Append-only event-log paradigm with immutable audit trail
- Dependency graph construction and traversal (add, connect, trace)
- Composite model governance (groups, members, automatic change propagation)
- 6 agent tools: record, query, investigate, trace, changelog, discover
- Three transport surfaces: MCP server, REST API, CLI
- 5 pluggable backends: InMemory, SQLite, Snowflake, HTTP pass-through, JSON files
- 4 source connectors: SQL, REST, GitHub, Prefect
- 3 regulatory compliance profiles: SR 11-7, EU AI Act, NIST AI RMF
- ML model introspection plugins (sklearn, xgboost, lightgbm)
- Audit pack export (HTML, JSON, Markdown)
- Observations, validation runs, and feedback lifecycle
- Scanner protocol for platform-level model discovery
- Plugin discovery via entry_points

### Out of Scope

- Model training / experiment tracking (MLflow/W&B territory)
- Real-time monitoring / alerting
- Automated remediation of findings
- Model serving / deployment
- Feature stores
- Data quality monitoring
- UI / dashboard frontend (REST API exists but no bundled frontend)
- Organization-specific connectors, auth, backends (separate companion packages)
- Model comparison / A/B testing

## Requirements

### Functional Requirements

1. **Model Registration**: Register models with content-addressed identity (ModelRef) via `record` tool or SDK `register()` method
2. **Event Recording**: Record arbitrary events (retrained, deployed, validated, etc.) as immutable Snapshots with schema-free payloads
3. **Dependency Graph**: Construct dependency graphs via DataNode input/output ports with automatic port matching (`connect()`)
4. **Composite Governance**: Aggregate technical components into business-level composite models with automatic member change propagation
5. **Multi-Platform Discovery**: Discover models from SQL databases, REST APIs, GitHub repos, and Prefect via connector factories
6. **Custom Connectors**: Support custom platform connectors via the `SourceConnector` protocol
7. **Dependency Tracing**: Trace upstream/downstream dependencies and perform impact analysis
8. **Changelog**: Query what changed across the inventory within a time range
9. **Point-in-Time Inventory**: Reconstruct inventory state at any historical timestamp
10. **Regulatory Validation**: Validate inventory against SR 11-7, EU AI Act, and NIST AI RMF compliance profiles
11. **Model Introspection**: Extract metadata from fitted sklearn, XGBoost, and LightGBM models via plugin system
12. **Audit Pack Export**: Export compliance documentation in HTML, JSON, and Markdown formats
13. **Observations and Validation**: Record observations, resolve them, and run validation checks against models

### Non-Functional Requirements

1. **Performance**: Support inventories of 10,000+ models without degradation in query or trace operations
2. **Auditability**: Every mutation produces an immutable, content-addressed Snapshot -- append-only, no updates or deletes
3. **Zero-Dependency Core**: Core SDK + SQLite backend require no external dependencies beyond stdlib
4. **Extensibility**: All extension points use `@runtime_checkable` Protocol + `importlib.metadata.entry_points()`
5. **Portability**: Storage-agnostic via LedgerBackend protocol -- swappable without code changes
6. **Licensing**: Apache-2.0, no organization-specific code in OSS repo
7. **API Consistency**: Same function signature across MCP, REST, CLI, and direct SDK import
8. **Backward Compatibility**: Point-in-time inventory reconstruction from any historical date

## Dependencies & Constraints

### Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| pydantic >= 2.0 | Core | Data validation, serialization, tool I/O schemas |
| httpx >= 0.28.1 | Core | HTTP client for REST connector and HTTP backend |
| FastMCP (mcp >= 1.7.1) | Optional | MCP server for AI agent interface |
| FastAPI >= 0.115 | Optional | REST API server |
| uvicorn >= 0.30 | Optional | ASGI server for REST API |
| snowflake-connector-python >= 3.0 | Optional | Snowflake backend |
| typer >= 0.9 | Optional | CLI interface |
| rich >= 13.0 | Optional | CLI formatting |
| scikit-learn, xgboost, lightgbm | Optional | Model introspection plugins |

### Constraints

1. **Apache-2.0 License**: All code must be generic and useful to any organization
2. **Boundary Rule**: Organization-specific connectors, auth, and backends must live in separate companion packages
3. **Generic Examples**: All examples in code, tests, and docstrings must use generic names
4. **Backward Compatibility**: Event-log paradigm (v0.3.0+) is the foundation -- all new features build on ModelRef/Snapshot/Tag
5. **No UI Bundled**: The framework provides API surfaces only -- frontends are built by consumers

## Milestones & Timeline

| Milestone | Version | Theme | Status |
|-----------|---------|-------|--------|
| Event-log paradigm | v0.3.0 | ModelRef, Snapshot, Scanner protocol | Complete |
| DataNode graph | v0.4.0 | Connectors, DataPort, auto-connect | Complete |
| Governed groups | v0.5.0 | Model groups, OSS boundary, SQL enhancements | Complete |
| Agent-first protocol | v0.6.0 | MCP server, REST API, 6 tools, JSON backend | Complete |
| Production backends | v0.7.x | Snowflake, HTTP pass-through, change tracking, Prefect | Complete |
| Composite governance | v0.8.0 | Members, propagation, observations, composite_summary | In Progress |
| Production hardening | v0.9.0 | Performance at scale, Snowflake optimizations | Planned |
| Stable release | v1.0.0 | Stable API, comprehensive regulatory coverage, external adoption | Planned |

## Assumptions & Risks

| ID | Assumption | Risk if Wrong |
|----|------------|---------------|
| A1 | Event-log paradigm scales to 10K+ models without bottlenecks | Performance failures force architectural rework |
| A2 | Composite governance (v0.8.0) stabilizes within 1-2 release cycles | Delays push v1.0 further out |
| A3 | External organizations will adopt an Apache-2.0 model inventory | OSS stays internal-only with no community |
| A4 | MCP/agent interface becomes the primary interaction mode | CLI/SDK must carry the product if agents don't mature |
