"""Audit pack export — self-contained compliance artifacts in HTML, JSON, and Markdown."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import model_ledger
from model_ledger.export.templates import (
    EVENT_CARD,
    EXEC_SUMMARY_SECTION,
    HTML_TEMPLATE,
    VALIDATION_FAIL_HEADER,
    VALIDATION_PASS,
    VIOLATION_ROW,
)


def export_audit_pack(
    *,
    inventory: Any,
    model_name: str,
    version: str | None = None,
    format: str = "html",
    output_path: str,
) -> None:
    """Export a self-contained audit pack for a model.

    Args:
        inventory: An Inventory instance.
        model_name: The registered model name.
        version: Specific version string. If None, uses the latest version.
        format: One of "html", "json", or "markdown".
        output_path: File path for the output artifact.
    """
    data = _gather_data(inventory, model_name, version)

    writers = {
        "json": _write_json,
        "html": _write_html,
        "markdown": _write_markdown,
    }
    writer = writers.get(format)
    if writer is None:
        raise ValueError(f"Unsupported format '{format}'. Choose from: {list(writers.keys())}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    writer(data, output)


def _gather_data(
    inventory: Any,
    model_name: str,
    version_str: str | None,
) -> dict[str, Any]:
    """Collect model, version, validation, and audit trail into a single dict."""
    model = inventory.get_model(model_name)

    # Resolve version
    if version_str is not None:
        version_obj = inventory.get_version(model_name, version_str)
    else:
        versions = inventory._backend.list_versions(model_name)
        version_obj = versions[-1] if versions else None

    # Run validation if we have a version
    validation_data: dict[str, Any] | None = None
    if version_obj is not None:
        try:
            from model_ledger.validate.engine import validate

            result = validate(model, version_obj, profile="sr_11_7")
            validation_data = {
                "profile": result.profile,
                "passed": result.passed,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
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
        except Exception:
            validation_data = None

    # Audit trail
    audit_events = inventory.get_audit_log(model_name)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Component tree
    component_tree = None
    if version_obj is not None:
        component_tree = _tree_to_dict(version_obj.tree)

    return {
        "model": {
            "name": model.name,
            "owner": model.owner,
            "tier": model.tier.value,
            "status": model.status.value,
            "model_type": model.model_type.value,
            "intended_purpose": model.intended_purpose,
            "description": model.description,
            "business_unit": model.business_unit,
            "vendor": model.vendor,
        },
        "version": _version_to_dict(version_obj) if version_obj else None,
        "component_tree": component_tree,
        "validation": validation_data,
        "audit_trail": [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp.isoformat(),
                "actor": e.actor,
                "action": e.action,
                "model_name": e.model_name,
                "version": e.version,
                "details": e.details,
                "reason": e.reason,
            }
            for e in audit_events
        ],
        "generated_at": generated_at,
        "ledger_version": model_ledger.__version__,
    }


def _version_to_dict(version_obj: Any) -> dict[str, Any]:
    """Serialize a ModelVersion to a plain dict."""
    return {
        "version": version_obj.version,
        "status": version_obj.status.value,
        "run_frequency": version_obj.run_frequency,
        "training_target": version_obj.training_target,
        "methodology_approach": version_obj.methodology_approach,
        "deployment_mode": version_obj.deployment_mode,
        "release_date": str(version_obj.release_date) if version_obj.release_date else None,
        "last_validation_date": (
            str(version_obj.last_validation_date) if version_obj.last_validation_date else None
        ),
        "next_validation_due": (
            str(version_obj.next_validation_due) if version_obj.next_validation_due else None
        ),
    }


# ---------------------------------------------------------------------------
# Format-specific writers
# ---------------------------------------------------------------------------


def _write_json(data: dict[str, Any], output: Path) -> None:
    """Write audit pack as a JSON file."""
    output.write_text(json.dumps(data, indent=2, default=str))


def _write_html(data: dict[str, Any], output: Path) -> None:
    """Write audit pack as a self-contained HTML file."""
    model = data["model"]
    version = data.get("version") or {}
    validation = data.get("validation")

    # Validation section
    if validation is None:
        validation_section = "<p>No validation results available.</p>"
    elif validation["passed"]:
        validation_section = VALIDATION_PASS.format(profile=validation["profile"])
    else:
        rows = ""
        for v in validation["violations"]:
            severity_class = v["severity"]  # "error", "warning", or "info"
            rows += VIOLATION_ROW.format(
                rule_id=v["rule_id"],
                severity=v["severity"].upper(),
                severity_class=severity_class,
                message=_escape_html(v["message"]),
                suggestion=_escape_html(v["suggestion"]),
            )
        validation_section = VALIDATION_FAIL_HEADER.format(
            profile=validation["profile"],
            error_count=validation["error_count"],
            warning_count=validation["warning_count"],
            rows=rows,
        )

    # Audit trail section
    audit_trail_section = ""
    for event in data.get("audit_trail", []):
        version_label = f" &bull; v{event['version']}" if event.get("version") else ""
        details_str = ""
        if event.get("details"):
            details_str = ", ".join(
                f"{k}: {v}" for k, v in event["details"].items() if v is not None
            )
        audit_trail_section += EVENT_CARD.format(
            action=event["action"],
            actor=event["actor"],
            timestamp=event["timestamp"],
            version_label=version_label,
            details=details_str,
        )
    if not audit_trail_section:
        audit_trail_section = "<p>No audit events recorded.</p>"

    # Executive summary
    compliance_summary = "N/A"
    if validation is not None:
        compliance_summary = (
            '<span class="badge badge-pass">PASS</span>'
            if validation["passed"]
            else '<span class="badge badge-fail">FAIL</span>'
        )
    executive_summary = EXEC_SUMMARY_SECTION.format(
        tier=model["tier"].upper(),
        model_type=model["model_type"],
        compliance_summary=compliance_summary,
        audit_count=len(data.get("audit_trail", [])),
    )

    # Component tree section
    tree_data = data.get("component_tree")
    if tree_data and tree_data.get("children"):
        component_tree_section = f'<div class="tree-container">{_render_tree_html(tree_data)}</div>'
    else:
        component_tree_section = "<p>No component tree defined for this version.</p>"

    html = HTML_TEMPLATE.format(
        model_name=_escape_html(model["name"]),
        generated_at=data["generated_at"],
        executive_summary=executive_summary,
        owner=_escape_html(model["owner"]),
        tier=model["tier"],
        model_status=model["status"],
        model_type=model["model_type"],
        intended_purpose=_escape_html(model["intended_purpose"]),
        version=version.get("version", "N/A"),
        version_status=version.get("status", "N/A"),
        methodology=version.get("methodology_approach") or "N/A",
        run_frequency=version.get("run_frequency") or "N/A",
        training_target=version.get("training_target") or "N/A",
        component_tree_section=component_tree_section,
        validation_section=validation_section,
        audit_trail_section=audit_trail_section,
        ledger_version=data["ledger_version"],
    )

    output.write_text(html)


def _write_markdown(data: dict[str, Any], output: Path) -> None:
    """Write audit pack as a Markdown file."""
    model = data["model"]
    version = data.get("version") or {}
    validation = data.get("validation")

    lines: list[str] = []

    # Header
    lines.append(f"# {model['name']}")
    lines.append("")
    lines.append(f"*Audit Pack -- Generated {data['generated_at']}*")
    lines.append("")

    # Model Card
    lines.append("## Model Card")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Name | {model['name']} |")
    lines.append(f"| Owner | {model['owner']} |")
    lines.append(f"| Tier | {model['tier']} |")
    lines.append(f"| Status | {model['status']} |")
    lines.append(f"| Type | {model['model_type']} |")
    lines.append(f"| Intended Purpose | {model['intended_purpose']} |")
    lines.append("")

    # Version Details
    lines.append("## Version Details")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Version | {version.get('version', 'N/A')} |")
    lines.append(f"| Status | {version.get('status', 'N/A')} |")
    lines.append(f"| Algorithm / Methodology | {version.get('methodology_approach') or 'N/A'} |")
    lines.append(f"| Run Frequency | {version.get('run_frequency') or 'N/A'} |")
    lines.append(f"| Training Target | {version.get('training_target') or 'N/A'} |")
    lines.append("")

    # Validation Results
    lines.append("## Validation Results")
    lines.append("")
    if validation is None:
        lines.append("No validation results available.")
    elif validation["passed"]:
        lines.append(f"**PASS** -- All rules satisfied for profile `{validation['profile']}`.")
    else:
        lines.append(
            f"**FAIL** -- Profile `{validation['profile']}` -- "
            f"{validation['error_count']} error(s), {validation['warning_count']} warning(s)."
        )
        lines.append("")
        lines.append("| Rule | Severity | Message | Suggestion |")
        lines.append("|------|----------|---------|------------|")
        for v in validation["violations"]:
            lines.append(
                f"| {v['rule_id']} | {v['severity'].upper()} | {v['message']} | {v['suggestion']} |"
            )
    lines.append("")

    # Audit Trail
    lines.append("## Audit Trail")
    lines.append("")
    for event in data.get("audit_trail", []):
        version_label = f" (v{event['version']})" if event.get("version") else ""
        lines.append(f"### {event['action']}{version_label}")
        lines.append(f"- **Actor:** {event['actor']}")
        lines.append(f"- **Timestamp:** {event['timestamp']}")
        if event.get("details"):
            details_str = ", ".join(
                f"{k}: {v}" for k, v in event["details"].items() if v is not None
            )
            if details_str:
                lines.append(f"- **Details:** {details_str}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Generated by model-ledger v{data['ledger_version']} on {data['generated_at']}*")
    lines.append("")

    output.write_text("\n".join(lines))


def _tree_to_dict(node: Any) -> dict[str, Any]:
    """Recursively convert a ComponentNode to a plain dict."""
    return {
        "name": node.name,
        "node_type": node.node_type,
        "metadata": node.metadata,
        "children": [_tree_to_dict(c) for c in node.children],
    }


def _render_tree_html(node: dict[str, Any], depth: int = 0) -> str:
    """Render a component tree as nested HTML with collapsible details."""
    type_label = (
        f' <span class="tree-type">({node["node_type"]})</span>'
        if node["node_type"] != "root"
        else ""
    )
    icon = "📂" if node.get("children") else "📄"

    if node.get("children"):
        children_html = "".join(_render_tree_html(c, depth + 1) for c in node["children"])
        open_attr = " open" if depth < 2 else ""
        return (
            f"<details{open_attr}>"
            f"<summary>{icon} {_escape_html(node['name'])}{type_label}</summary>"
            f'<div class="tree-node">{children_html}</div>'
            f"</details>"
        )
    return f"<div>{icon} {_escape_html(node['name'])}{type_label}</div>"


def _escape_html(text: str) -> str:
    """Minimal HTML entity escaping."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
