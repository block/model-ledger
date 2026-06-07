---
title: "ADR 0003 — Agents are the primary interface"
description: Design a small, consolidated, tool-shaped API for agents first; expose it identically over MCP, REST, and the SDK.
---

# ADR 0003 — Agents are the primary interface; the SDK is tool-shaped

**Status:** Accepted

## Context

Governance questions are conversational by nature — *"which high-risk models changed this
week and haven't been validated?"* The cheapest way to answer them is to let an agent
traverse the inventory directly. Most libraries treat an agent/MCP layer as an
afterthought wrapped around a human-shaped API, which produces awkward, chatty tools.

## Decision

Design the API for the agent first. The SDK is **tool-shaped**: each capability is one
consolidated verb — `discover`, `record`, `investigate`, `query`, `trace`, `changelog`,
`tag` — and the same verbs are exposed identically over MCP and REST. Tools follow
[Anthropic's tool-writing guidance](https://www.anthropic.com/engineering/writing-tools-for-agents):
few, broad, orthogonal, with agent-readable descriptions and error messages that name the
next action.

## Consequences

**Positive**

- One mental model across MCP, REST, SDK, and CLI; they can't drift because they share the
  tool functions.
- The consolidated surface is easier for a human to learn too — designing for the agent
  made the SDK cleaner as a side effect.
- Errors are actionable (they suggest the next call) rather than raising into the agent.

**Negative (accepted)**

- Broad verbs do more per call, which fits fine-grained REST conventions less neatly (no
  resource-per-endpoint sprawl).
- A small, opinionated verb set means some niche operations live only in the SDK.

## Alternatives considered

- **Human-first SDK with a thin MCP wrapper (rejected):** yields chatty, leaky tools and
  two surfaces that drift.
- **Granular REST endpoints mirrored to many tools (rejected):** overflows an agent's
  working memory and multiplies the maintenance surface.

See [Agents (MCP)](../guides/agents.md).
