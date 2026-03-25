"""EU AI Act compliance profile.

Based on EU AI Act (Regulation 2024/1689), Annex IV documentation requirements,
and Article 9 risk management requirements for high-risk AI systems.
"""

from __future__ import annotations

from model_ledger.core.enums import RiskTier
from model_ledger.core.models import Model, ModelVersion
from model_ledger.validate.engine import ValidationResult, Violation, register_profile


@register_profile("eu_ai_act")
class EUAIActProfile:
    """EU AI Act compliance validation profile.

    Covers Annex IV (technical documentation), Article 9 (risk management),
    Article 10 (data governance), Article 13 (transparency), and Article 15
    (accuracy, robustness, cybersecurity).
    """

    def validate(self, model: Model, version: ModelVersion) -> ValidationResult:
        result = ValidationResult(model_name=model.name, profile="eu_ai_act")

        self._check_intended_purpose(model, result)
        self._check_risk_assessment(model, result)
        self._check_affected_populations(model, result)
        self._check_data_governance(version, result)
        self._check_transparency(model, version, result)
        self._check_human_oversight(model, result)
        self._check_accuracy_metrics(version, result)
        self._check_assumptions_and_limitations(model, result)
        self._check_operating_boundaries(model, result)

        return result

    def _check_intended_purpose(self, model: Model, result: ValidationResult) -> None:
        if not model.intended_purpose or len(model.intended_purpose) < 20:
            result.violations.append(
                Violation(
                    rule_id="eu_intended_purpose",
                    severity="error",
                    message="Annex IV(1)(a): Intended purpose must be clearly described. "
                    "Current description is missing or too brief.",
                    suggestion="Provide a detailed intended_purpose describing what the system "
                    "does, who uses it, and in what context.",
                )
            )

    def _check_risk_assessment(self, model: Model, result: ValidationResult) -> None:
        if model.risk_rating is None:
            result.violations.append(
                Violation(
                    rule_id="eu_risk_assessment",
                    severity="error",
                    message="Article 9: High-risk AI systems require a risk management system. "
                    "No risk rating has been assigned.",
                    suggestion="Set risk_rating with ModelRiskRating(model_exposure=..., "
                    "output_reliance=..., model_complexity=..., input_uncertainty=...).",
                )
            )

    def _check_affected_populations(self, model: Model, result: ValidationResult) -> None:
        if not model.affected_populations:
            severity = "error" if model.tier == RiskTier.HIGH else "warning"
            result.violations.append(
                Violation(
                    rule_id="eu_affected_populations",
                    severity=severity,
                    message="Annex IV(2)(g): Must identify groups of persons likely to be affected. "
                    "No affected populations documented.",
                    suggestion="Set affected_populations=['consumers', 'merchants', ...] "
                    "identifying who the model's decisions impact.",
                )
            )

    def _check_data_governance(self, version: ModelVersion, result: ValidationResult) -> None:
        if not version.training_data_description:
            result.violations.append(
                Violation(
                    rule_id="eu_data_governance",
                    severity="error",
                    message="Article 10: Training data must be documented with governance measures. "
                    "No training data description provided.",
                    suggestion="Describe the training data: source, size, collection method, "
                    "preprocessing steps, and any known biases.",
                )
            )

    def _check_transparency(
        self, model: Model, version: ModelVersion, result: ValidationResult
    ) -> None:
        if not version.documents:
            result.violations.append(
                Violation(
                    rule_id="eu_transparency_docs",
                    severity="error",
                    message="Article 13: System must be sufficiently transparent. "
                    "No documentation attached to this version.",
                    suggestion="Attach governance documents: system design, model specification, "
                    "or conceptual soundness document.",
                )
            )
        if not model.description:
            result.violations.append(
                Violation(
                    rule_id="eu_transparency_description",
                    severity="warning",
                    message="Article 13: Model should have a clear description for transparency.",
                    suggestion="Set description='...' with a plain-language explanation of "
                    "what the model does and how it works.",
                )
            )

    def _check_human_oversight(self, model: Model, result: ValidationResult) -> None:
        if not model.stakeholders:
            result.violations.append(
                Violation(
                    rule_id="eu_human_oversight",
                    severity="warning",
                    message="Article 14: High-risk systems must have human oversight measures. "
                    "No stakeholders documented.",
                    suggestion="Add stakeholders with defined roles (e.g., model owner, "
                    "compliance officer, human reviewer).",
                )
            )

    def _check_accuracy_metrics(self, version: ModelVersion, result: ValidationResult) -> None:
        has_metrics = any(
            c.node_type in ("metric", "metrics", "performance")
            for c in self._walk_tree(version.tree)
        )
        has_evidence = any(e.evidence_type == "performance_report" for e in version.evidence)

        if not has_metrics and not has_evidence:
            result.violations.append(
                Violation(
                    rule_id="eu_accuracy_metrics",
                    severity="warning",
                    message="Article 15: Accuracy, robustness, and cybersecurity levels must be "
                    "documented. No performance metrics or evidence found.",
                    suggestion="Add performance evidence: v.add_evidence('performance_report', "
                    "title='Model Performance Report').",
                )
            )

    def _check_assumptions_and_limitations(self, model: Model, result: ValidationResult) -> None:
        if not model.assumptions_and_limitations:
            result.violations.append(
                Violation(
                    rule_id="eu_limitations",
                    severity="warning",
                    message="Annex IV(2)(f): Known limitations must be documented.",
                    suggestion="Set assumptions_and_limitations=['...'] describing known "
                    "constraints, edge cases, and conditions under which performance degrades.",
                )
            )

    def _check_operating_boundaries(self, model: Model, result: ValidationResult) -> None:
        if not model.operating_boundaries:
            result.violations.append(
                Violation(
                    rule_id="eu_operating_boundaries",
                    severity="warning",
                    message="Annex IV(2)(b): Operating conditions and boundaries must be specified.",
                    suggestion="Set operating_boundaries='...' describing the conditions "
                    "under which the model is designed to operate.",
                )
            )

    @staticmethod
    def _walk_tree(node):
        """Recursively walk the component tree."""
        yield node
        for child in node.children:
            yield from EUAIActProfile._walk_tree(child)
