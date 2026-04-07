# tests/test_connectors/test_sql_connector.py
"""Tests for sql_connector factory."""
from model_ledger.connectors.sql import sql_connector
from model_ledger.graph.protocol import SourceConnector


class MockConnection:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, query, params=None):
        return self._rows


def test_returns_source_connector():
    conn = MockConnection([])
    c = sql_connector(name="test", connection=conn, query="SELECT 1", name_column="name")
    assert isinstance(c, SourceConnector)
    assert c.name == "test"


def test_simple_discovery():
    conn = MockConnection([
        {"name": "model_a", "owner": "alice", "status": "active"},
        {"name": "model_b", "owner": "bob", "status": "active"},
    ])
    c = sql_connector(name="registry", connection=conn,
                      query="SELECT name, owner, status FROM models",
                      name_column="name")
    nodes = c.discover()
    assert len(nodes) == 2
    assert nodes[0].name == "model_a"
    assert nodes[0].platform == "registry"
    assert nodes[0].metadata["owner"] == "alice"
    assert nodes[0].metadata["status"] == "active"


def test_name_prefix():
    conn = MockConnection([{"slug": "my_queue", "display": "My Queue"}])
    c = sql_connector(name="case_mgmt", connection=conn,
                      query="SELECT slug, display FROM queues",
                      name_column="slug", name_prefix="queue:")
    nodes = c.discover()
    assert nodes[0].name == "queue:my_queue"


def test_input_output_columns():
    conn = MockConnection([
        {"name": "etl_job", "input_table": "raw.events", "output_table": "analytics.scores"},
    ])
    c = sql_connector(name="etl", connection=conn,
                      query="SELECT name, input_table, output_table FROM jobs",
                      name_column="name",
                      input_columns=["input_table"],
                      output_columns=["output_table"])
    nodes = c.discover()
    assert len(nodes[0].inputs) == 1
    assert nodes[0].inputs[0].identifier == "raw.events"
    assert len(nodes[0].outputs) == 1
    assert nodes[0].outputs[0].identifier == "analytics.scores"


def test_sql_column_parsing():
    conn = MockConnection([
        {"name": "my_rule", "query_sql": "SELECT * FROM schema.alerts WHERE model_name = 'fraud_v3'"},
    ])
    c = sql_connector(name="rules", connection=conn,
                      query="SELECT name, query_sql FROM algorithms",
                      name_column="name",
                      sql_column="query_sql")
    nodes = c.discover()
    assert any(p.identifier == "schema.alerts" for p in nodes[0].inputs)


def test_output_port_config():
    conn = MockConnection([
        {"name": "algo1", "queue_label": "my_queue"},
    ])
    c = sql_connector(name="alerting", connection=conn,
                      query="SELECT name, queue_label FROM algos",
                      name_column="name",
                      output_port={"column": "queue_label", "kind": "alert_queue"})
    nodes = c.discover()
    assert nodes[0].outputs[0].identifier == "my_queue"
    assert nodes[0].outputs[0].schema.get("kind") == "alert_queue"


def test_output_port_fallback():
    conn = MockConnection([
        {"name": "algo1", "queue_label": None},
    ])
    c = sql_connector(name="alerting", connection=conn,
                      query="SELECT name, queue_label FROM algos",
                      name_column="name",
                      output_port={"column": "queue_label", "fallback": "name", "kind": "alert_queue"})
    nodes = c.discover()
    assert nodes[0].outputs[0].identifier == "algo1"


def test_explicit_metadata_columns():
    conn = MockConnection([
        {"name": "m1", "owner": "alice", "status": "active", "junk": "ignored"},
    ])
    c = sql_connector(name="test", connection=conn,
                      query="SELECT name, owner, status, junk FROM models",
                      name_column="name",
                      metadata_columns={"owner": "owner", "model_status": "status"})
    nodes = c.discover()
    assert nodes[0].metadata["owner"] == "alice"
    assert nodes[0].metadata["model_status"] == "active"
    assert "junk" not in nodes[0].metadata


def test_input_port_config():
    conn = MockConnection([
        {"slug": "my_queue", "display": "My Queue"},
    ])
    c = sql_connector(name="case_mgmt", connection=conn,
                      query="SELECT slug, display FROM queues",
                      name_column="slug", name_prefix="queue:",
                      input_port={"column": "slug", "kind": "alert_queue"})
    nodes = c.discover()
    assert nodes[0].inputs[0].identifier == "my_queue"
    assert nodes[0].inputs[0].schema.get("kind") == "alert_queue"


def test_shared_table_patterns_custom():
    conn = MockConnection([
        {"name": "my_rule", "query_sql": "SELECT * FROM my_schema.my_scores WHERE model_name = 'fraud_v3'"},
    ])
    c = sql_connector(name="rules", connection=conn,
                      query="SELECT name, query_sql FROM algorithms",
                      name_column="name",
                      sql_column="query_sql",
                      shared_table_patterns=["my_scores"])
    nodes = c.discover()
    # my_scores matches the pattern, so it gets model_name discriminator
    scored_inputs = [p for p in nodes[0].inputs if p.schema.get("model_name")]
    assert len(scored_inputs) == 1
    assert scored_inputs[0].schema["model_name"] == "fraud_v3"


def test_shared_table_patterns_empty():
    conn = MockConnection([
        {"name": "my_rule", "query_sql": "SELECT * FROM schema.alerts WHERE model_name = 'fraud_v3'"},
    ])
    c = sql_connector(name="rules", connection=conn,
                      query="SELECT name, query_sql FROM algorithms",
                      name_column="name",
                      sql_column="query_sql",
                      shared_table_patterns=[])
    nodes = c.discover()
    # No patterns → no model_name discriminators on inputs
    scored_inputs = [p for p in nodes[0].inputs if p.schema.get("model_name")]
    assert len(scored_inputs) == 0


def test_sql_preprocessor_strips_template_vars():
    conn = MockConnection([
        {"name": "job1", "raw_sql": "SELECT * FROM {{schema}}.{{table}} WHERE x = 1"},
    ])
    c = sql_connector(name="etl", connection=conn,
                      query="SELECT name, raw_sql FROM jobs",
                      name_column="name",
                      sql_column="raw_sql")
    nodes = c.discover()
    # strip_template_vars is the default preprocessor — {{schema}}.{{table}} → schema.table
    assert any(p.identifier == "schema.table" for p in nodes[0].inputs)


def test_sql_preprocessor_disabled():
    conn = MockConnection([
        {"name": "job1", "raw_sql": "SELECT * FROM {{schema}}.{{table}}"},
    ])
    c = sql_connector(name="etl", connection=conn,
                      query="SELECT name, raw_sql FROM jobs",
                      name_column="name",
                      sql_column="raw_sql",
                      sql_preprocessor=None)
    nodes = c.discover()
    # With preprocessing disabled, {{schema}}.{{table}} won't parse as a table
    assert len(nodes[0].inputs) == 0


def test_cron_column():
    conn = MockConnection([
        {"name": "job1", "cron": "0 7 * * *"},
    ])
    c = sql_connector(name="etl", connection=conn,
                      query="SELECT name, cron FROM jobs",
                      name_column="name",
                      cron_column="cron")
    nodes = c.discover()
    assert nodes[0].metadata["cron"] == "0 7 * * *"
    assert "run_frequency" in nodes[0].metadata


def test_shared_table_fallback():
    conn = MockConnection([
        {"name": "org_prefix_checks", "raw_sql":
         "INSERT INTO schema.global_alert_attributes SELECT 1"},
    ])
    c = sql_connector(name="etl", connection=conn,
                      query="SELECT name, raw_sql FROM jobs",
                      name_column="name",
                      sql_column="raw_sql",
                      shared_table_patterns=["global_alert"],
                      shared_table_fallback={"source_column": "name", "strip_prefix": "org_prefix_"})
    nodes = c.discover()
    out = [p for p in nodes[0].outputs if p.schema.get("model_name")]
    assert len(out) == 1
    assert out[0].schema["model_name"] == "checks"  # prefix stripped


def test_empty_result():
    conn = MockConnection([])
    c = sql_connector(name="test", connection=conn, query="SELECT 1", name_column="name")
    assert c.discover() == []


def test_integrates_with_ledger():
    from model_ledger import Ledger
    conn = MockConnection([
        {"name": "writer", "output_table": "shared"},
        {"name": "reader", "input_table": "shared"},
    ])
    writer_conn = sql_connector(name="etl", connection=conn,
                                query="SELECT name, output_table FROM jobs",
                                name_column="name",
                                output_columns=["output_table"])
    # Need separate connector for reader since MockConnection returns same rows
    reader_conn_data = MockConnection([
        {"name": "reader", "input_table": "shared"},
    ])
    reader_conn = sql_connector(name="etl", connection=reader_conn_data,
                                query="SELECT name, input_table FROM jobs",
                                name_column="name",
                                input_columns=["input_table"])
    ledger = Ledger()
    ledger.add(writer_conn.discover())
    ledger.add(reader_conn.discover())
    result = ledger.connect()
    assert result["links_created"] >= 1
