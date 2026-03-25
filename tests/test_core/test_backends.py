"""Tests for storage backends with parametrized fixtures."""

import pytest

from model_ledger.backends.memory import InMemoryBackend
from model_ledger.backends.sqlite import SQLiteBackend
from model_ledger.core.enums import RiskTier, VersionStatus
from model_ledger.core.exceptions import ImmutableVersionError
from model_ledger.core.models import AuditEvent, Model, ModelVersion


@pytest.fixture(params=["sqlite", "memory"])
def backend(request, tmp_path):
    if request.param == "sqlite":
        return SQLiteBackend(str(tmp_path / "test.db"))
    return InMemoryBackend()


def _make_model(name="test_model"):
    return Model(name=name, owner="alice", tier=RiskTier.HIGH, intended_purpose="Testing")


def test_save_and_get_model(backend):
    model = _make_model()
    backend.save_model(model)
    loaded = backend.get_model("test_model")
    assert loaded is not None
    assert loaded.name == "test_model"


def test_get_nonexistent_model(backend):
    assert backend.get_model("nope") is None


def test_list_models(backend):
    backend.save_model(_make_model("a"))
    backend.save_model(_make_model("b"))
    assert len(backend.list_models()) == 2


def test_upsert_model(backend):
    model = _make_model()
    backend.save_model(model)
    model.business_unit = "Lending"
    backend.save_model(model)
    loaded = backend.get_model("test_model")
    assert loaded.business_unit == "Lending"


def test_save_and_get_version(backend):
    backend.save_model(_make_model())
    version = ModelVersion(version="1.0.0")
    backend.save_version("test_model", version)
    loaded = backend.get_version("test_model", "1.0.0")
    assert loaded is not None
    assert len(loaded.tree.children) == 3


def test_save_draft_version_allows_overwrite(backend):
    backend.save_model(_make_model())
    v = ModelVersion(version="1.0.0")
    backend.save_version("test_model", v)
    v.run_frequency = "daily"
    backend.save_version("test_model", v)
    loaded = backend.get_version("test_model", "1.0.0")
    assert loaded.run_frequency == "daily"


def test_backend_rejects_published_version_modification(backend):
    backend.save_model(_make_model())
    version = ModelVersion(version="1.0.0", status=VersionStatus.PUBLISHED)
    backend.save_version("test_model", version)
    modified = ModelVersion(version="1.0.0", status=VersionStatus.PUBLISHED, run_frequency="daily")
    with pytest.raises(ImmutableVersionError):
        backend.save_version("test_model", modified)


def test_force_save_version_bypasses_immutability(backend):
    backend.save_model(_make_model())
    version = ModelVersion(version="1.0.0", status=VersionStatus.DRAFT)
    backend.save_version("test_model", version)
    version.status = VersionStatus.PUBLISHED
    backend.force_save_version("test_model", version)
    loaded = backend.get_version("test_model", "1.0.0")
    assert loaded.status == VersionStatus.PUBLISHED


def test_audit_event_append_only(backend):
    event = AuditEvent(
        actor="alice",
        action="registered_model",
        model_name="test",
        details={},
    )
    backend.append_audit_event(event)
    log = backend.get_audit_log("test")
    assert len(log) == 1
    assert log[0].actor == "alice"


def test_audit_log_ordered(backend):
    for i in range(3):
        backend.append_audit_event(
            AuditEvent(
                actor="alice",
                action=f"action_{i}",
                model_name="test",
                details={},
            )
        )
    log = backend.get_audit_log("test")
    assert len(log) == 3
    assert log[0].action == "action_0"


def test_audit_log_filtered_by_version(backend):
    backend.append_audit_event(
        AuditEvent(actor="a", action="x", model_name="m", version="1.0.0", details={})
    )
    backend.append_audit_event(
        AuditEvent(actor="a", action="y", model_name="m", version="2.0.0", details={})
    )
    log = backend.get_audit_log("m", version="1.0.0")
    assert len(log) == 1
    assert log[0].version == "1.0.0"


def test_get_nonexistent_version(backend):
    backend.save_model(_make_model())
    assert backend.get_version("test_model", "99.0.0") is None


def test_list_versions(backend):
    """Test that list_versions returns all versions for a model."""
    model = Model(name="test-lv", owner="tester", tier=RiskTier.LOW, intended_purpose="testing")
    backend.save_model(model)
    v1 = ModelVersion(version="0.1.0")
    v2 = ModelVersion(version="0.2.0")
    backend.save_version("test-lv", v1)
    backend.save_version("test-lv", v2)
    versions = backend.list_versions("test-lv")
    version_strs = [v.version for v in versions]
    assert "0.1.0" in version_strs
    assert "0.2.0" in version_strs
