"""Model introspection — plugin-based metadata extraction."""

from model_ledger.introspect.models import (
    ComponentInfo,
    DataSourceInfo,
    FeatureInfo,
    IntrospectionResult,
    ThresholdInfo,
)
from model_ledger.introspect.protocol import Introspector
from model_ledger.introspect.registry import get_registry, register_introspector

__all__ = [
    "ComponentInfo",
    "DataSourceInfo",
    "FeatureInfo",
    "IntrospectionResult",
    "Introspector",
    "ThresholdInfo",
    "get_registry",
    "register_introspector",
]
