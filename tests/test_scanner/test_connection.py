"""Tests for DBConnection protocol."""

from model_ledger.scanner.connection import DBConnection


class FakeDBConnection:
    def __init__(self, results: list[dict]):
        self._results = results
        self.last_query: str | None = None
        self.last_params: dict | None = None

    def execute(self, query: str, params: dict | None = None) -> list[dict]:
        self.last_query = query
        self.last_params = params
        return self._results


class TestDBConnection:
    def test_implements_protocol(self):
        conn = FakeDBConnection([])
        assert isinstance(conn, DBConnection)

    def test_execute_returns_rows(self):
        rows = [{"id": 1, "name": "model-a"}, {"id": 2, "name": "model-b"}]
        conn = FakeDBConnection(rows)
        result = conn.execute("SELECT * FROM models")
        assert len(result) == 2
        assert result[0]["name"] == "model-a"

    def test_execute_with_params(self):
        conn = FakeDBConnection([{"id": 1}])
        conn.execute("SELECT * FROM models WHERE id = :id", {"id": 1})
        assert conn.last_params == {"id": 1}
