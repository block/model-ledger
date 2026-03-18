"""In-memory storage backend for testing."""

from __future__ import annotations

from model_ledger.core.enums import VersionStatus
from model_ledger.core.exceptions import ImmutableVersionError
from model_ledger.core.models import AuditEvent, Model, ModelVersion


class InMemoryBackend:
    def __init__(self) -> None:
        self._models: dict[str, Model] = {}
        self._versions: dict[str, dict[str, ModelVersion]] = {}
        self._audit_log: list[AuditEvent] = []

    def save_model(self, model: Model) -> None:
        self._models[model.name] = model

    def get_model(self, name: str) -> Model | None:
        return self._models.get(name)

    def list_models(self) -> list[Model]:
        return list(self._models.values())

    def save_version(self, model_name: str, version: ModelVersion) -> None:
        versions = self._versions.setdefault(model_name, {})
        existing = versions.get(version.version)
        if existing is not None and existing.status == VersionStatus.PUBLISHED:
            raise ImmutableVersionError(model_name, version.version)
        versions[version.version] = version

    def force_save_version(self, model_name: str, version: ModelVersion) -> None:
        self._versions.setdefault(model_name, {})[version.version] = version

    def get_version(self, model_name: str, version: str) -> ModelVersion | None:
        return self._versions.get(model_name, {}).get(version)

    def append_audit_event(self, event: AuditEvent) -> None:
        self._audit_log.append(event)

    def get_audit_log(
        self, model_name: str, version: str | None = None
    ) -> list[AuditEvent]:
        events = [e for e in self._audit_log if e.model_name == model_name]
        if version is not None:
            events = [e for e in events if e.version == version]
        return events
