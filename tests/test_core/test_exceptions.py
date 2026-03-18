"""Tests for core exception hierarchy with actionable messages."""

import pytest
from model_ledger.core.exceptions import (
    ModelInventoryError,
    ModelNotFoundError,
    VersionNotFoundError,
    ImmutableVersionError,
    ValidationError,
    StorageError,
)


def test_all_exceptions_inherit_from_base():
    for exc_cls in [
        ModelNotFoundError,
        VersionNotFoundError,
        ImmutableVersionError,
        ValidationError,
        StorageError,
    ]:
        assert issubclass(exc_cls, ModelInventoryError)


def test_model_not_found_shows_known_models():
    err = ModelNotFoundError("fraud_v1", known=["ccrr_global", "tm_arr"])
    assert "fraud_v1" in str(err)
    assert "ccrr_global" in str(err)


def test_model_not_found_no_known():
    err = ModelNotFoundError("fraud_v1")
    assert "fraud_v1" in str(err)


def test_version_not_found_suggests_new_version():
    err = VersionNotFoundError("ccrr_global", "2.0.0")
    assert "ccrr_global" in str(err)
    assert "2.0.0" in str(err)
    assert "new_version" in str(err)


def test_immutable_version_suggests_base():
    err = ImmutableVersionError("ccrr_global", "1.0.0")
    assert "immutable" in str(err).lower()
    assert "1.0.0" in str(err)
    assert "base" in str(err).lower()


def test_catch_all_with_base_class():
    with pytest.raises(ModelInventoryError):
        raise ModelNotFoundError("test")

    with pytest.raises(ModelInventoryError):
        raise ImmutableVersionError("test", "1.0.0")
