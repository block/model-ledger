"""In-memory storage backend for testing."""

from __future__ import annotations

from model_ledger.core.enums import VersionStatus
from model_ledger.core.exceptions import ImmutableVersionError
from model_ledger.core.models import AuditEvent, Model, ModelVersion
from model_ledger.core.observations import (
    FeedbackEvent,
    Observation,
    ValidationReport,
    ValidationRun,
)


class InMemoryBackend:
    def __init__(self) -> None:
        self._models: dict[str, Model] = {}
        self._versions: dict[str, dict[str, ModelVersion]] = {}
        self._audit_log: list[AuditEvent] = []
        self._observations: dict[str, Observation] = {}
        self._validation_runs: dict[str, ValidationRun] = {}
        self._validation_reports: dict[str, ValidationReport] = {}
        self._feedback_events: list[FeedbackEvent] = []

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

    def save_observation(self, observation: Observation) -> None:
        self._observations[observation.observation_id] = observation

    def get_observation(self, observation_id: str) -> Observation | None:
        return self._observations.get(observation_id)

    def list_observations(self, model_version_ref: str | None = None) -> list[Observation]:
        obs = list(self._observations.values())
        if model_version_ref:
            obs = [o for o in obs if o.model_version_ref == model_version_ref]
        return obs

    def save_validation_run(self, run: ValidationRun) -> None:
        self._validation_runs[run.run_id] = run

    def get_validation_run(self, run_id: str) -> ValidationRun | None:
        return self._validation_runs.get(run_id)

    def save_validation_report(self, report: ValidationReport) -> None:
        self._validation_reports[report.report_id] = report

    def get_validation_report(self, report_id: str) -> ValidationReport | None:
        return self._validation_reports.get(report_id)

    def append_feedback_event(self, event: FeedbackEvent) -> None:
        self._feedback_events.append(event)

    def list_feedback_events(self, observation_ref: str | None = None) -> list[FeedbackEvent]:
        events = self._feedback_events
        if observation_ref:
            events = [e for e in events if e.observation_ref == observation_ref]
        return events
