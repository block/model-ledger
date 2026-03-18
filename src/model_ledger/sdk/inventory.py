"""Inventory — the main entry point for model-ledger."""

from __future__ import annotations

from model_ledger.backends.protocol import InventoryBackend
from model_ledger.backends.sqlite import SQLiteBackend
from model_ledger.core.enums import ModelType, RiskTier, VersionStatus
from model_ledger.core.exceptions import (
    ImmutableVersionError,
    ModelNotFoundError,
    VersionNotFoundError,
)
from model_ledger.core.models import AuditEvent, Model, ModelVersion
from model_ledger.sdk.draft_version import DraftVersion


class Inventory:
    def __init__(
        self,
        db_path: str = "inventory.db",
        backend: InventoryBackend | None = None,
    ) -> None:
        self._backend = backend or SQLiteBackend(db_path)

    def register_model(
        self,
        *,
        name: str,
        owner: str,
        tier: str | RiskTier,
        intended_purpose: str,
        developers: list[str] | None = None,
        validator: str | None = None,
        business_unit: str | None = None,
        model_type: str | ModelType = "ml_model",
        jurisdictions: list[str] | None = None,
        vendor: str | None = None,
        tags: list[str] | None = None,
        actor: str = "system",
    ) -> Model:
        existing = self._backend.get_model(name)
        if existing is not None:
            return existing
        model = Model(
            name=name,
            owner=owner,
            tier=RiskTier(tier),
            intended_purpose=intended_purpose,
            developers=developers or [],
            validator=validator,
            business_unit=business_unit,
            model_type=ModelType(model_type),
            jurisdictions=jurisdictions or [],
            vendor=vendor,
            tags=tags or [],
        )
        self._backend.save_model(model)
        self._backend.append_audit_event(
            AuditEvent(
                actor=actor,
                action="registered_model",
                model_name=name,
                details={"tier": str(model.tier.value)},
            )
        )
        return model

    def get_model(self, name: str) -> Model:
        model = self._backend.get_model(name)
        if model is None:
            known = [m.name for m in self._backend.list_models()]
            raise ModelNotFoundError(name, known)
        return model

    def list_models(self) -> list[Model]:
        return self._backend.list_models()

    def new_version(
        self,
        model_name: str,
        base: str | None = None,
        actor: str = "system",
    ) -> DraftVersion:
        self.get_model(model_name)
        if base:
            base_version = self._backend.get_version(model_name, base)
            if base_version is None:
                raise VersionNotFoundError(model_name, base)
            parts = base.split(".")
            parts[1] = str(int(parts[1]) + 1)
            parts[2] = "0"
            new_ver_str = ".".join(parts)
            version = base_version.model_copy(deep=True)
            version.version = new_ver_str
            version.status = VersionStatus.DRAFT
            version.release_date = None
        else:
            new_ver_str = "0.1.0"
            existing = self._backend.get_version(model_name, new_ver_str)
            if existing is not None:
                # Auto-increment minor version
                counter = 1
                while existing is not None:
                    counter += 1
                    new_ver_str = f"0.{counter}.0"
                    existing = self._backend.get_version(model_name, new_ver_str)
            version = ModelVersion(version=new_ver_str)

        self._backend.save_version(model_name, version)
        self._backend.append_audit_event(
            AuditEvent(
                actor=actor,
                action="started_version",
                model_name=model_name,
                version=new_ver_str,
                details={"base": base},
            )
        )
        return DraftVersion(self, model_name, version, actor=actor)

    def get_version(self, model_name: str, version: str) -> ModelVersion | None:
        return self._backend.get_version(model_name, version)

    def publish(
        self, model_name: str, version: str, actor: str = "system"
    ) -> None:
        v = self._backend.get_version(model_name, version)
        if v is None:
            raise VersionNotFoundError(model_name, version)
        if v.status == VersionStatus.PUBLISHED:
            raise ImmutableVersionError(model_name, version)
        v.status = VersionStatus.PUBLISHED
        self._backend.force_save_version(model_name, v)
        self._backend.append_audit_event(
            AuditEvent(
                actor=actor,
                action="published_version",
                model_name=model_name,
                version=version,
                details={},
            )
        )

    def deprecate(
        self, model_name: str, version: str, actor: str = "system"
    ) -> None:
        v = self._backend.get_version(model_name, version)
        if v is None:
            raise VersionNotFoundError(model_name, version)
        v.status = VersionStatus.DEPRECATED
        self._backend.force_save_version(model_name, v)
        self._backend.append_audit_event(
            AuditEvent(
                actor=actor,
                action="deprecated_version",
                model_name=model_name,
                version=version,
                details={},
            )
        )

    def get_audit_log(
        self, model_name: str, version: str | None = None
    ) -> list[AuditEvent]:
        return self._backend.get_audit_log(model_name, version)
