"""DraftVersion — context manager for building a model version."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from model_ledger.core.models import (
    ComponentNode,
    Evidence,
    GovernanceDoc,
    ModelArtifact,
    ModelVersion,
    Reference,
)

if TYPE_CHECKING:
    from model_ledger.sdk.inventory import Inventory


class DraftVersion:
    """Context manager for building a model version draft.

    All mutations happen on this object. Auto-saves on context exit.
    Does NOT auto-publish.
    """

    def __init__(
        self,
        inventory: Inventory,
        model_name: str,
        version: ModelVersion,
        actor: str = "system",
    ) -> None:
        self._inv = inventory
        self._model_name = model_name
        self._version = version
        self._actor = actor
        self._saved = False

    @property
    def version_str(self) -> str:
        return self._version.version

    def add_component(
        self, path: str, *, type: str, metadata: dict[str, Any] | None = None
    ) -> None:
        parts = path.split("/")
        parent = self._version.tree
        for part in parts[:-1]:
            found = next((c for c in parent.children if c.name.lower() == part.lower()), None)
            if found is None:
                found = ComponentNode(name=part, node_type="category")
                parent.children.append(found)
            parent = found
        parent.children.append(
            ComponentNode(
                name=parts[-1],
                node_type=type,
                path=path,
                metadata=metadata or {},
            )
        )

    def add_document(self, *, doc_type: str, title: str, url: str | None = None) -> None:
        self._version.documents.append(GovernanceDoc(doc_type=doc_type, title=title, url=url))

    def add_reference(
        self,
        ref_type: str,
        *,
        identifier: str,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._version.references.append(
            Reference(
                ref_type=ref_type,
                identifier=identifier,
                url=url,
                metadata=metadata or {},
            )
        )

    def add_evidence(
        self,
        evidence_type: str,
        *,
        title: str,
        artifact_uri: str | None = None,
    ) -> None:
        self._version.evidence.append(
            Evidence(evidence_type=evidence_type, title=title, artifact_uri=artifact_uri)
        )

    def add_artifact(self, *, artifact_type: str, uri: str, checksum: str | None = None) -> None:
        self._version.artifacts.append(
            ModelArtifact(artifact_type=artifact_type, uri=uri, checksum=checksum)
        )

    def set_training_target(self, target: str) -> None:
        self._version.training_target = target

    def set_run_frequency(self, frequency: str) -> None:
        self._version.run_frequency = frequency

    def set_next_validation_due(self, due_date: str | date) -> None:
        if isinstance(due_date, str):
            due_date = date.fromisoformat(due_date)
        self._version.next_validation_due = due_date

    def introspect(self, obj: Any, *, introspector: str | None = None) -> Any:
        """Introspect a model object and apply extracted metadata to this version.

        Auto-detects the appropriate introspector plugin, extracts metadata
        (algorithm, features, hyperparameters, data sources), and maps it
        onto the version's fields and component tree.

        Args:
            obj: A fitted model object or config to introspect.
            introspector: Optional name of a specific introspector to use.

        Returns:
            IntrospectionResult with all extracted metadata.
        """
        from model_ledger.introspect.registry import get_registry

        registry = get_registry()
        intro = registry.get_by_name(introspector) if introspector else registry.find(obj)
        result = intro.introspect(obj)
        self._apply_result(result)
        return result

    def _apply_result(self, result: Any) -> None:
        """Map IntrospectionResult onto version fields and component tree."""
        if result.algorithm:
            self._version.methodology_approach = result.algorithm
        if result.features:
            self.add_component(
                "Inputs/features",
                type="feature_set",
                metadata={
                    "count": len(result.features),
                    "features": [f.model_dump() for f in result.features],
                },
            )
        if result.thresholds:
            self.add_component(
                "Processing/thresholds",
                type="threshold_set",
                metadata={"thresholds": [t.model_dump() for t in result.thresholds]},
            )
        if result.data_sources:
            for ds in result.data_sources:
                self.add_component(
                    f"Inputs/{ds.name}", type="data_source", metadata=ds.model_dump()
                )
        if result.execution_schedule:
            self.set_run_frequency(result.execution_schedule)
        self._version.artifacts.append(
            ModelArtifact(
                artifact_type="introspection_result",
                uri=f"introspect://{result.introspector}",
            )
        )

    def validate(self, profile: str = "sr_11_7"):
        from model_ledger.validate.engine import validate

        model = self._inv.get_model(self._model_name)
        return validate(model, self._version, profile=profile)

    def _save(self) -> None:
        self._inv._backend.save_version(self._model_name, self._version)
        self._saved = True

    def __enter__(self) -> DraftVersion:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._saved:
            self._save()
