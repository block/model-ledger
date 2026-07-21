---
title: "ADR 0004 — Framework-agnostic core, pluggable profiles"
description: Keep regulations out of the core; express them as a pluggable compliance-profile layer over a generic inventory.
---

# ADR 0004 — Framework-agnostic core; regulations are pluggable profiles

**Status:** Accepted

## Context

model-ledger's demand is driven by regulation (SR 26‑2, EU AI Act Annex IV, NIST AI RMF,
ISO 42001). The tempting move is to build "an SR 11‑7 tool." But specific regulations get
renumbered and superseded (SR 11‑7 → SR 26‑2 in 2026), differ by jurisdiction, and would
narrow a tool that is genuinely general.

## Decision

The core is a generic model inventory with **no regulation baked in**. Specific frameworks
are expressed as **compliance profiles** — a plugin layer (`sr_11_7`, `eu_ai_act`,
`nist_ai_rmf`) discovered via entry points, checking a model's completeness against a
framework's expectations. The documentation leads with the durable capability (complete,
auditable, point-in-time inventory) and treats named regimes as a thin, current layer.

## Consequences

**Positive**

- A renumbered or new regulation is a profile change, not a core change — the inventory is
  never stale on a regulator's letter.
- The tool serves any organization with deployed models, not one jurisdiction's banks.
- The core stays tiny (`httpx` + `pydantic`), which is what lets downstream packages add
  org-specific connectors, auth, and profiles without forking it.

**Negative (accepted)**

- `record()` takes a schema-free `payload`; envelope validation is the caller's or a
  profile's responsibility, not the core's.
- "Does it support regulation X?" is answered by "is there a profile?", which requires the
  profile ecosystem to keep pace.

## Alternatives considered

- **Bake in SR 11‑7 / a single framework (rejected):** dates instantly and narrows the
  audience; we watched SR 11‑7 get superseded mid-project.
- **A rigid, regulation-shaped schema (rejected):** forces every platform's metadata into
  one regulator's vocabulary at discovery time.

See [Governance](../governance.md).
