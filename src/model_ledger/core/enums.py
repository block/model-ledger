"""Core enums with case-insensitive coercion for developer convenience."""

from enum import Enum


class CaseInsensitiveEnum(str, Enum):
    """Base enum that accepts any case variation of the value."""

    @classmethod
    def _missing_(cls, value: object) -> "CaseInsensitiveEnum | None":
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None


class ModelType(CaseInsensitiveEnum):
    ML_MODEL = "ml_model"
    HEURISTIC = "heuristic"
    VENDOR = "vendor"
    LLM = "llm"
    SPREADSHEET = "spreadsheet"


class RiskTier(CaseInsensitiveEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ModelStatus(CaseInsensitiveEnum):
    """Lifecycle state of a model, in lifecycle order.

    ``SHADOW`` and ``DISABLED`` sit between ``ACTIVE`` and ``DEPRECATED``:
    both describe a model that still exists at its source but is not acting
    on production decisions. A shadow model is deployed and evaluated but
    takes no action; a disabled model has been switched off and can be
    re-enabled. ``DEPRECATED`` and ``RETIRED`` remain the terminal states.
    """

    DEVELOPMENT = "development"
    REVIEW = "review"
    ACTIVE = "active"
    SHADOW = "shadow"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class VersionStatus(CaseInsensitiveEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
