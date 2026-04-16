"""model-ledger: Open-source model governance framework.

Register models, track changes, discover dependencies, and validate
against compliance profiles (SR 11-7, EU AI Act, NIST AI RMF).

    >>> from model_ledger import Ledger
    >>> ledger = Ledger()
    >>> ledger.register(name="my-model", owner="alice", model_type="ml_model",
    ...                 tier="high", purpose="Fraud detection")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from model_ledger.connectors import github_connector, rest_connector, sql_connector
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
from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag
from model_ledger.core.models import ComponentNode, Model, ModelVersion
from model_ledger.graph.models import DataNode, DataPort
from model_ledger.graph.protocol import SourceConnector
from model_ledger.scanner.protocol import ModelCandidate, Scanner
from model_ledger.sdk.inventory import Inventory
from model_ledger.sdk.ledger import Ledger

# v0.6.0 — agent protocol tools
from model_ledger.tools import (
    changelog,
    discover,
    investigate,
    query,
    record,
    trace,
)
from model_ledger.tools.schemas import (
    ChangelogInput,
    ChangelogOutput,
    DiscoverInput,
    DiscoverOutput,
    InvestigateInput,
    InvestigateOutput,
    ModelSummary,
    QueryInput,
    QueryOutput,
    RecordInput,
    RecordOutput,
    TraceInput,
    TraceOutput,
)

if TYPE_CHECKING:
    from model_ledger.introspect.models import IntrospectionResult
    from model_ledger.introspect.protocol import Introspector

__all__ = [
    # v0.3.0 — primary API
    "Ledger",
    "ModelRef",
    "Snapshot",
    "Tag",
    "ModelCandidate",
    "Scanner",
    # v0.4.0 — graph
    "DataNode",
    "DataPort",
    "SourceConnector",
    # v0.5.0 — connector factories
    "sql_connector",
    "rest_connector",
    "github_connector",
    # v0.2.0 — legacy
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
    # v0.6.0 — agent tools
    "changelog",
    "discover",
    "investigate",
    "query",
    "record",
    "trace",
    "ChangelogInput",
    "ChangelogOutput",
    "DiscoverInput",
    "DiscoverOutput",
    "InvestigateInput",
    "InvestigateOutput",
    "ModelSummary",
    "QueryInput",
    "QueryOutput",
    "RecordInput",
    "RecordOutput",
    "TraceInput",
    "TraceOutput",
]

__version__ = "0.6.0"


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
