---
title: Recipes
description: Copy-paste solutions to real tasks — impact analysis, point-in-time inventory, scheduled discovery, and more.
---

# Recipes

Self-contained, copy-paste solutions to real tasks. Each one runs against the
in-memory or SQLite backend with no setup.

<div class="grid cards" markdown>

-   <span class="recipe-num">Recipe № 1</span>

    __[Impact analysis](impact-analysis.md)__

    ---

    "If we deprecate this, what breaks?" Walk the dependency graph downstream to find
    the full blast radius before you change anything.

-   <span class="recipe-num">Recipe № 2</span>

    __[Point-in-time inventory](point-in-time.md)__

    ---

    Reconstruct exactly which models were active — and in what state — on any past
    date. The answer an examiner actually wants.

-   <span class="recipe-num">Recipe № 3</span>

    __[Discover from a SQL registry](discover-sql.md)__

    ---

    Point a connector at a database table and pull models into the ledger on a
    schedule, idempotently.

</div>

!!! note "More on the way"
    This gallery grows. Recipes are verified against the SDK so they can't quietly rot
    — if a release breaks one, the build fails.
