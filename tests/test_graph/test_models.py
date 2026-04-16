"""Tests for DataNode and DataPort."""

from model_ledger.graph.models import DataNode, DataPort


class TestDataPort:
    def test_create(self):
        p = DataPort("my_table")
        assert p.identifier == "my_table"
        assert p.schema == {}

    def test_lowercases(self):
        assert DataPort("APP_COMPLIANCE.CASH.TABLE").identifier == "app_compliance.cash.table"

    def test_equality(self):
        assert DataPort("table_a") == DataPort("table_a")

    def test_case_insensitive(self):
        assert DataPort("TABLE_A") == DataPort("table_a")

    def test_inequality(self):
        assert DataPort("table_a") != DataPort("table_b")

    def test_matching_schema(self):
        assert DataPort("t", model_name="a") == DataPort("t", model_name="a")

    def test_different_schema(self):
        assert DataPort("t", model_name="a") != DataPort("t", model_name="b")

    def test_one_no_schema(self):
        # A port with schema must NOT match a bare port — prevents false edges
        assert DataPort("t", model_name="a") != DataPort("t")

    def test_like_pattern(self):
        assert DataPort("s", model_name="tm-%") == DataPort("s", model_name="tm-m2o")

    def test_like_no_match(self):
        assert DataPort("s", model_name="tm-%") != DataPort("s", model_name="uup-gambling")

    def test_hashable(self):
        assert len({DataPort("a"), DataPort("a"), DataPort("b")}) == 2

    def test_repr_with_schema(self):
        r = repr(DataPort("table", model_name="x"))
        assert "table" in r and "model_name" in r

    def test_repr_simple(self):
        assert "table" in repr(DataPort("table"))


class TestDataNode:
    def test_string_inputs(self):
        node = DataNode("scorer", inputs=["a", "b"], outputs=["c"])
        assert len(node.inputs) == 2
        assert all(isinstance(p, DataPort) for p in node.inputs)

    def test_dataport_inputs(self):
        node = DataNode("scorer", inputs=[DataPort("a")])
        assert node.inputs[0].identifier == "a"

    def test_mixed_inputs(self):
        node = DataNode("scorer", inputs=["a", DataPort("b", model_name="x")])
        assert node.inputs[1].schema == {"model_name": "x"}

    def test_defaults(self):
        node = DataNode("simple")
        assert node.platform == "" and node.inputs == [] and node.outputs == []

    def test_metadata(self):
        node = DataNode("s", metadata={"owner": "team"})
        assert node.metadata["owner"] == "team"
