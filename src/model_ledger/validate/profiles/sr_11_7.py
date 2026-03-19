"""SR 11-7 compliance profile.

Based on Federal Reserve SR 11-7, OCC 2021 Handbook, and examination practice.
"""

from __future__ import annotations

from model_ledger.core.enums import RiskTier
from model_ledger.core.models import Model, ModelVersion
from model_ledger.validate.engine import ValidationResult, Violation, register_profile


@register_profile("sr_11_7")
class SR117Profile:
    """SR 11-7 compliance validation profile."""

    def validate(self, model: Model, version: ModelVersion) -> ValidationResult:
        result = ValidationResult(model_name=model.name, profile="sr_11_7")

        self._check_has_developers(model, result)
        self._check_has_validator(model, result)
        self._check_validator_independence(model, result)
        self._check_has_ipo_structure(version, result)
        self._check_has_governance_document(version, result)
        self._check_has_validation_schedule(model, version, result)

        return result

    def _check_has_developers(self, model: Model, result: ValidationResult) -> None:
        if not model.developers:
            result.violations.append(
                Violation(
                    rule_id="has_developers",
                    severity="error",
                    message="Model has no developers listed.",
                    suggestion="Set developers=['name'] when registering the model.",
                )
            )

    def _check_has_validator(self, model: Model, result: ValidationResult) -> None:
        if not model.validator:
            result.violations.append(
                Violation(
                    rule_id="has_validator",
                    severity="error",
                    message="Model has no independent validator assigned.",
                    suggestion="Set validator='name' when registering the model.",
                )
            )

    def _check_validator_independence(
        self, model: Model, result: ValidationResult
    ) -> None:
        if (
            model.validator
            and model.developers
            and model.validator in model.developers
        ):
            result.violations.append(
                Violation(
                    rule_id="validator_independence",
                    severity="error",
                    message=f"Validator '{model.validator}' is also listed as a developer. "
                    "SR 11-7 requires independent validation.",
                    suggestion="Assign a validator who is not part of the development team.",
                )
            )

    def _check_has_ipo_structure(
        self, version: ModelVersion, result: ValidationResult
    ) -> None:
        top_names = {c.name for c in version.tree.children}
        required = {"Inputs", "Processing", "Outputs"}
        missing = required - top_names
        if missing:
            result.violations.append(
                Violation(
                    rule_id="has_ipo_structure",
                    severity="error",
                    message=f"Component tree missing required sections: {missing}. "
                    "SR 11-7 requires Input, Processing, and Output components.",
                    suggestion="Use v.add_component('inputs/...') to populate the tree.",
                )
            )

    def _check_has_governance_document(
        self, version: ModelVersion, result: ValidationResult
    ) -> None:
        if not version.documents:
            result.violations.append(
                Violation(
                    rule_id="has_governance_document",
                    severity="error",
                    message="No governance documents attached to this version.",
                    suggestion="Use v.add_document(doc_type='system_design', title='...') "
                    "to attach a CSD or model specification.",
                )
            )

    def _check_has_validation_schedule(
        self, model: Model, version: ModelVersion, result: ValidationResult
    ) -> None:
        if version.next_validation_due is None:
            severity = "error" if model.tier == RiskTier.HIGH else "warning"
            result.violations.append(
                Violation(
                    rule_id="has_validation_schedule",
                    severity=severity,
                    message="No next validation date set."
                    + (" High-tier models require a validation schedule." if severity == "error" else ""),
                    suggestion="Use v.set_next_validation_due('2027-01-01') to set the date.",
                )
            )
