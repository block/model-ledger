"""Tests for table-based pipeline discovery."""

from model_ledger.adapters.tables import discover_pipelines_from_table, DBConnection


class FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, query, params=None):
        return self._rows


def test_discovers_pipelines():
    conn = FakeConnection([
        {"NAME": "fraud_v3", "FIRST_OUTPUT": "2024-01-01", "LAST_OUTPUT": "2026-03-16", "TOTAL_ROWS": 1000000},
        {"NAME": "aml_v2", "FIRST_OUTPUT": "2024-06-01", "LAST_OUTPUT": "2026-03-16", "TOTAL_ROWS": 500000},
    ])
    nodes = discover_pipelines_from_table(conn, "scores_archive", "MODEL_NAME", "RUN_DATE")
    assert len(nodes) == 2
    assert nodes[0].name == "pipeline:fraud_v3"
    assert nodes[0].outputs[0].identifier == "scores_archive"
    assert nodes[0].outputs[0].schema == {"model_name": "fraud_v3"}
    assert nodes[0].metadata["total_rows"] == 1000000


def test_empty_table():
    conn = FakeConnection([])
    assert discover_pipelines_from_table(conn, "t", "name", "ts") == []


def test_custom_platform():
    conn = FakeConnection([{"NAME": "x", "FIRST_OUTPUT": "", "LAST_OUTPUT": "", "TOTAL_ROWS": 1}])
    nodes = discover_pipelines_from_table(conn, "t", "name", "ts", platform="bigquery")
    assert nodes[0].platform == "bigquery"


def test_output_port_has_discriminator():
    conn = FakeConnection([{"NAME": "my_model", "FIRST_OUTPUT": "", "LAST_OUTPUT": "", "TOTAL_ROWS": 1}])
    nodes = discover_pipelines_from_table(conn, "scores", "MODEL_NAME", "ts")
    port = nodes[0].outputs[0]
    assert port.schema["model_name"] == "my_model"


def test_implements_dbconnection():
    conn = FakeConnection([])
    assert isinstance(conn, DBConnection)
