---
title: Design decisions
description: Architecture Decision Records — the load-bearing choices behind model-ledger, the alternatives weighed, and the costs accepted.
---

# Design decisions

Architecture Decision Records (ADRs) capture the choices that shape model-ledger: the
context, the decision, the alternatives considered, and the consequences — including the
costs accepted on purpose. They are short, dated, and immutable; a reversed decision gets
a new ADR that supersedes the old one rather than an edit.

| # | Decision | Status |
|---|---|---|
| [0001](0001-event-log-not-a-registry.md) | Model the inventory as an event log, not a registry | Accepted |
| [0002](0002-everything-is-a-datanode.md) | Everything is a DataNode; the graph builds itself | Accepted |
| [0003](0003-agents-first.md) | Agents are the primary interface; the SDK is tool-shaped | Accepted |
| [0004](0004-framework-agnostic.md) | Framework-agnostic core; regulations are pluggable profiles | Accepted |
| [0005](0005-storage-agnostic.md) | Storage-agnostic via the LedgerBackend protocol | Accepted |
| [0006](0006-discovery-and-validation-subsystems.md) | Discovery and validation are two subsystems; bridge, don't delete | Accepted |

The narrative that ties these together is the [Architecture](../concepts/architecture.md) page.
