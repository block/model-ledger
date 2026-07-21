---
title: "ADR 0006 — Discovery and validation are two subsystems"
description: Recognize the event-log (discovery) and the rich governance model (validation) as complementary subsystems; bridge them additively rather than delete or rewrite either.
---

# ADR 0006 — Discovery and validation are two subsystems; bridge, don't delete

**Status:** Accepted

## Context

The codebase contains what looks, from the export list, like competing paradigms:

- **The event-log (v0.3+):** `ModelRef` (a thin identity) + immutable `Snapshot`s + the
  `DataNode` graph. This is the **discovery / inventory / agent** subsystem — *what models
  exist, how they connect, what changed*.
- **The rich governance model (v0.2):** `Model`/`ModelVersion` carrying `intended_purpose`,
  `risk_rating`, `affected_populations`, stakeholders, findings, deployments; the `validate`
  engine; and the SR 11‑7 / EU AI Act / NIST **compliance profiles** that check those fields.
  This is the **validation** subsystem — *can a model pass an examiner's bar?*

A surface-level read ("three paradigms in `__all__`, clean it up") suggests deleting the
v0.2 API. Mapping the dependencies shows that would be a serious mistake: the v0.2 model is
the substance behind the [Governance](../governance.md) page and the regulatory wedge — a
rich, field-level compliance model plus three non-trivial profiles, the audit-pack export,
and a meaningful share of the test suite. The thin event-log `ModelRef` carries none of those
fields, so it cannot be validated by the profiles as-is.

The real issue is not clutter. **The two subsystems are disconnected:** a *discovered* model
(`ModelRef`) has no path to *validation*. You can inventory a model or validate one, but not
both in one flow.

## Decision

1. **Retain the v0.2 governance/validation subsystem.** It is not legacy dead weight; it is
   the validation half of the product. Do not delete it or rewrite its profiles destructively.
2. **Bridge the two subsystems *additively*.** Make a discovered model validatable by
   projecting its event-log evidence (metadata + snapshots) into the governance concepts the
   profiles check — without breaking the existing rich-`Model` path. The event-log is the
   spine; validation becomes a capability over it.
3. **Document both layers honestly** — discovery and validation are two intentional,
   complementary subsystems, not old-vs-new. The fix for "surface clutter" is *clarity*, not
   deletion.

The bridge is a deliberate, staged effort (it touches the profile inputs and deserves its own
focused, well-tested change), not a rushed rewrite.

## Consequences

**Positive**

- The compliance capability — the product's differentiator — is preserved intact.
- Once bridged, discovery feeds validation: you can ask "is this *discovered* model SR 26‑2
  ready?" in one system.
- The public surface is explained as two coherent layers rather than apologized for as clutter.

**Negative (accepted)**

- Two models of a "model" coexist (thin `ModelRef`, rich `Model`) until the bridge matures;
  the mapping between them is an explicit layer to maintain.
- "Concept-based" validation over event-log evidence is looser than rich typed checks, so the
  bridge must be designed to preserve validation meaningfulness, not just presence-of-a-field.

## Alternatives considered

- **Delete v0.2 and clean `__all__` (rejected):** destroys the validation subsystem and the
  regulatory wedge; a shallow read of a deep system.
- **Immediately rewrite the profiles to be event-log-native (deferred):** correct direction,
  but rushing it risks downgrading sophisticated validation to thin evidence-checks. Staged.
- **Leave them disconnected, document the boundary (interim):** honest but leaves the two
  halves of governance unable to talk; acceptable only as a way station to the bridge.

See [Architecture](../concepts/architecture.md) and [Governance](../governance.md).
