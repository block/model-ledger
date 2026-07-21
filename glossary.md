---
title: Glossary
description: The vocabulary of model-ledger — DataNode, Snapshot, ModelRef, Composite, and the rest, in one place.
---

# Glossary

The whole system is a handful of nouns. (These terms also get hover-definitions
wherever they appear in the docs.)

`Backend`
:   Pluggable storage behind the `LedgerBackend` protocol — in-memory, SQLite, JSON
    files, Snowflake, or a remote HTTP service. Swapping it never changes your code.

`Composite`
:   A governed group whose members are themselves models — a business-level entity (e.g.
    a "Credit Decision System") that rolls up its scorecard, rules, and ETL. See
    [Composites](concepts/composite.md).

`Connector`
:   A source that emits `DataNode`s from a platform (SQL, REST, GitHub, …) via the
    `SourceConnector` protocol. See [Connectors & discovery](guides/connectors.md).

`DataNode`
:   The core graph primitive: anything with typed input/output ports — an ML model, a
    heuristic rule, an ETL job, an alert queue. See [DataNode & the graph](concepts/datanode.md).

`DataPort`
:   A named connection point on a `DataNode`, optionally carrying schema so identically
    named outputs from different models don't falsely link.

`Dependency graph`
:   The links between nodes, built automatically when an output port name matches an
    input port name (`connect()`).

`Event log`
:   The inventory itself — an append-only sequence of immutable Snapshots. Nothing is
    overwritten, so history is always reconstructable.

`ModelRef`
:   A model's stable identity: name, owner, type, risk `tier`, purpose, status. The
    minimum a regulator needs. See [Snapshots & the event log](concepts/snapshot.md).

`Point-in-time`
:   Reconstruction of the inventory as it stood on any past date, via `inventory_at()`.

`Profile`
:   A pluggable compliance check (`sr_11_7`, `eu_ai_act`, `nist_ai_rmf`) that validates a
    model's completeness against a framework. See [Governance](governance.md).

`Snapshot`
:   An immutable, content-addressed record of one thing that happened to a model — a
    registration, a retrain, a validation. The unit of the event log.

`Tag`
:   A mutable named pointer to a specific Snapshot (e.g. `production`, `latest-validated`).
