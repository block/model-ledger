"""Tests for SQL parsing utilities."""

from model_ledger.adapters.sql import (
    extract_model_name_filters,
    extract_tables_from_sql,
    extract_write_tables,
    strip_template_vars,
)


class TestExtractTables:
    def test_simple(self):
        assert "schema.table1" in extract_tables_from_sql("SELECT * FROM schema.table1")

    def test_join(self):
        sql = "SELECT * FROM a.b JOIN c.d ON 1=1"
        tables = extract_tables_from_sql(sql)
        assert len(tables) == 2

    def test_dedup(self):
        sql = "SELECT * FROM a.b JOIN a.b ON 1=1"
        assert len(extract_tables_from_sql(sql)) == 1

    def test_empty(self):
        assert extract_tables_from_sql("") == []
        assert extract_tables_from_sql(None) == []

    def test_unqualified_names(self):
        sql = "INSERT INTO feature_store SELECT * FROM raw_events"
        assert extract_tables_from_sql(sql) == ["raw_events"]

    def test_unqualified_join(self):
        tables = extract_tables_from_sql("SELECT * FROM orders JOIN customers ON 1=1")
        assert tables == ["orders", "customers"]

    def test_mixed_qualified_and_bare(self):
        tables = extract_tables_from_sql("SELECT * FROM schema.table1 JOIN raw_events ON 1=1")
        assert tables == ["schema.table1", "raw_events"]

    def test_bare_sql_keywords_not_extracted(self):
        # Subqueries / table functions must not surface keywords as tables.
        assert extract_tables_from_sql("SELECT * FROM LATERAL (SELECT 1)") == []
        assert extract_tables_from_sql("SELECT * FROM TABLE(my_function())") == []
        assert extract_tables_from_sql("SELECT * FROM VALUES (1), (2)") == []


class TestExtractWriteTables:
    def test_insert_into(self):
        assert "schema.output" in extract_write_tables("INSERT INTO schema.output SELECT 1")

    def test_create_table(self):
        assert "schema.t" in extract_write_tables("CREATE OR REPLACE TABLE schema.t AS SELECT 1")

    def test_merge_into(self):
        assert "schema.t" in extract_write_tables("MERGE INTO schema.t USING src ON 1=1")

    def test_select_only(self):
        assert extract_write_tables("SELECT * FROM schema.t") == []

    def test_empty(self):
        assert extract_write_tables("") == []
        assert extract_write_tables(None) == []

    def test_unqualified_insert(self):
        assert extract_write_tables("INSERT INTO feature_store SELECT * FROM raw_events") == [
            "feature_store"
        ]

    def test_unqualified_create(self):
        assert extract_write_tables("CREATE TABLE staging AS SELECT 1") == ["staging"]

    def test_unqualified_merge(self):
        assert extract_write_tables("MERGE INTO targets USING src ON 1=1") == ["targets"]

    def test_docstring_example_extractable_by_sibling(self):
        # The extract_write_tables docstring example must be fully parseable
        # by both extractors.
        sql = "INSERT INTO schema.output SELECT * FROM source"
        assert extract_write_tables(sql) == ["schema.output"]
        assert extract_tables_from_sql(sql) == ["source"]

    def test_insert_overwrite_keyword_not_extracted(self):
        assert extract_write_tables("INSERT OVERWRITE INTO schema.t SELECT 1") != ["OVERWRITE"]


class TestExtractModelNameFilters:
    def test_equals(self):
        assert extract_model_name_filters("WHERE model_name = 'fraud_v3'") == ["fraud_v3"]

    def test_like(self):
        assert extract_model_name_filters("WHERE model_name LIKE 'tm-%'") == ["tm-%"]

    def test_in(self):
        result = extract_model_name_filters("WHERE model_name IN ('a', 'b', 'c')")
        assert result == ["a", "b", "c"]

    def test_as_alias(self):
        assert extract_model_name_filters("SELECT 'tm_checks' AS model_name") == ["tm_checks"]

    def test_none(self):
        assert extract_model_name_filters("WHERE id = 1") == []

    def test_empty(self):
        assert extract_model_name_filters("") == []
        assert extract_model_name_filters(None) == []


class TestStripTemplateVars:
    def test_strips(self):
        assert strip_template_vars("{{schema}}.{{table}}") == "schema.table"

    def test_in_query(self):
        result = strip_template_vars("SELECT * FROM {{app}}.{{cash}}.my_table")
        assert result == "SELECT * FROM app.cash.my_table"

    def test_strips_spaced_vars(self):
        result = strip_template_vars(
            "SELECT * FROM {{ schema }}.{{ table }} WHERE run_date = '{{ ds }}'"
        )
        assert result == "SELECT * FROM schema.table WHERE run_date = 'ds'"

    def test_docstring_example_is_accurate(self):
        assert (
            strip_template_vars("SELECT * FROM {{schema}}.{{table_name}}")
            == "SELECT * FROM schema.table_name"
        )

    def test_no_templates(self):
        assert strip_template_vars("SELECT 1") == "SELECT 1"

    def test_empty(self):
        assert strip_template_vars("") == ""
        assert strip_template_vars(None) == ""
