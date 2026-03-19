"""Validation engine with profile-based compliance checking."""

from __future__ import annotations

from dataclasses import dataclass, field

from model_ledger.core.models import Model, ModelVersion


@dataclass(frozen=True)
class Violation:
    rule_id: str
    severity: str  # "error" | "warning" | "info"
    message: str
    suggestion: str


@dataclass
class ValidationResult:
    model_name: str
    profile: str
    violations: list[Violation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    @property
    def errors(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warnings(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "warning"]

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        total = len(self.violations)
        err_count = len(self.errors)
        warn_count = len(self.warnings)
        lines = [f"{status}: {self.model_name} [{self.profile}]"]
        if err_count:
            lines.append(f"  Errors: {err_count}")
        if warn_count:
            lines.append(f"  Warnings: {warn_count}")
        if total == 0:
            lines.append("  All rules satisfied")
        for v in self.violations:
            lines.append(f"  [{v.severity.upper()}] {v.rule_id}: {v.message}")
        return "\n".join(lines)


_PROFILES: dict[str, type] = {}


def register_profile(name: str):
    def decorator(cls):
        _PROFILES[name] = cls
        return cls
    return decorator


def validate(
    model: Model, version: ModelVersion, *, profile: str = "sr_11_7"
) -> ValidationResult:
    if profile not in _PROFILES:
        raise ValueError(
            f"Unknown profile '{profile}'. Available: {list(_PROFILES.keys())}"
        )
    checker = _PROFILES[profile]()
    return checker.validate(model, version)


# Import profiles to trigger registration
from model_ledger.validate.profiles import sr_11_7 as _sr_11_7  # noqa: E402, F401
