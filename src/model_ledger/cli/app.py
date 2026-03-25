"""Typer CLI for model-ledger."""

from __future__ import annotations

import json
import os

import typer
from rich.console import Console
from rich.table import Table

from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.sdk.inventory import Inventory

app = typer.Typer(
    name="model-ledger",
    help="Developer-first model inventory and governance CLI.",
    no_args_is_help=True,
)
console = Console()


def _default_db() -> str:
    return os.environ.get("MODEL_LEDGER_DB", "inventory.db")


def _get_inventory(db: str) -> Inventory:
    return Inventory(db_path=db)


@app.command(name="list")
def list_models(
    db: str = typer.Option(default=None, help="Path to the inventory database."),
    format: str = typer.Option("table", help="Output format: table or json."),
) -> None:
    """List all registered models."""
    db = db or _default_db()
    inv = _get_inventory(db)
    models = inv.list_models()

    if format == "json":
        data = [
            {
                "name": m.name,
                "owner": m.owner,
                "tier": m.tier.value,
                "status": m.status.value,
                "model_type": m.model_type.value,
                "intended_purpose": m.intended_purpose,
            }
            for m in models
        ]
        typer.echo(json.dumps(data, indent=2))
        return

    if not models:
        console.print("[dim]No models registered.[/dim]")
        return

    table = Table(title="Model Inventory")
    table.add_column("Name", style="bold cyan")
    table.add_column("Owner")
    table.add_column("Tier")
    table.add_column("Status")
    table.add_column("Type")

    for m in models:
        table.add_row(m.name, m.owner, m.tier.value, m.status.value, m.model_type.value)

    console.print(table)


@app.command(name="show")
def show_model(
    model_name: str = typer.Argument(help="Name of the model to show."),
    db: str = typer.Option(default=None, help="Path to the inventory database."),
    format: str = typer.Option("table", help="Output format: table or json."),
) -> None:
    """Show details for a specific model."""
    db = db or _default_db()
    inv = _get_inventory(db)

    try:
        model = inv.get_model(model_name)
    except ModelNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None

    versions = inv._backend.list_versions(model_name)

    if format == "json":
        data = model.model_dump(mode="json")
        data["versions_on_disk"] = [v.model_dump(mode="json") for v in versions]
        typer.echo(json.dumps(data, indent=2, default=str))
        return

    table = Table(title=f"Model: {model.name}")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Name", model.name)
    table.add_row("Owner", model.owner)
    table.add_row("Tier", model.tier.value)
    table.add_row("Status", model.status.value)
    table.add_row("Type", model.model_type.value)
    table.add_row("Purpose", model.intended_purpose)
    table.add_row("Developers", ", ".join(model.developers) if model.developers else "-")
    table.add_row("Validator", model.validator or "-")
    table.add_row("Business Unit", model.business_unit or "-")
    table.add_row("Vendor", model.vendor or "-")
    table.add_row("Tags", ", ".join(model.tags) if model.tags else "-")
    table.add_row("Versions", str(len(versions)))

    console.print(table)


@app.command(name="validate")
def validate_cmd(
    model_name: str = typer.Argument(help="Name of the model to validate."),
    db: str = typer.Option(default=None, help="Path to the inventory database."),
    version: str | None = typer.Option(None, help="Version to validate. Defaults to latest."),
    profile: str = typer.Option("sr_11_7", help="Validation profile to use."),
    format: str = typer.Option("table", help="Output format: table or json."),
) -> None:
    """Validate a model version against a compliance profile."""
    db = db or _default_db()
    inv = _get_inventory(db)

    try:
        model = inv.get_model(model_name)
    except ModelNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None

    # Resolve version
    if version is None:
        versions = inv._backend.list_versions(model_name)
        if not versions:
            console.print(f"[red]Error:[/red] No versions found for '{model_name}'.")
            raise typer.Exit(code=1)
        ver = versions[-1]
    else:
        ver = inv.get_version(model_name, version)
        if ver is None:
            console.print(f"[red]Error:[/red] Version '{version}' not found for '{model_name}'.")
            raise typer.Exit(code=1)

    from model_ledger.validate.engine import validate

    result = validate(model, ver, profile=profile)

    if format == "json":
        data = {
            "model_name": result.model_name,
            "profile": result.profile,
            "passed": result.passed,
            "errors": len(result.errors),
            "warnings": len(result.warnings),
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "message": v.message,
                    "suggestion": v.suggestion,
                }
                for v in result.violations
            ],
        }
        typer.echo(json.dumps(data, indent=2))
        exit_code = 0 if result.passed else 1
        raise typer.Exit(code=exit_code)

    # Rich table output
    status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
    console.print(f"\n{status}: {model_name} [{profile}]")

    if not result.violations:
        console.print("  [green]All rules satisfied[/green]")
    else:
        table = Table()
        table.add_column("Severity", style="bold")
        table.add_column("Rule")
        table.add_column("Message")
        table.add_column("Suggestion")

        for v in result.violations:
            severity_style = "red" if v.severity == "error" else "yellow"
            table.add_row(
                f"[{severity_style}]{v.severity.upper()}[/{severity_style}]",
                v.rule_id,
                v.message,
                v.suggestion,
            )
        console.print(table)

    exit_code = 0 if result.passed else 1
    raise typer.Exit(code=exit_code)


@app.command(name="audit-log")
def audit_log(
    model_name: str = typer.Argument(help="Name of the model."),
    db: str = typer.Option(default=None, help="Path to the inventory database."),
    version: str | None = typer.Option(None, help="Filter to a specific version."),
    format: str = typer.Option("table", help="Output format: table or json."),
) -> None:
    """Show the audit log for a model."""
    db = db or _default_db()
    inv = _get_inventory(db)

    try:
        inv.get_model(model_name)
    except ModelNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None

    events = inv.get_audit_log(model_name, version)

    if format == "json":
        data = [e.model_dump(mode="json") for e in events]
        typer.echo(json.dumps(data, indent=2, default=str))
        return

    if not events:
        console.print("[dim]No audit events found.[/dim]")
        return

    table = Table(title=f"Audit Log: {model_name}")
    table.add_column("Timestamp", style="dim")
    table.add_column("Actor")
    table.add_column("Action", style="bold")
    table.add_column("Version")
    table.add_column("Details")

    for e in events:
        table.add_row(
            str(e.timestamp),
            e.actor,
            e.action,
            e.version or "-",
            json.dumps(e.details) if e.details else "-",
        )

    console.print(table)


@app.command(name="export")
def export_cmd(
    model_name: str = typer.Argument(help="Name of the model to export."),
    db: str = typer.Option(default=None, help="Path to the inventory database."),
    version: str | None = typer.Option(None, help="Version to export. Defaults to latest."),
    output: str = typer.Option("audit_pack", help="Output directory for the audit pack."),
) -> None:
    """Export an audit pack for a model version."""
    db = db or _default_db()
    inv = _get_inventory(db)

    try:
        inv.get_model(model_name)
    except ModelNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None

    # Resolve version
    if version is None:
        versions = inv._backend.list_versions(model_name)
        if not versions:
            console.print(f"[red]Error:[/red] No versions found for '{model_name}'.")
            raise typer.Exit(code=1)
        version = versions[-1].version

    try:
        from model_ledger.export.audit_pack import export_audit_pack

        export_audit_pack(inv, model_name, version, output_dir=output)
        console.print(f"[green]Audit pack exported to {output}/[/green]")
    except (ImportError, AttributeError):
        console.print(
            f"[yellow]Export not yet implemented.[/yellow] "
            f"Would export audit pack for {model_name} v{version} to {output}/"
        )


@app.command(name="introspect")
def introspect_cmd(
    artifact_path: str = typer.Argument(help="Path to a serialized model artifact."),
    db: str = typer.Option(default=None, help="Path to the inventory database."),
    model_name: str | None = typer.Option(None, help="Model name to attach results to."),
    allow_pickle: bool = typer.Option(False, "--allow-pickle", help="Allow loading pickle files."),
    format: str = typer.Option("table", help="Output format: table or json."),
) -> None:
    """Introspect a serialized model artifact."""
    db = db or _default_db()

    if not allow_pickle:
        console.print(
            "[red]Error:[/red] Loading serialized artifacts requires --allow-pickle flag. "
            "Pickle files can execute arbitrary code."
        )
        raise typer.Exit(code=1)

    import pickle
    from pathlib import Path

    path = Path(artifact_path)
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {artifact_path}")
        raise typer.Exit(code=1)

    try:
        with open(path, "rb") as f:
            obj = pickle.load(f)  # noqa: S301
    except Exception as e:
        console.print(f"[red]Error loading artifact:[/red] {e}")
        raise typer.Exit(code=1) from None

    from model_ledger.introspect.registry import get_registry

    registry = get_registry()
    try:
        intro = registry.find(obj)
        result = intro.introspect(obj)
    except Exception as e:
        console.print(f"[red]Error during introspection:[/red] {e}")
        raise typer.Exit(code=1) from None

    if format == "json":
        typer.echo(json.dumps(result.model_dump(), indent=2, default=str))
        return

    console.print("\n[bold]Introspection Result[/bold]")
    console.print(f"  Introspector: {result.introspector}")
    if result.framework:
        console.print(f"  Framework: {result.framework}")
    if result.algorithm:
        console.print(f"  Algorithm: {result.algorithm}")
    if result.features:
        console.print(f"  Features: {len(result.features)}")
    if result.hyperparameters:
        console.print(f"  Hyperparameters: {json.dumps(result.hyperparameters, default=str)}")

    # Optionally attach to model
    if model_name:
        inv = _get_inventory(db)
        try:
            inv.get_model(model_name)
            versions = inv._backend.list_versions(model_name)
            if versions:
                console.print(
                    f"\n[dim]Introspection result available. "
                    f"Use the SDK to attach to {model_name}.[/dim]"
                )
        except ModelNotFoundError:
            console.print(f"[yellow]Warning:[/yellow] Model '{model_name}' not found in inventory.")
