---
title: "ADR 0005 — Storage-agnostic backends"
description: Put all persistence behind one LedgerBackend protocol so the same code runs from in-memory to Snowflake.
---

# ADR 0005 — Storage-agnostic via the LedgerBackend protocol

**Status:** Accepted

## Context

The same inventory needs to run as a throwaway in-memory object in a test, a single
SQLite file on a laptop, git-friendly JSON in a repo, a Snowflake schema in production,
and a thin client against a remote HTTP service. Coupling the SDK to any one of these
would force a rewrite to change storage and make testing slow.

## Decision

All persistence sits behind a single `@runtime_checkable` `LedgerBackend` protocol. The
`Ledger` SDK is written against the protocol only; the backend is a constructor argument
(`Ledger.from_sqlite(...)`, `Ledger.from_snowflake(...)`, `Ledger(JsonFileLedgerBackend(...))`,
`Ledger(HttpLedgerBackend(...))`). Third parties can add backends (e.g. Postgres) by
implementing the protocol and registering an entry point — no core change.

## Consequences

**Positive**

- Choosing storage is a one-line decision that never leaks into application code.
- Tests run in-memory and fast; the same code path is exercised against every backend.
- Backends are an open extension point, not a closed enum.

**Negative (accepted)**

- The protocol is a contract: adding a method means implementing it across every backend
  (and any third-party one), so the surface must evolve deliberately. The HTTP backend in
  particular can't always reconstruct server-side state locally and falls back to caches.
- The lowest-common-denominator protocol can't expose every backend's native superpowers.

## Alternatives considered

- **Hard-code one backend (rejected):** forces a rewrite to change storage and makes tests
  depend on infrastructure.
- **An ORM abstraction (rejected):** heavier, leakier, and a poor fit for the append-only
  event-log and the non-SQL backends (JSON files, HTTP).

See [Choosing a backend](../guides/backends.md).
