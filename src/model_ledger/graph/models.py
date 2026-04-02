"""DataNode and DataPort — the core graph primitives."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any


class DataPort:
    """A connection point. Acts like a string, carries optional schema for precision."""
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
    if "%" in a:
        pattern = "^" + re.escape(a).replace("%", ".*") + "$"
        return bool(re.match(pattern, b, re.IGNORECASE))
    if "%" in b:
        pattern = "^" + re.escape(b).replace("%", ".*") + "$"
        return bool(re.match(pattern, a, re.IGNORECASE))
    return a.lower() == b.lower()


@dataclass
class DataNode:
    name: str
    platform: str = ""
    inputs: list[DataPort] = field(default_factory=list)
    outputs: list[DataPort] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.inputs = [DataPort(x) if isinstance(x, str) else x for x in self.inputs]
        self.outputs = [DataPort(x) if isinstance(x, str) else x for x in self.outputs]
