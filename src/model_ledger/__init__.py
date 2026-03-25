"""model-ledger: Developer-first model inventory and governance framework.

Register models, introspect ML artifacts, validate against compliance
profiles (SR 11-7, EU AI Act, NIST AI RMF), and export audit packs.

    >>> from model_ledger import Inventory
    >>> inv = Inventory()
    >>> inv.register_model(name="my-model", owner="alice", tier="high",
    ...                    intended_purpose="Fraud detection")
    >>> with inv.new_version("my-model") as v:
    ...     v.introspect(fitted_model)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from model_ledger.core.enums import ModelStatus, ModelType, RiskTier, VersionStatus
from model_ledger.core.exceptions import (
    ImmutableVersionError,
    ModelInventoryError,
    ModelNotFoundError,
    NoIntrospectorError,
    StorageError,
    ValidationError,
    VersionNotFoundError,
)
from model_ledger.core.models import ComponentNode, Model, ModelVersion
from model_ledger.sdk.inventory import Inventory

if TYPE_CHECKING:
    from model_ledger.introspect.models import IntrospectionResult
    from model_ledger.introspect.protocol import Introspector

__all__ = [
    # Core
    "Inventory",
    "Model",
    "ModelVersion",
    "ComponentNode",
    # Enums
    "ModelType",
    "RiskTier",
    "ModelStatus",
    "VersionStatus",
    # Exceptions
    "ModelInventoryError",
    "ModelNotFoundError",
    "VersionNotFoundError",
    "ImmutableVersionError",
    "ValidationError",
    "StorageError",
    "NoIntrospectorError",
    # Introspection
    "introspect",
    "register_introspector",
]

__version__ = "0.2.0"


def introspect(obj: Any, *, introspector: str | None = None) -> IntrospectionResult:
    """Introspect a model object — extract algorithm, features, and metadata.

    Works with any registered introspector plugin. Ships with sklearn,
    XGBoost, and LightGBM support out of the box.

    Args:
        obj: A fitted model object (e.g., sklearn estimator, XGBClassifier)
        introspector: Optional name of a specific introspector to use.
            If None, auto-detects based on the object type.

    Returns:
        IntrospectionResult with algorithm, features, hyperparameters, etc.

    Raises:
        NoIntrospectorError: If no registered introspector can handle the object.

    Example:
        >>> from model_ledger import introspect
        >>> result = introspect(fitted_model)
        >>> print(result.algorithm, len(result.features))
    """
    from model_ledger.introspect.registry import get_registry

    registry = get_registry()
    intro = registry.get_by_name(introspector) if introspector else registry.find(obj)
    return intro.introspect(obj)


def register_introspector(introspector: Introspector) -> None:
    """Register a custom introspector plugin.

    Manually registered introspectors take priority over entry-point-discovered ones.

    Args:
        introspector: An object implementing the Introspector protocol
            (must have name, can_handle, and introspect attributes).

    Example:
        >>> from model_ledger import register_introspector
        >>> register_introspector(MyCustomIntrospector())
    """
    from model_ledger.introspect.registry import get_registry

    get_registry().register(introspector)
