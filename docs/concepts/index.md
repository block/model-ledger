---
title: Concepts
description: The whole model in three ideas — the DataNode graph, the Snapshot event log, and Composites.
---

# Concepts

model-ledger is small on purpose. Three ideas carry the whole system.

<div class="grid cards" markdown>

-   :material-graph-outline:{ .lg } &nbsp;__[DataNode & the graph](datanode.md)__

    ---

    Everything is a `DataNode` with typed input/output ports. Declare what a node
    reads and writes; the dependency graph builds itself from port matching.

-   :material-history:{ .lg } &nbsp;__[Snapshot & the event log](snapshot.md)__

    ---

    A model is an identity (`ModelRef`). Everything that happens to it is an
    immutable, content-addressed `Snapshot`. The inventory is an append-only log.

-   :material-layers-outline:{ .lg } &nbsp;__[Composites](composite.md)__

    ---

    Governed groups whose members are themselves models. A "credit decision system"
    that rolls up its scorecard, policy rules, and ETL — each governed in its own right.

</div>

## How they fit together

```mermaid
graph TB
    subgraph identity ["Identity"]
        REF["ModelRef<br/><small>name · owner · type · tier · purpose</small>"]
    end
    subgraph history ["History (append-only)"]
        S1["Snapshot<br/><small>registered</small>"] --> S2["Snapshot<br/><small>retrained</small>"] --> S3["Snapshot<br/><small>validated</small>"]
    end
    subgraph graph ["Graph"]
        N1["DataNode"] -->|port match| N2["DataNode"]
    end
    REF --- S1
    REF -.is a node in.- N1
    classDef ink fill:#1c1a17,color:#f7f3ec,stroke:#000;
    classDef ox fill:#7a1a1a,color:#fff,stroke:#5a1010;
    class REF ink; class S1,S2,S3 ox;
```

- **Identity** is the minimum a regulator needs: who owns it, what kind of model,
  how risky, what it's for.
- **History** is every change, immutable and ordered. You can ask the inventory what
  it looked like on any past date.
- **Graph** is how models relate. Declare ports; dependencies follow.

A fourth idea — **compliance profiles** (SR 11-7, EU AI Act, NIST AI RMF) — reads this
data to check completeness. It's a pluggable layer, not part of the core model; see the
[API reference](../reference/index.md).
