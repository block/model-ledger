---
title: "ADR 0002 — Everything is a DataNode"
description: Represent models, rules, ETL, and queues with one typed-port node, and let the dependency graph assemble itself from port matching.
---

# ADR 0002 — Everything is a DataNode; the graph builds itself

**Status:** Accepted

## Context

A real model estate spans ML models, heuristic rules, ETL jobs, and alert queues, across
many platforms with no shared identifier scheme. To map dependencies, most tools require
either a central registry of IDs or per-platform adapters that understand each other.
Both are brittle and don't scale across platforms.

## Decision

Every entity is a single type — `DataNode` — with typed input and output **ports**. A
node declares only what it consumes and produces. `connect()` then creates a dependency
edge wherever an output port name matches an input port name. Connectors emit nodes and
know nothing about the rest of the graph.

`DataPort` carries optional schema discriminators (e.g. `model_name`) so that two nodes
writing a same-named table do not falsely link.

## Consequences

**Positive**

- Cross-platform edges (warehouse ETL → MLflow model → alerting queue) form with no shared
  ID scheme and no inter-connector coupling.
- Adding a platform is "emit `DataNode`s" — connectors stay dumb and independent, which is
  what makes discovery scale.
- One abstraction to learn; rules and ETL are first-class, not second-class to ML models.

**Negative (accepted)**

- Port-name collisions are possible; resolving them precisely requires `DataPort` schema
  discriminators rather than bare strings.
- Port naming becomes a modeling concern the connector author must get right.

## Alternatives considered

- **Per-platform model types (rejected):** too rigid; every new platform is a new type and
  new cross-type wiring.
- **A fixed, central metadata schema (rejected):** cannot span heterogeneous platforms;
  forces lossy normalization at discovery time.

See [DataNode & the graph](../concepts/datanode.md).
