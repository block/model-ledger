# v0.4.0 DataNode Graph — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `DataNode`, `DataPort`, and graph methods (`add`, `connect`, `trace`, `upstream`, `downstream`) to the Ledger class, enabling auto-discovery of model dependency graphs from port matching.

**Architecture:** `DataNode` and `DataPort` are new data models in `graph/`. `DataPort` is a smart string — acts like a string by default, carries optional schema for shared-table discriminators. The `Ledger` class gets 5 new methods that decompose into existing `register()`, `record()`, and `link_dependency()` calls. No new storage — everything persists through the existing Snapshot/ModelRef infrastructure.

**Tech Stack:** Python 3.10+, Pydantic (existing), pytest

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/model_ledger/graph/__init__.py` | Package init, re-exports |
| Create | `src/model_ledger/graph/models.py` | `DataNode`, `DataPort` |
| Create | `src/model_ledger/graph/protocol.py` | `SourceConnector` protocol |
| Modify | `src/model_ledger/sdk/ledger.py` | Add `add()`, `connect()`, `trace()`, `upstream()`, `downstream()` |
| Modify | `src/model_ledger/__init__.py` | Export `DataNode`, `DataPort` |
| Create | `tests/test_graph/__init__.py` | Test package |
| Create | `tests/test_graph/test_models.py` | DataNode and DataPort tests |
| Create | `tests/test_graph/test_ledger_graph.py` | Ledger graph method tests |

---

### Task 1: DataPort

**Files:**
- Create: `src/model_ledger/graph/__init__.py`
- Create: `src/model_ledger/graph/models.py`
- Create: `tests/test_graph/__init__.py`
- Create: `tests/test_graph/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph/__init__.py
# (empty)
```

```python
# tests/test_graph/test_models.py
"""Tests for DataNode and DataPort."""

from model_ledger.graph.models import DataPort, DataNode


class TestDataPort:
    def test_create_from_string_identifier(self):
        p = DataPort("my_table")
        assert p.identifier == "my_table"
        assert p.schema == {}

    def test_lowercases_identifier(self):
        p = DataPort("APP_COMPLIANCE.CASH.TABLE")
        assert p.identifier == "app_compliance.cash.table"

    def test_equality_same_identifier(self):
        assert DataPort("table_a") == DataPort("table_a")

    def test_equality_case_insensitive(self):
        assert DataPort("TABLE_A") == DataPort("table_a")

    def test_inequality_different_identifier(self):
        assert DataPort("table_a") != DataPort("table_b")

    def test_equality_with_matching_schema(self):
        a = DataPort("shared_table", model_name="tm-m2o")
        b = DataPort("shared_table", model_name="tm-m2o")
        assert a == b

    def test_inequality_with_different_schema(self):
        a = DataPort("shared_table", model_name="tm-m2o")
        b = DataPort("shared_table", model_name="tm-o2m")
        assert a != b

    def test_equality_one_has_no_schema(self):
        a = DataPort("shared_table", model_name="tm-m2o")
        b = DataPort("shared_table")
        assert a == b  # no schema on b means "match any"

    def test_schema_like_pattern(self):
        a = DataPort("scores", model_name="tm-%")
        b = DataPort("scores", model_name="tm-m2o")
        assert a == b

    def test_schema_like_pattern_no_match(self):
        a = DataPort("scores", model_name="tm-%")
        b = DataPort("scores", model_name="uup-gambling")
        assert a != b

    def test_hashable(self):
        s = {DataPort("a"), DataPort("a"), DataPort("b")}
        assert len(s) == 2

    def test_repr(self):
        p = DataPort("table", model_name="x")
        assert "table" in repr(p)
        assert "model_name" in repr(p)

    def test_repr_simple(self):
        p = DataPort("table")
        assert "table" in repr(p)


class TestDataNode:
    def test_create_with_string_inputs(self):
        node = DataNode("scorer", inputs=["features", "segments"], outputs=["scores"])
        assert len(node.inputs) == 2
        assert all(isinstance(p, DataPort) for p in node.inputs)
        assert node.inputs[0].identifier == "features"

    def test_create_with_dataport_inputs(self):
        node = DataNode("scorer", inputs=[DataPort("features")], outputs=["scores"])
        assert node.inputs[0].identifier == "features"

    def test_create_mixed_inputs(self):
        node = DataNode("scorer",
            inputs=["features", DataPort("scores", model_name="tm-m2o")],
            outputs=["alerts"])
        assert node.inputs[0].identifier == "features"
        assert node.inputs[1].schema == {"model_name": "tm-m2o"}

    def test_defaults(self):
        node = DataNode("simple")
        assert node.platform == ""
        assert node.inputs == []
        assert node.outputs == []
        assert node.metadata == {}

    def test_metadata(self):
        node = DataNode("scorer", platform="gondola",
            metadata={"owner": "ml-team", "version": "v3"})
        assert node.metadata["owner"] == "ml-team"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Development/model-ledger && uv run pytest tests/test_graph/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# src/model_ledger/graph/__init__.py
"""Graph-based model discovery — DataNode, DataPort, SourceConnector."""

from model_ledger.graph.models import DataNode, DataPort

__all__ = ["DataNode", "DataPort"]
```

```python
# src/model_ledger/graph/models.py
"""DataNode and DataPort — the core graph primitives."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class DataPort:
    """A connection point. Acts like a string, carries optional schema for precision.

    Simple case — just an identifier:
        DataPort("transactions_table")

    With discriminator — for shared tables:
        DataPort("batch_scores_archive", model_name="tm-m2o")

    Matching:
        - Two ports match if identifiers are equal (case-insensitive)
        - If both have a schema key, values must match (supports SQL LIKE %)
        - If only one has a schema key, it matches anything
    """

    __slots__ = ("identifier", "schema")

    def __init__(self, identifier: str, **schema: str) -> None:
        self.identifier = identifier.lower()
        self.schema = schema

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.identifier == other.lower()
        if not isinstance(other, DataPort):
            return NotImplemented
        if self.identifier != other.identifier:
            return False
        for key in set(self.schema) & set(other.schema):
            if not _value_matches(self.schema[key], other.schema[key]):
                return False
        return True

    def __hash__(self) -> int:
        return hash(self.identifier)

    def __repr__(self) -> str:
        if self.schema:
            params = ", ".join(f"{k}={v!r}" for k, v in self.schema.items())
            return f"DataPort({self.identifier!r}, {params})"
        return f"DataPort({self.identifier!r})"


def _value_matches(a: str, b: str) -> bool:
    """Match values, supporting SQL LIKE patterns (% wildcard)."""
    if "%" in a:
        pattern = "^" + re.escape(a).replace("%", ".*") + "$"
        return bool(re.match(pattern, b, re.IGNORECASE))
    if "%" in b:
        pattern = "^" + re.escape(b).replace("%", ".*") + "$"
        return bool(re.match(pattern, a, re.IGNORECASE))
    return a.lower() == b.lower()


@dataclass
class DataNode:
    """A model, job, rule, or workflow that transforms data.

    Inputs and outputs can be strings (auto-wrapped as DataPort)
    or DataPort objects (for shared-table discriminators).

    Example:
        >>> node = DataNode("fraud_scorer", platform="gondola",
        ...     inputs=["features", "segments"],
        ...     outputs=["scores"])
    """

    name: str
    platform: str = ""
    inputs: list[DataPort] = field(default_factory=list)
    outputs: list[DataPort] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.inputs = [DataPort(x) if isinstance(x, str) else x for x in self.inputs]
        self.outputs = [DataPort(x) if isinstance(x, str) else x for x in self.outputs]
```

- [ ] **Step 4: Run tests**

Run: `cd ~/Development/model-ledger && uv run pytest tests/test_graph/test_models.py -v`
Expected: PASS (15 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/Development/model-ledger
git add src/model_ledger/graph/ tests/test_graph/
git commit -m "feat: add DataNode and DataPort graph primitives"
```

---

### Task 2: SourceConnector Protocol

**Files:**
- Create: `src/model_ledger/graph/protocol.py`

- [ ] **Step 1: Write implementation**

```python
# src/model_ledger/graph/protocol.py
"""SourceConnector protocol — the extension point for platform discovery."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from model_ledger.graph.models import DataNode


@runtime_checkable
class SourceConnector(Protocol):
    """Discovers DataNodes from a platform.

    Implement this to connect a new data source (Snowflake, SageMaker,
    Airflow, etc.) to the model-ledger graph.

    Example:
        class MyConnector:
            name = "my_platform"
            def discover(self) -> list[DataNode]:
                return [DataNode("model_a", inputs=["table_x"], outputs=["scores"])]
    """

    name: str

    def discover(self) -> list[DataNode]: ...
```

- [ ] **Step 2: Update graph __init__.py**

```python
# src/model_ledger/graph/__init__.py
"""Graph-based model discovery — DataNode, DataPort, SourceConnector."""

from model_ledger.graph.models import DataNode, DataPort
from model_ledger.graph.protocol import SourceConnector

__all__ = ["DataNode", "DataPort", "SourceConnector"]
```

- [ ] **Step 3: Commit**

```bash
cd ~/Development/model-ledger
git add src/model_ledger/graph/protocol.py src/model_ledger/graph/__init__.py
git commit -m "feat: add SourceConnector protocol"
```

---

### Task 3: Ledger Graph Methods

**Files:**
- Modify: `src/model_ledger/sdk/ledger.py`
- Create: `tests/test_graph/test_ledger_graph.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph/test_ledger_graph.py
"""Tests for Ledger graph methods — add, connect, trace, upstream, downstream."""

import pytest

from model_ledger.graph.models import DataNode, DataPort
from model_ledger.sdk.ledger import Ledger


@pytest.fixture
def ledger():
    return Ledger()


class TestAdd:
    def test_add_single_node(self, ledger):
        node = DataNode("scorer", platform="gondola",
            inputs=["features"], outputs=["scores"])
        ledger.add(node)
        model = ledger.get("scorer")
        assert model.name == "scorer"

    def test_add_list_of_nodes(self, ledger):
        nodes = [
            DataNode("a", platform="x", inputs=[], outputs=["t1"]),
            DataNode("b", platform="x", inputs=["t1"], outputs=[]),
        ]
        ledger.add(nodes)
        assert len(ledger.list()) == 2

    def test_add_creates_discovered_snapshot(self, ledger):
        node = DataNode("scorer", platform="gondola",
            inputs=["features"], outputs=["scores"],
            metadata={"owner": "ml-team"})
        ledger.add(node)
        snaps = ledger.history("scorer")
        assert len(snaps) >= 1
        discovered = [s for s in snaps if s.event_type == "discovered"]
        assert len(discovered) == 1
        assert discovered[0].payload["platform"] == "gondola"
        assert discovered[0].payload["inputs"] == [{"identifier": "features"}]

    def test_add_idempotent(self, ledger):
        node = DataNode("scorer", platform="gondola", outputs=["scores"])
        ledger.add(node)
        ledger.add(node)
        assert len(ledger.list()) == 1


class TestConnect:
    def test_connect_matching_ports(self, ledger):
        ledger.add([
            DataNode("writer", outputs=["shared_table"]),
            DataNode("reader", inputs=["shared_table"]),
        ])
        result = ledger.connect()
        assert result["links_created"] >= 1

        deps = ledger.dependencies("reader", direction="upstream")
        assert any(d["model"].name == "writer" for d in deps)

    def test_connect_no_match(self, ledger):
        ledger.add([
            DataNode("a", outputs=["table_x"]),
            DataNode("b", inputs=["table_y"]),
        ])
        result = ledger.connect()
        assert result["links_created"] == 0

    def test_connect_skips_self_refs(self, ledger):
        ledger.add(DataNode("a", inputs=["t"], outputs=["t"]))
        result = ledger.connect()
        assert result["links_created"] == 0

    def test_connect_shared_table_with_discriminator(self, ledger):
        ledger.add([
            DataNode("writer_a", outputs=[DataPort("shared", model_name="model_a")]),
            DataNode("writer_b", outputs=[DataPort("shared", model_name="model_b")]),
            DataNode("reader_a", inputs=[DataPort("shared", model_name="model_a")]),
        ])
        result = ledger.connect()
        deps = ledger.dependencies("reader_a", direction="upstream")
        upstream_names = [d["model"].name for d in deps]
        assert "writer_a" in upstream_names
        assert "writer_b" not in upstream_names

    def test_connect_pipeline(self, ledger):
        ledger.add([
            DataNode("segmentation", outputs=["segments"]),
            DataNode("scoring", inputs=["segments"], outputs=["scores"]),
            DataNode("alerting", inputs=["scores"], outputs=["alerts"]),
        ])
        ledger.connect()
        # alerting depends on scoring depends on segmentation
        deps = ledger.dependencies("alerting", direction="upstream")
        assert any(d["model"].name == "scoring" for d in deps)
        deps2 = ledger.dependencies("scoring", direction="upstream")
        assert any(d["model"].name == "segmentation" for d in deps2)


class TestTrace:
    def test_trace_returns_ordered_pipeline(self, ledger):
        ledger.add([
            DataNode("seg", outputs=["segments"]),
            DataNode("score", inputs=["segments"], outputs=["scores"]),
            DataNode("alert", inputs=["scores"]),
        ])
        ledger.connect()
        pipeline = ledger.trace("alert")
        assert pipeline == ["seg", "score", "alert"]

    def test_trace_single_node(self, ledger):
        ledger.add(DataNode("standalone"))
        ledger.connect()
        assert ledger.trace("standalone") == ["standalone"]

    def test_trace_not_found(self, ledger):
        with pytest.raises(Exception):
            ledger.trace("nonexistent")


class TestUpstreamDownstream:
    def test_upstream(self, ledger):
        ledger.add([
            DataNode("a", outputs=["t1"]),
            DataNode("b", inputs=["t1"], outputs=["t2"]),
            DataNode("c", inputs=["t2"]),
        ])
        ledger.connect()
        assert "a" in ledger.upstream("b")
        assert "a" in ledger.upstream("c")
        assert "b" in ledger.upstream("c")

    def test_downstream(self, ledger):
        ledger.add([
            DataNode("a", outputs=["t1"]),
            DataNode("b", inputs=["t1"], outputs=["t2"]),
            DataNode("c", inputs=["t2"]),
        ])
        ledger.connect()
        assert "b" in ledger.downstream("a")
        assert "c" in ledger.downstream("a")

    def test_upstream_empty(self, ledger):
        ledger.add(DataNode("root", outputs=["t1"]))
        ledger.connect()
        assert ledger.upstream("root") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Development/model-ledger && uv run pytest tests/test_graph/test_ledger_graph.py -v`
Expected: FAIL — `AttributeError: 'Ledger' object has no attribute 'add'`

- [ ] **Step 3: Write implementation**

Add these methods to `src/model_ledger/sdk/ledger.py`, at the end of the `Ledger` class:

```python
    # --- Graph methods (v0.4.0) ---

    def add(self, nodes: DataNode | list[DataNode]) -> None:
        """Register DataNodes. Each becomes a ModelRef + discovered Snapshot."""
        from model_ledger.graph.models import DataNode, DataPort

        if isinstance(nodes, DataNode):
            nodes = [nodes]
        for node in nodes:
            self.register(
                name=node.name,
                owner=node.metadata.get("owner", "unknown"),
                model_type=node.metadata.get("node_type", "unknown"),
                tier=node.metadata.get("tier", "unclassified"),
                purpose=node.metadata.get("purpose", ""),
                model_origin=node.metadata.get("model_origin", "internal"),
                actor=f"connector:{node.platform}" if node.platform else "system",
            )
            self.record(
                node.name,
                event="discovered",
                payload={
                    "platform": node.platform,
                    "inputs": [
                        {"identifier": p.identifier, **p.schema}
                        for p in node.inputs
                    ],
                    "outputs": [
                        {"identifier": p.identifier, **p.schema}
                        for p in node.outputs
                    ],
                    **{k: v for k, v in node.metadata.items()
                       if k not in ("owner", "node_type", "tier", "purpose", "model_origin")},
                },
                actor=f"connector:{node.platform}" if node.platform else "system",
            )

    def connect(self) -> dict[str, int]:
        """Match output ports to input ports. Write dependency links."""
        from collections import defaultdict
        from model_ledger.graph.models import DataNode, DataPort

        nodes = self._load_discovered_nodes()
        output_index: dict[str, list[tuple[DataNode, DataPort]]] = defaultdict(list)
        for node in nodes:
            for port in node.outputs:
                output_index[port.identifier].append((node, port))

        links_created = 0
        seen: set[tuple[str, str]] = set()
        for node in nodes:
            for in_port in node.inputs:
                for upstream_node, out_port in output_index.get(in_port.identifier, []):
                    if upstream_node.name == node.name:
                        continue
                    if not (out_port == in_port):
                        continue
                    key = (upstream_node.name, node.name)
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        self.link_dependency(
                            upstream=upstream_node.name,
                            downstream=node.name,
                            relationship="data_flow",
                            actor="graph_builder",
                            metadata={
                                "via": in_port.identifier,
                                "via_schema": in_port.schema if in_port.schema else None,
                            },
                        )
                        links_created += 1
                    except ModelNotFoundError:
                        continue
        return {"links_created": links_created}

    def trace(self, name: str) -> list[str]:
        """Topological path from sources to this node."""
        self._resolve_model(name)  # raises if not found
        visited: set[str] = set()
        order: list[str] = []

        def _walk(n: str) -> None:
            if n in visited:
                return
            visited.add(n)
            for dep in self.dependencies(n, direction="upstream"):
                _walk(dep["model"].name)
            order.append(n)

        _walk(name)
        return order

    def upstream(self, name: str) -> list[str]:
        """All models this one depends on (transitive)."""
        path = self.trace(name)
        return [n for n in path if n != name]

    def downstream(self, name: str) -> list[str]:
        """All models that depend on this one (transitive)."""
        self._resolve_model(name)
        visited: set[str] = set()
        result: list[str] = []

        def _walk(n: str) -> None:
            for dep in self.dependencies(n, direction="downstream"):
                child = dep["model"].name
                if child not in visited:
                    visited.add(child)
                    result.append(child)
                    _walk(child)

        _walk(name)
        return result

    def _load_discovered_nodes(self) -> list[DataNode]:
        """Rebuild DataNodes from stored discovery snapshots."""
        from model_ledger.graph.models import DataNode, DataPort

        nodes = []
        for model in self._backend.list_models():
            snaps = self._backend.list_snapshots(model.model_hash)
            discovered = [s for s in snaps if s.event_type == "discovered"]
            if not discovered:
                continue
            latest = max(discovered, key=lambda s: s.timestamp)
            payload = latest.payload
            inputs = [
                DataPort(p["identifier"], **{k: v for k, v in p.items() if k != "identifier"})
                for p in payload.get("inputs", [])
            ]
            outputs = [
                DataPort(p["identifier"], **{k: v for k, v in p.items() if k != "identifier"})
                for p in payload.get("outputs", [])
            ]
            nodes.append(DataNode(
                name=model.name,
                platform=payload.get("platform", ""),
                inputs=inputs,
                outputs=outputs,
                metadata={k: v for k, v in payload.items()
                          if k not in ("platform", "inputs", "outputs")},
            ))
        return nodes
```

Also add the import at the top of the file (after existing imports):

```python
from __future__ import annotations

from typing import TYPE_CHECKING
# ... existing imports ...

if TYPE_CHECKING:
    from model_ledger.graph.models import DataNode
```

- [ ] **Step 4: Run tests**

Run: `cd ~/Development/model-ledger && uv run pytest tests/test_graph/ -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `cd ~/Development/model-ledger && uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
cd ~/Development/model-ledger
git add src/model_ledger/sdk/ledger.py tests/test_graph/test_ledger_graph.py
git commit -m "feat: add graph methods to Ledger (add, connect, trace, upstream, downstream)"
```

---

### Task 4: Public API Exports

**Files:**
- Modify: `src/model_ledger/__init__.py`

- [ ] **Step 1: Update exports**

Add to the imports:
```python
from model_ledger.graph.models import DataNode, DataPort
from model_ledger.graph.protocol import SourceConnector
```

Add to `__all__`:
```python
    # v0.4.0 — graph
    "DataNode",
    "DataPort",
    "SourceConnector",
```

Update version:
```python
__version__ = "0.4.0"
```

- [ ] **Step 2: Verify imports work**

Run: `cd ~/Development/model-ledger && uv run python -c "from model_ledger import Ledger, DataNode, DataPort, SourceConnector; print('OK')"`

- [ ] **Step 3: Commit**

```bash
cd ~/Development/model-ledger
git add src/model_ledger/__init__.py
git commit -m "feat: export DataNode, DataPort, SourceConnector — model-ledger v0.4.0"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | DataPort + DataNode | 15 |
| 2 | SourceConnector protocol | 0 |
| 3 | Ledger graph methods | 14 |
| 4 | Public exports | 0 (verification) |
| **Total** | | **29 tests** |
