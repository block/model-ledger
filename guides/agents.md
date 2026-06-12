---
title: Agents (MCP)
description: The MCP server is the product. Eight tools and three resources let any agent explore, register, and reason about your model inventory.
---

# Agents (MCP)

model-ledger is built agents-first. The Python SDK and REST API are first-class, but
the surface we optimize for is the **MCP server** — because the most natural way to
ask *"which high-risk models changed this week and haven't been validated?"* is to
just ask.

## Connect it

```bash
pip install "model-ledger[mcp]"

# Claude Code (one time). Drop --demo to start empty; add a backend to persist.
claude mcp add model-ledger -- model-ledger mcp --demo
claude mcp add model-ledger -- model-ledger mcp --backend sqlite --path ./inventory.db
```

The server speaks stdio and works with any MCP client (Claude Desktop, Goose, Cursor).
Point it at a remote deployment with `--backend http --path https://your-ledger:8000`,
and the tools call that REST API directly.

## The eight tools

Each tool is a plain function with Pydantic I/O, designed per
[Anthropic's tool-writing guidance](https://www.anthropic.com/engineering/writing-tools-for-agents) —
consolidated verbs, not a sprawl of endpoints.

| Tool | What the agent uses it for |
|------|----------------------------|
| **`discover`** | Bulk-import models from inline dicts or a JSON file |
| **`record`** | Register a model (`event="registered"`) or append any event to its history |
| **`investigate`** | Deep-dive one model — identity, recent events, upstream/downstream deps, group memberships |
| **`query`** | Search & filter the inventory (text + `platform`/`model_type`/`owner`/`status`, paginated) |
| **`trace`** | Walk the dependency graph — `upstream`, `downstream`, or `both` |
| **`changelog`** | What changed across the whole inventory in a time range (defaults to last 7 days) |
| **`tag`** | Create or move a named pointer (`production`, `latest-validated`) to a model's latest snapshot |
| **`list_tags`** | List the tags on a model |

And three **resources** — read-only orientation an agent can pull without a tool call:

| Resource | Contents |
|----------|----------|
| `ledger://overview` | Model count, event count, type breakdown |
| `ledger://schema` | JSON Schema for every tool's I/O — the agent learns the contract |
| `ledger://backends` | Which backend is active |

## A worked conversation

What a multi-tool exchange actually looks like under the hood:

> **You:** Anything risky change this week?

```json
// changelog(since="2026-06-01")
{ "events": [
  {"model_name": "fraud_scoring", "event_type": "retrained", "timestamp": "2026-06-03T14:11Z"},
  {"model_name": "aml_threshold_rule", "event_type": "threshold_changed", "timestamp": "2026-06-04T09:02Z"}
], "total": 2 }
```

> **Claude:** Two changes. `fraud_scoring` was retrained, and `aml_threshold_rule`'s
> threshold changed. Want the blast radius of either?
>
> **You:** The threshold rule — what depends on it?

```json
// trace(name="aml_threshold_rule", direction="downstream")
{ "nodes": [
  {"name": "sar_queue", "depth": 1, "relationship": "depends_on"},
  {"name": "compliance_dashboard", "depth": 2, "relationship": "depends_on"}
] }
```

> **Claude:** It feeds `sar_queue` directly and `compliance_dashboard` one hop further.
> Let me check whether the rule has been validated since the change.

```json
// investigate(model_name="aml_threshold_rule", detail="full")
{ "owner": "compliance-eng", "model_type": "heuristic", "tier": "high",
  "recent_events": [{"event_type": "threshold_changed", "actor": "j.lee"}],
  "validations": [] }
```

> **Claude:** ⚠️ `aml_threshold_rule` is tier **high**, changed yesterday by `j.lee`,
> feeds the SAR queue — and has **no validation recorded since the change**. Worth
> flagging to MRM.

That chain — `changelog → trace → investigate` — is the whole point: the agent reasons
over the event log, not a static table.

## Discovering at scale

The `discover` tool imports inline model lists, a JSON file, or a config-drivable connector:

```json
// discover(source_type="inline", models=[{"name": "...", "platform": "..."}])
{ "added": 12, "skipped": 0, "links_created": 8 }

// discover(source_type="connector", connector_name="rest",
//          connector_config={"name": "mlflow", "url": "...", "items_path": "...", "name_field": "..."})
{ "models_added": 40, "links_created": 12, "errors": [] }
```

!!! info "Which connectors an agent can run"
    `rest` and `prefect` are pure-config connectors, so an agent can run them directly
    through `discover`. `sql` and `github` need a live database connection or a parser
    callable that can't be expressed as JSON — for those, `discover` returns a message in
    the result's `errors` field pointing you to the SDK (see
    [Connectors & discovery](connectors.md)). Connector problems come back as `errors`
    rather than raising, so the agent always gets a usable response.

## Your docs are an agent surface, too

These docs publish [`/llms.txt`](../llms.txt) and [`/llms-full.txt`](../llms-full.txt),
and every page is fetchable as raw Markdown by appending `.md` to its path. Point an
IDE agent at them and it learns model-ledger without leaving the editor — fitting for a
tool whose product is an MCP server.
