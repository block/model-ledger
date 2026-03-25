"""Exception hierarchy with actionable error messages."""


class ModelInventoryError(Exception):
    """Base exception for all model-ledger errors."""


class ModelNotFoundError(ModelInventoryError):
    """Raised when a model is not found in the inventory."""

    def __init__(self, name: str, known: list[str] | None = None):
        known_str = f" Known models: {known}" if known else ""
        super().__init__(f"No model named '{name}'.{known_str}")


class VersionNotFoundError(ModelInventoryError):
    """Raised when a version is not found."""

    def __init__(self, model_name: str, version: str):
        super().__init__(
            f"No version '{version}' for model '{model_name}'. "
            f"Use inv.new_version('{model_name}') to create one."
        )


class ImmutableVersionError(ModelInventoryError):
    """Raised when trying to modify a published version."""

    def __init__(self, model_name: str, version: str):
        super().__init__(
            f"Version '{version}' of '{model_name}' is published and immutable. "
            f"Create a new version with inv.new_version('{model_name}', base='{version}')."
        )


class ValidationError(ModelInventoryError):
    """Raised when validation fails."""


class StorageError(ModelInventoryError):
    """Raised when the storage backend encounters an error."""


class NoIntrospectorError(ModelInventoryError):
    """Raised when no introspector can handle the given object."""

    def __init__(self, target: type | str) -> None:
        self.target = target
        label = target.__name__ if isinstance(target, type) else target
        super().__init__(f"No introspector found for {label}")
