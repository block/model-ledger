"""Tests for the optional ``get_models`` bulk-resolution backend method.

``get_models(hashes) -> {hash: ModelRef}`` is the batched counterpart to
``get_model``. Every shipped backend implements it, and ``batch_fallbacks``
supplies a protocol-only version for third-party backends that do not. These
tests pin the shared contract: same refs as one-by-one resolution, missing
hashes omitted, dedup, and empty/blank input handled.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from model_ledger.backends import batch_fallbacks
from model_ledger.backends.json_files import JsonFileLedgerBackend
from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.backends.sqlite_ledger import SQLiteLedgerBackend
from model_ledger.core.ledger_models import ModelRef


def _make_model(name: str) -> ModelRef:
    return ModelRef(
        name=name,
        owner="risk-team",
        model_type="ml_model",
        tier="high",
        purpose="testing",
    )


def _seed(backend, names):
    refs = {}
    for n in names:
        ref = _make_model(n)
        backend.save_model(ref)
        refs[n] = ref
    return refs


def _backends(tmp_path: Path):
    sqlite = SQLiteLedgerBackend(str(tmp_path / "g.db"))
    json_files = JsonFileLedgerBackend(str(tmp_path / "jf"))
    return {
        "memory": InMemoryLedgerBackend(),
        "sqlite": sqlite,
        "json_files": json_files,
    }


@pytest.fixture(params=["memory", "sqlite", "json_files"])
def backend(request, tmp_path):
    return _backends(tmp_path)[request.param]


class TestGetModels:
    def test_resolves_all_hashes(self, backend):
        refs = _seed(backend, ["a", "b", "c"])
        result = backend.get_models([refs["a"].model_hash, refs["b"].model_hash])
        assert set(result) == {refs["a"].model_hash, refs["b"].model_hash}
        assert result[refs["a"].model_hash].name == "a"
        assert result[refs["b"].model_hash].name == "b"

    def test_omits_missing_hashes(self, backend):
        refs = _seed(backend, ["a"])
        result = backend.get_models([refs["a"].model_hash, "deadbeef-missing"])
        assert set(result) == {refs["a"].model_hash}

    def test_empty_and_blank_input(self, backend):
        _seed(backend, ["a"])
        assert backend.get_models([]) == {}
        assert backend.get_models(["", ""]) == {}

    def test_dedup_repeated_hash(self, backend):
        refs = _seed(backend, ["a"])
        h = refs["a"].model_hash
        result = backend.get_models([h, h, h])
        assert set(result) == {h}

    def test_parity_with_single_get_model(self, backend):
        refs = _seed(backend, ["a", "b", "c"])
        hashes = [r.model_hash for r in refs.values()]
        bulk = backend.get_models(hashes)
        for h in hashes:
            single = backend.get_model(h)
            assert bulk[h].model_hash == single.model_hash
            assert bulk[h].name == single.name


class TestGetModelsFallback:
    """The protocol-only fallback must match the native implementations."""

    def test_fallback_resolves_and_omits(self):
        backend = InMemoryLedgerBackend()
        refs = _seed(backend, ["a", "b"])
        result = batch_fallbacks.get_models(
            backend, [refs["a"].model_hash, "missing", refs["b"].model_hash]
        )
        assert set(result) == {refs["a"].model_hash, refs["b"].model_hash}

    def test_fallback_dedups_and_skips_blank(self):
        backend = InMemoryLedgerBackend()
        refs = _seed(backend, ["a"])
        h = refs["a"].model_hash
        result = batch_fallbacks.get_models(backend, ["", h, h])
        assert set(result) == {h}
