import json
from pathlib import Path

from model_ledger import Inventory
from model_ledger.backends.memory import InMemoryBackend
from model_ledger.export import export_audit_pack


def _setup_inventory():
    inv = Inventory(backend=InMemoryBackend())
    inv.register_model(
        name="test-model",
        owner="tester",
        tier="medium",
        intended_purpose="Testing audit pack export",
    )
    with inv.new_version("test-model") as v:
        v.add_component("Inputs/feature_set", type="feature_set")
        v.add_component("Processing/algorithm", type="algorithm")
        v.set_training_target("fraud detection")
        v.set_run_frequency("daily")
    return inv


def test_export_json(tmp_path):
    inv = _setup_inventory()
    output = str(tmp_path / "pack.json")
    export_audit_pack(inventory=inv, model_name="test-model", format="json", output_path=output)
    data = json.loads(Path(output).read_text())
    assert data["model"]["name"] == "test-model"
    assert data["model"]["owner"] == "tester"
    assert "audit_trail" in data


def test_export_html(tmp_path):
    inv = _setup_inventory()
    output = str(tmp_path / "pack.html")
    export_audit_pack(inventory=inv, model_name="test-model", format="html", output_path=output)
    html = Path(output).read_text()
    assert "<html" in html
    assert "test-model" in html
    assert "tester" in html


def test_export_markdown(tmp_path):
    inv = _setup_inventory()
    output = str(tmp_path / "pack.md")
    export_audit_pack(inventory=inv, model_name="test-model", format="markdown", output_path=output)
    md = Path(output).read_text()
    assert "# test-model" in md
    assert "tester" in md


def test_export_with_version(tmp_path):
    inv = _setup_inventory()
    output = str(tmp_path / "pack.json")
    export_audit_pack(
        inventory=inv, model_name="test-model", version="0.1.0", format="json", output_path=output
    )
    data = json.loads(Path(output).read_text())
    assert data["version"]["version"] == "0.1.0"


def test_export_with_validation(tmp_path):
    inv = _setup_inventory()
    output = str(tmp_path / "pack.json")
    export_audit_pack(inventory=inv, model_name="test-model", format="json", output_path=output)
    data = json.loads(Path(output).read_text())
    assert "validation" in data
