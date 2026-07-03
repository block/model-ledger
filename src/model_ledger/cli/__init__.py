try:
    from model_ledger.cli.app import app
except ModuleNotFoundError as _exc:  # pragma: no cover — exercised only on bare installs
    if _exc.name not in {"typer", "rich"}:
        raise

    import sys

    def app() -> None:  # type: ignore[misc]
        """Fallback entry point when the CLI extra is not installed."""
        sys.stderr.write(
            "The model-ledger CLI requires the [cli] extra:\n\n"
            '    pip install "model-ledger[cli]"\n'
        )
        sys.exit(1)


__all__ = ["app"]
