---
title: API Reference
description: The public API, generated directly from the source docstrings — it can never drift from the installed version.
---

# API Reference

Everything below is generated from the source at build time with
[mkdocstrings](https://mkdocstrings.github.io/) + [Griffe](https://mkdocstrings.github.io/griffe/).
It reflects the exact installed version — there is no hand-maintained copy to fall out
of date.

## Ledger

The one object you'll use most. Every method is tool-shaped — usable directly, over
REST, or as an MCP tool.

::: model_ledger.Ledger
    options:
      show_root_heading: false
      heading_level: 3

## Data models

The event-log primitives. A model is a `ModelRef`; every change is a `Snapshot`; a
`Tag` is a mutable pointer.

::: model_ledger.ModelRef
    options:
      heading_level: 3
::: model_ledger.Snapshot
    options:
      heading_level: 3
::: model_ledger.Tag
    options:
      heading_level: 3

## Graph

::: model_ledger.DataNode
    options:
      heading_level: 3
::: model_ledger.DataPort
    options:
      heading_level: 3

## Connectors

Factory functions that emit `DataNode`s from external sources. See
[Connectors & discovery](../guides/connectors.md) for usage.

::: model_ledger.sql_connector
    options:
      heading_level: 3
::: model_ledger.rest_connector
    options:
      heading_level: 3
::: model_ledger.github_connector
    options:
      heading_level: 3

## Introspection

::: model_ledger.introspect
    options:
      heading_level: 3
::: model_ledger.register_introspector
    options:
      heading_level: 3
