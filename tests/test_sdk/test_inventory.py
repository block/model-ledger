"""Tests for the fluent SDK with context manager."""

import pytest

from model_ledger import Inventory
from model_ledger.backends.memory import InMemoryBackend
from model_ledger.core.enums import RiskTier, VersionStatus
from model_ledger.core.exceptions import (
    ModelNotFoundError,
    VersionNotFoundError,
)


@pytest.fixture
def inv(tmp_path):
    return Inventory(db_path=str(tmp_path / "test.db"))


def test_register_model(inv):
    model = inv.register_model(
        name="fraud_model",
        owner="alice",
        tier="high",
        intended_purpose="Detect fraud",
    )
    assert model.name == "fraud_model"
    assert model.tier == RiskTier.HIGH


def test_register_model_idempotent(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    assert len(inv.list_models()) == 1


def test_new_version_context_manager(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with inv.new_version("m") as v:
        v.add_component("inputs/features/risk_score", type="Feature")
        v.add_document(doc_type="system_design", title="CSD v1")
    loaded = inv.get_version("m", v.version_str)
    assert loaded is not None
    assert loaded.status == VersionStatus.DRAFT
    # Inputs should have a child
    inputs = loaded.tree.children[0]
    assert len(inputs.children) > 0


def test_new_version_with_base_copies_content(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with inv.new_version("m") as v:
        v.add_component("inputs/features/f1", type="Feature")
        v.add_document(doc_type="model_spec", title="Spec")
    inv.publish("m", v.version_str)

    with inv.new_version("m", base=v.version_str) as v2:
        pass
    loaded = inv.get_version("m", v2.version_str)
    # Tree copied from base
    inputs = loaded.tree.children[0]
    assert len(inputs.children) > 0
    # Docs copied from base
    assert len(loaded.documents) > 0


def test_publish_makes_immutable(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with inv.new_version("m") as v:
        pass
    inv.publish("m", v.version_str)
    loaded = inv.get_version("m", v.version_str)
    assert loaded.status == VersionStatus.PUBLISHED


def test_model_not_found(inv):
    with pytest.raises(ModelNotFoundError, match="No model named"):
        inv.new_version("nonexistent")


def test_add_reference(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with inv.new_version("m") as v:
        v.add_reference("github", identifier="abc123", metadata={"repo": "test"})
    loaded = inv.get_version("m", v.version_str)
    assert len(loaded.references) == 1


def test_add_evidence(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with inv.new_version("m") as v:
        v.add_evidence("test_result", title="Unit tests", artifact_uri="gs://bucket/results.json")
    loaded = inv.get_version("m", v.version_str)
    assert len(loaded.evidence) == 1


def test_add_artifact(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with inv.new_version("m") as v:
        v.add_artifact(artifact_type="pickle", uri="gs://bucket/model.pkl")
    loaded = inv.get_version("m", v.version_str)
    assert len(loaded.artifacts) == 1


def test_deprecate_version(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with inv.new_version("m") as v:
        pass
    inv.publish("m", v.version_str)
    inv.deprecate("m", v.version_str)
    loaded = inv.get_version("m", v.version_str)
    assert loaded.status == VersionStatus.DEPRECATED


def test_audit_trail(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test", actor="vignesh")
    log = inv.get_audit_log("m")
    assert len(log) >= 1
    assert log[0].action == "registered_model"
    assert log[0].actor == "vignesh"


def test_set_training_target(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with inv.new_version("m") as v:
        v.set_training_target("SAR filing prediction")
        v.set_run_frequency("daily")
    loaded = inv.get_version("m", v.version_str)
    assert loaded.training_target == "SAR filing prediction"
    assert loaded.run_frequency == "daily"


def test_set_next_validation_due(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with inv.new_version("m") as v:
        v.set_next_validation_due("2027-01-01")
    loaded = inv.get_version("m", v.version_str)
    assert str(loaded.next_validation_due) == "2027-01-01"


def test_get_model_raises_on_missing(inv):
    with pytest.raises(ModelNotFoundError):
        inv.get_model("nonexistent")


def test_version_not_found_on_publish(inv):
    inv.register_model(name="m", owner="a", tier="low", intended_purpose="Test")
    with pytest.raises(VersionNotFoundError):
        inv.publish("m", "99.0.0")


def test_draft_version_introspect():
    from model_ledger.introspect.models import FeatureInfo, IntrospectionResult
    from model_ledger.introspect.registry import get_registry, reset_registry

    class FakeIntrospector:
        name = "fake"

        def can_handle(self, obj):
            return isinstance(obj, dict) and obj.get("_type") == "fake_model"

        def introspect(self, obj):
            return IntrospectionResult(
                introspector="fake",
                framework="fake-framework",
                algorithm="FakeAlgorithm",
                features=[FeatureInfo(name="f1"), FeatureInfo(name="f2")],
            )

    reset_registry()
    get_registry().register(FakeIntrospector())

    inv = Inventory(backend=InMemoryBackend())
    inv.register_model(name="test-model", owner="tester", tier="low", intended_purpose="testing")
    with inv.new_version("test-model") as v:
        result = v.introspect({"_type": "fake_model"})

    assert isinstance(result, IntrospectionResult)
    assert result.algorithm == "FakeAlgorithm"
    version = inv.get_version("test-model", v.version_str)
    assert version.methodology_approach == "FakeAlgorithm"
    reset_registry()


def test_standalone_introspect():
    # Import the function directly to avoid subpackage shadowing
    import importlib

    import model_ledger as _ml

    # Reload to restore the function attribute after subpackage import
    importlib.reload(_ml)
    ml_introspect = _ml.introspect

    from model_ledger.introspect.models import IntrospectionResult
    from model_ledger.introspect.registry import get_registry, reset_registry

    class FakeIntrospector:
        name = "fake"

        def can_handle(self, obj):
            return isinstance(obj, dict) and obj.get("_type") == "fake_model"

        def introspect(self, obj):
            return IntrospectionResult(introspector="fake", algorithm="FakeAlgo")

    reset_registry()
    get_registry().register(FakeIntrospector())

    result = ml_introspect({"_type": "fake_model"})
    assert result.algorithm == "FakeAlgo"
    reset_registry()


def test_new_version_explicit_version_string(inv):
    """Test that explicit version parameter is used as-is."""
    inv.register_model(
        name="test-explicit",
        owner="tester",
        tier="low",
        intended_purpose="testing",
    )
    with inv.new_version("test-explicit", version="3.0.0") as v:
        pass
    assert v.version_str == "3.0.0"
    stored = inv.get_version("test-explicit", "3.0.0")
    assert stored is not None
    assert stored.version == "3.0.0"


def test_new_version_explicit_preserves_auto_increment(inv):
    """Explicit version doesn't break auto-increment for subsequent versions."""
    inv.register_model(
        name="test-mixed",
        owner="tester",
        tier="low",
        intended_purpose="testing",
    )
    with inv.new_version("test-mixed", version="3.0.0") as v1:
        pass
    with inv.new_version("test-mixed") as v2:
        pass
    assert v1.version_str == "3.0.0"
    assert v2.version_str == "0.1.0"  # auto-increment starts fresh
