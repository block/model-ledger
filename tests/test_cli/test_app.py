import json

from typer.testing import CliRunner

from model_ledger import Inventory
from model_ledger.cli.app import app

runner = CliRunner()


def test_list_empty(tmp_path):
    db = str(tmp_path / "test.db")
    # Create empty inventory to initialize db
    Inventory(db_path=db)
    result = runner.invoke(app, ["list", "--db", db])
    assert result.exit_code == 0


def test_list_with_model(tmp_path):
    db = str(tmp_path / "test.db")
    inv = Inventory(db_path=db)
    inv.register_model(name="test-model", owner="tester", tier="low", intended_purpose="testing")
    result = runner.invoke(app, ["list", "--db", db])
    assert result.exit_code == 0
    assert "test-model" in result.output


def test_show_model(tmp_path):
    db = str(tmp_path / "test.db")
    inv = Inventory(db_path=db)
    inv.register_model(name="test-model", owner="tester", tier="low", intended_purpose="testing")
    result = runner.invoke(app, ["show", "test-model", "--db", db])
    assert result.exit_code == 0
    assert "test-model" in result.output
    assert "tester" in result.output


def test_show_model_not_found(tmp_path):
    db = str(tmp_path / "test.db")
    Inventory(db_path=db)
    result = runner.invoke(app, ["show", "nonexistent", "--db", db])
    assert result.exit_code != 0


def test_validate_model(tmp_path):
    db = str(tmp_path / "test.db")
    inv = Inventory(db_path=db)
    inv.register_model(name="test-model", owner="tester", tier="low", intended_purpose="testing")
    with inv.new_version("test-model"):
        pass
    result = runner.invoke(app, ["validate", "test-model", "--db", db])
    assert result.exit_code in (0, 1)


def test_validate_json_format(tmp_path):
    db = str(tmp_path / "test.db")
    inv = Inventory(db_path=db)
    inv.register_model(name="test-model", owner="tester", tier="low", intended_purpose="testing")
    with inv.new_version("test-model"):
        pass
    result = runner.invoke(app, ["validate", "test-model", "--db", db, "--format", "json"])
    assert result.exit_code in (0, 1)
    data = json.loads(result.output)
    assert "model_name" in data


def test_audit_log(tmp_path):
    db = str(tmp_path / "test.db")
    inv = Inventory(db_path=db)
    inv.register_model(name="test-model", owner="tester", tier="low", intended_purpose="testing")
    result = runner.invoke(app, ["audit-log", "test-model", "--db", db])
    assert result.exit_code == 0
    assert "registered_model" in result.output


def test_list_json_format(tmp_path):
    db = str(tmp_path / "test.db")
    inv = Inventory(db_path=db)
    inv.register_model(name="test-model", owner="tester", tier="low", intended_purpose="testing")
    result = runner.invoke(app, ["list", "--db", db, "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["name"] == "test-model"
