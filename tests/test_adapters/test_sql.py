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


class TestCteNamesExcluded:
    """CTE names are query-local aliases, never read tables.

    Bare-identifier acceptance must not turn WITH-clause bindings into
    phantom lineage inputs.
    """

    def test_single_cte(self):
        sql = (
            "WITH recent_events AS (SELECT * FROM warehouse.raw_events) SELECT * FROM recent_events"
        )
        assert extract_tables_from_sql(sql) == ["warehouse.raw_events"]

    def test_multi_cte_dbt_style(self):
        sql = """
        WITH base AS (
            SELECT * FROM raw.events
        ), enriched AS (
            SELECT * FROM base JOIN raw.users ON base.user_id = raw.users.id
        ), final AS (
            SELECT * FROM enriched
        )
        SELECT * FROM final
        """
        assert extract_tables_from_sql(sql) == ["raw.events", "raw.users"]

    def test_nested_with(self):
        sql = (
            "WITH outer_cte AS ("
            "  WITH inner_cte AS (SELECT * FROM warehouse.raw_events)"
            "  SELECT * FROM inner_cte"
            ") SELECT * FROM outer_cte JOIN warehouse.users ON 1=1"
        )
        assert extract_tables_from_sql(sql) == ["warehouse.raw_events", "warehouse.users"]

    def test_with_recursive(self):
        sql = (
            "WITH RECURSIVE ancestry AS ("
            "  SELECT * FROM org_chart"
            "  UNION ALL"
            "  SELECT * FROM ancestry JOIN org_chart ON 1=1"
            ") SELECT * FROM ancestry"
        )
        assert extract_tables_from_sql(sql) == ["org_chart"]

    def test_cte_with_column_list(self):
        sql = "WITH cte (a, b) AS (SELECT 1, 2 FROM real_table) SELECT * FROM cte"
        assert extract_tables_from_sql(sql) == ["real_table"]

    def test_cte_shadowing_real_table_is_excluded(self):
        # A CTE that reuses a real table's name shadows it for the whole
        # statement; references resolve to the CTE, so nothing is extracted.
        sql = "WITH raw_events AS (SELECT * FROM warehouse.archive) SELECT * FROM raw_events"
        assert extract_tables_from_sql(sql) == ["warehouse.archive"]

    def test_cte_feeding_a_write_statement(self):
        sql = "WITH cte AS (SELECT 1) INSERT INTO out_table SELECT * FROM cte"
        assert extract_tables_from_sql(sql) == []
        assert extract_write_tables(sql) == ["out_table"]

    def test_original_bare_from_still_resolves(self):
        # The OSS-4 headline case must keep working with the CTE filter on.
        sql = "INSERT INTO feature_store SELECT * FROM raw_events"
        assert extract_tables_from_sql(sql) == ["raw_events"]

    def test_case_insensitive_exclusion(self):
        sql = "WITH Recent AS (SELECT * FROM warehouse.raw_events) SELECT * FROM RECENT"
        assert extract_tables_from_sql(sql) == ["warehouse.raw_events"]


class TestDeleteFromNotARead:
    def test_bare_delete_target_not_extracted(self):
        assert extract_tables_from_sql("DELETE FROM audit_log WHERE 1=1") == []

    def test_qualified_delete_target_not_extracted(self):
        assert extract_tables_from_sql("DELETE FROM schema.audit_log WHERE 1=1") == []

    def test_delete_with_using_keeps_the_read_source(self):
        sql = "DELETE FROM audit_log USING retention_policy WHERE 1=1"
        assert "audit_log" not in extract_tables_from_sql(sql)


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

    def test_insert_overwrite_table_hive_form(self):
        # Hive/Spark: INSERT OVERWRITE TABLE <name> ...
        sql = "INSERT OVERWRITE TABLE feature_out SELECT * FROM src"
        assert extract_write_tables(sql) == ["feature_out"]

    def test_insert_overwrite_table_qualified(self):
        sql = "INSERT OVERWRITE TABLE warehouse.feature_out SELECT * FROM src"
        assert extract_write_tables(sql) == ["warehouse.feature_out"]

    def test_insert_overwrite_bare(self):
        assert extract_write_tables("INSERT OVERWRITE feature_out SELECT 1") == ["feature_out"]


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
