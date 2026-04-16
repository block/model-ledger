# Project Charter: model-ledger

**Version**: 1.0.0
**Status**: Complete
**Created**: 2026-04-16

### Problem & Context

Financial institutions operate hundreds to thousands of ML models and rules-based systems across 10+ platforms, yet typically track only a fraction in any formal inventory. Regulatory mandates — SR 11-7, EU AI Act (enforcement August 2026), OSFI E-23, PRA SS1/23 — require comprehensive, auditable model inventories with full lineage and change trails.

Existing model registries (MLflow, SageMaker, Weights & Biases) are single-platform silos. They track what was trained in their environment but cannot provide a unified, cross-platform view of every deployed model, its dependencies, or its governance status. The result: MRM teams resort to spreadsheets, coverage gaps go undetected, and regulatory audits surface material findings.

**Why now**: Regulatory frameworks like SR 11-7 and the EU AI Act are raising the bar for model governance. Organizations increasingly need a solution that can discover and govern models across all platforms — this is a growing industry need, not a single-deadline event.

### Target Users

| Segment | Role | Primary Need |
|---------|------|--------------|
| Model Risk Management (MRM) teams | Govern and inventory all models | Complete, living inventory satisfying regulatory requirements |
| ML Engineers | Build and deploy models | Discover dependencies, trace impact of changes, understand lineage |
| AI Agents (via MCP) | Query inventory conversationally | Tool-shaped API for natural-language governance queries |
| Regulators / Auditors | Examine compliance posture | Audit trails, compliance documentation, coverage reports |

### Business Rationale

model-ledger is the missing governance layer that sits above platform-specific registries and provides a unified, cross-platform model inventory.

**Core value delivered**:
1. **Unified discovery**: Discovers models across all platforms as one connected graph, eliminating blind spots from platform silos
2. **Immutable audit trail**: Every change is tracked as a content-addressed, append-only event — satisfying regulatory auditability requirements
3. **Dependency mapping**: Maps upstream/downstream dependencies so teams can trace the blast radius of any change
4. **Regulatory compliance**: Validates inventory against SR 11-7, EU AI Act, and NIST AI RMF compliance profiles out of the box
5. **Agent-native interface**: Exposes everything through a tool-shaped API (MCP, REST, CLI) so AI agents can query and manage the inventory conversationally
6. **Composite governance**: Aggregates technical components into business-level composite models, letting regulators examine governable entities rather than raw artifacts

**Differentiation**: Unlike MLflow/SageMaker/W&B (single-platform training registries), model-ledger is a cross-platform governance framework. Unlike GRC tools, it is code-native, event-sourced, and agent-accessible. Apache-2.0 licensing enables adoption without vendor lock-in.

### Scope Guardrails

**In Scope (v0.7.x)**:
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

**Out of Scope (by design)**:
- Model training / experiment tracking (MLflow/W&B territory)
- Real-time monitoring / alerting
- Automated remediation of findings
- Model serving / deployment
- Feature stores
- Data quality monitoring
- UI / dashboard frontend (REST API exists but no bundled frontend)
- Organization-specific connectors, auth, backends (separate companion packages)
- Model comparison / A/B testing

### Success Criteria

**Success looks like**:
1. **Regulatory readiness**: Model inventory is comprehensive enough to satisfy SR 11-7 and EU AI Act (August 2026 deadline) audit requirements — complete coverage of deployed models with audit trails
2. **Coverage at scale**: Organizations move from partial tracking (~15%) to >90% coverage across all platforms
3. **OSS adoption**: External organizations (banks, fintechs) adopt model-ledger as their model inventory solution — evidenced by PyPI downloads, GitHub stars, and external contributions
4. **Agent-native usage**: AI agents (via MCP) become the primary interface for querying and managing the inventory — model governance becomes conversational
5. **Composite governance**: Business-level composites successfully aggregate thousands of technical nodes with automatic change propagation, enabling regulators to examine governable entities

**Failure looks like**:
- Regulatory audit finds significant gaps in model inventory coverage
- Framework is too complex for MRM teams to adopt — they fall back to spreadsheets
- OSS project stays internal-only with no external adoption
- Event-log paradigm creates performance bottlenecks at scale (>10K models)
