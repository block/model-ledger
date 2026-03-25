"""NIST AI Risk Management Framework (AI RMF 1.0) compliance profile.

Based on NIST AI 100-1, covering the four core functions:
GOVERN, MAP, MEASURE, MANAGE.
"""

from __future__ import annotations

from model_ledger.core.enums import RiskTier
from model_ledger.core.models import Model, ModelVersion
from model_ledger.validate.engine import ValidationResult, Violation, register_profile


@register_profile("nist_ai_rmf")
class NISTAIRMFProfile:
    """NIST AI Risk Management Framework compliance validation profile.

    Validates against the four core functions:
    - GOVERN: Organizational governance and accountability
    - MAP: Context and risk identification
    - MEASURE: Analysis and assessment
    - MANAGE: Risk treatment and monitoring
    """

    def validate(self, model: Model, version: ModelVersion) -> ValidationResult:
        result = ValidationResult(model_name=model.name, profile="nist_ai_rmf")

        # GOVERN function
        self._check_governance_accountability(model, result)
        self._check_governance_documentation(version, result)

        # MAP function
        self._check_map_intended_use(model, result)
        self._check_map_risk_identification(model, result)
        self._check_map_stakeholders(model, result)

        # MEASURE function
        self._check_measure_performance(version, result)
        self._check_measure_bias(model, version, result)

        # MANAGE function
        self._check_manage_monitoring(version, result)
        self._check_manage_incident_response(model, version, result)

        return result

    # --- GOVERN ---

    def _check_governance_accountability(self, model: Model, result: ValidationResult) -> None:
        if not model.owner:
            result.violations.append(
                Violation(
                    rule_id="nist_govern_accountability",
                    severity="error",
                    message="GOVERN 1.1: AI risk management roles and responsibilities must be defined. "
                    "No model owner assigned.",
                    suggestion="Set owner='name' when registering the model.",
                )
            )
        if not model.developers:
            result.violations.append(
                Violation(
                    rule_id="nist_govern_developers",
                    severity="error",
                    message="GOVERN 1.2: Development team must be identified for accountability.",
                    suggestion="Set developers=['name'] when registering the model.",
                )
            )

    def _check_governance_documentation(
        self, version: ModelVersion, result: ValidationResult
    ) -> None:
        if not version.documents:
            result.violations.append(
                Violation(
                    rule_id="nist_govern_documentation",
                    severity="error",
                    message="GOVERN 4.1: Documentation practices must enable traceability. "
                    "No governance documents attached.",
                    suggestion="Attach system design, model spec, or validation report.",
                )
            )

    # --- MAP ---

    def _check_map_intended_use(self, model: Model, result: ValidationResult) -> None:
        if not model.intended_purpose:
            result.violations.append(
                Violation(
                    rule_id="nist_map_intended_use",
                    severity="error",
                    message="MAP 1.1: Intended purpose and context of use must be clearly defined.",
                    suggestion="Set intended_purpose describing the use case and deployment context.",
                )
            )
        if not model.restrictions_on_use:
            result.violations.append(
                Violation(
                    rule_id="nist_map_restrictions",
                    severity="warning",
                    message="MAP 1.5: Restrictions on use should be documented.",
                    suggestion="Set restrictions_on_use=['...'] listing prohibited uses.",
                )
            )

    def _check_map_risk_identification(self, model: Model, result: ValidationResult) -> None:
        if model.risk_rating is None and model.tier == RiskTier.HIGH:
            result.violations.append(
                Violation(
                    rule_id="nist_map_risk_id",
                    severity="error",
                    message="MAP 2.1: AI risks must be identified and documented. "
                    "High-tier model has no risk rating.",
                    suggestion="Assign a ModelRiskRating to quantify risk dimensions.",
                )
            )
        if not model.potential_harms:
            result.violations.append(
                Violation(
                    rule_id="nist_map_harms",
                    severity="warning",
                    message="MAP 2.2: Potential harms should be enumerated.",
                    suggestion="Set potential_harms=['...'] identifying possible negative impacts.",
                )
            )

    def _check_map_stakeholders(self, model: Model, result: ValidationResult) -> None:
        if not model.affected_populations:
            result.violations.append(
                Violation(
                    rule_id="nist_map_stakeholders",
                    severity="warning",
                    message="MAP 3.1: Affected individuals and communities should be identified.",
                    suggestion="Set affected_populations=['...'] identifying impacted groups.",
                )
            )

    # --- MEASURE ---

    def _check_measure_performance(self, version: ModelVersion, result: ValidationResult) -> None:
        has_evidence = bool(version.evidence)
        has_metrics_component = any(
            c.node_type in ("metric", "metrics", "performance")
            for c in self._walk_tree(version.tree)
        )
        if not has_evidence and not has_metrics_component:
            result.violations.append(
                Violation(
                    rule_id="nist_measure_performance",
                    severity="error",
                    message="MEASURE 2.1: AI system performance must be evaluated. "
                    "No performance evidence or metrics found.",
                    suggestion="Add evidence: v.add_evidence('performance_report', title='...').",
                )
            )

    def _check_measure_bias(
        self, model: Model, version: ModelVersion, result: ValidationResult
    ) -> None:
        has_bias_evidence = any(
            "bias" in e.evidence_type.lower() or "fairness" in e.evidence_type.lower()
            for e in version.evidence
        )
        has_bias_doc = any(
            "bias" in d.title.lower()
            or "fairness" in d.title.lower()
            or "fair_lending" in d.doc_type.lower()
            for d in version.documents
        )
        if model.tier == RiskTier.HIGH and not has_bias_evidence and not has_bias_doc:
            result.violations.append(
                Violation(
                    rule_id="nist_measure_bias",
                    severity="warning",
                    message="MEASURE 2.6: Bias and fairness assessments should be conducted "
                    "for high-tier models.",
                    suggestion="Add bias assessment evidence or fair lending documentation.",
                )
            )

    # --- MANAGE ---

    def _check_manage_monitoring(self, version: ModelVersion, result: ValidationResult) -> None:
        if not version.monitoring_frequency and not version.monitoring_status:
            result.violations.append(
                Violation(
                    rule_id="nist_manage_monitoring",
                    severity="warning",
                    message="MANAGE 2.1: Ongoing monitoring plans should be established.",
                    suggestion="Set monitoring_frequency and monitoring_status on the version.",
                )
            )
        if version.next_validation_due is None:
            result.violations.append(
                Violation(
                    rule_id="nist_manage_validation_schedule",
                    severity="warning",
                    message="MANAGE 2.4: Periodic re-evaluation schedule should be defined.",
                    suggestion="Use v.set_next_validation_due('YYYY-MM-DD').",
                )
            )

    def _check_manage_incident_response(
        self, model: Model, version: ModelVersion, result: ValidationResult
    ) -> None:
        has_incident_plan = any(
            d.doc_type in ("incident_response", "runbook", "escalation_plan")
            for d in version.documents
        )
        if model.tier == RiskTier.HIGH and not has_incident_plan:
            result.violations.append(
                Violation(
                    rule_id="nist_manage_incident_response",
                    severity="warning",
                    message="MANAGE 4.1: Incident response plans should exist for high-tier models.",
                    suggestion="Attach an incident_response or runbook document.",
                )
            )

    @staticmethod
    def _walk_tree(node):
        """Recursively walk the component tree."""
        yield node
        for child in node.children:
            yield from NISTAIRMFProfile._walk_tree(child)
