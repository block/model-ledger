"""Tests for Ledger class method constructors."""
import os
import tempfile
import pytest
from model_ledger.sdk.ledger import Ledger
from model_ledger.backends.sqlite_ledger import SQLiteLedgerBackend
from model_ledger.backends.ledger_memory import InMemoryLedgerBackend


class TestFromSqlite:
    def test_creates_ledger_with_sqlite_backend(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            ledger = Ledger.from_sqlite(path)
            ledger.register(name="test", owner="alice", model_type="ml",
                           tier="high", purpose="test", actor="test")
            assert len(ledger.list()) == 1
            del ledger
            ledger2 = Ledger.from_sqlite(path)
            assert len(ledger2.list()) == 1
        finally:
            os.unlink(path)

    def test_creates_file_if_missing(self):
        path = tempfile.mktemp(suffix=".db")
        try:
            ledger = Ledger.from_sqlite(path)
            assert os.path.exists(path)
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestFromSnowflake:
    def test_creates_ledger_with_snowflake_backend(self):
        from tests.test_backends.test_snowflake_ledger import MockLedgerSession
        session = MockLedgerSession()
        ledger = Ledger.from_snowflake(session, schema="TEST_SCHEMA")
        ledger.register(name="test", owner="alice", model_type="ml",
                       tier="high", purpose="test", actor="test")
        assert len(ledger.list()) == 1


class TestDefaultConstructor:
    def test_default_is_in_memory(self):
        ledger = Ledger()
        assert isinstance(ledger._backend, InMemoryLedgerBackend)

    def test_explicit_backend(self):
        backend = InMemoryLedgerBackend()
        ledger = Ledger(backend)
        assert ledger._backend is backend
