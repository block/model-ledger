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
    DEVELOPMENT = "development"
    REVIEW = "review"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class VersionStatus(CaseInsensitiveEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
