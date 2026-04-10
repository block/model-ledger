# tests/test_tools/test_discover.py
"""Tests for the discover tool — bulk ingestion from inline data, files, or connectors."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.discover import discover
from model_ledger.tools.schemas import DiscoverInput, DiscoverOutput


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


class TestDiscoverInline:
    """Inline source_type — models passed directly as list of dicts."""

    def test_inline_adds_models(self, ledger):
        """Two inline models should yield models_added=2, models_skipped=0."""
        inp = DiscoverInput(
            source_type="inline",
            models=[
                {"name": "feature_pipeline", "platform": "airflow"},
                {"name": "scoring_model", "platform": "sagemaker"},
            ],
            auto_connect=False,
        )
        result = discover(inp, ledger)

        assert isinstance(result, DiscoverOutput)
        assert result.models_added == 2
        assert result.models_skipped == 0
        assert len(result.models) == 2
        assert result.errors == []

    def test_inline_auto_connect(self, ledger):
        """Models with matching input/output ports should create links."""
        inp = DiscoverInput(
            source_type="inline",
            models=[
                {
                    "name": "feature_pipeline",
                    "platform": "airflow",
                    "outputs": ["feature_table"],
                },
                {
                    "name": "scoring_model",
                    "platform": "sagemaker",
                    "inputs": ["feature_table"],
                },
            ],
            auto_connect=True,
        )
        result = discover(inp, ledger)

        assert result.models_added == 2
        assert result.links_created >= 1

    def test_inline_auto_connect_false(self, ledger):
        """When auto_connect=False, links_created must be 0."""
        inp = DiscoverInput(
            source_type="inline",
            models=[
                {
                    "name": "feature_pipeline",
                    "platform": "airflow",
                    "outputs": ["feature_table"],
                },
                {
                    "name": "scoring_model",
                    "platform": "sagemaker",
                    "inputs": ["feature_table"],
                },
            ],
            auto_connect=False,
        )
        result = discover(inp, ledger)

        assert result.models_added == 2
        assert result.links_created == 0

    def test_inline_dedup(self, ledger):
        """Adding the same models twice should skip them on the second call."""
        models = [
            {"name": "feature_pipeline", "platform": "airflow"},
            {"name": "scoring_model", "platform": "sagemaker"},
        ]
        inp1 = DiscoverInput(source_type="inline", models=models, auto_connect=False)
        result1 = discover(inp1, ledger)
        assert result1.models_added == 2
        assert result1.models_skipped == 0

        inp2 = DiscoverInput(source_type="inline", models=models, auto_connect=False)
        result2 = discover(inp2, ledger)
        assert result2.models_added == 0
        assert result2.models_skipped == 2

    def test_inline_empty_list(self, ledger):
        """Empty model list yields models_added=0."""
        inp = DiscoverInput(source_type="inline", models=[], auto_connect=False)
        result = discover(inp, ledger)

        assert result.models_added == 0
        assert result.models_skipped == 0
        assert result.links_created == 0
        assert result.models == []

    def test_inline_none_models_raises(self, ledger):
        """source_type='inline' with models=None should raise ValueError."""
        inp = DiscoverInput(source_type="inline", models=None)
        with pytest.raises(ValueError, match="models"):
            discover(inp, ledger)


class TestDiscoverFile:
    """File source_type — models loaded from a JSON file."""

    def test_file_loads_models(self, ledger):
        """Loading models from a JSON file should add them."""
        models = [
            {"name": "etl_job", "platform": "spark"},
            {"name": "report_gen", "platform": "tableau"},
        ]
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
        ) as f:
            json.dump(models, f)
            tmp_path = f.name

        try:
            inp = DiscoverInput(
                source_type="file",
                file_path=tmp_path,
                auto_connect=False,
            )
            result = discover(inp, ledger)

            assert result.models_added == 2
            assert result.models_skipped == 0
        finally:
            os.unlink(tmp_path)

    def test_file_none_path_raises(self, ledger):
        """source_type='file' with file_path=None should raise ValueError."""
        inp = DiscoverInput(source_type="file", file_path=None)
        with pytest.raises(ValueError, match="file_path"):
            discover(inp, ledger)


class TestDiscoverConnector:
    """Connector source_type — should raise NotImplementedError."""

    def test_connector_raises(self, ledger):
        inp = DiscoverInput(
            source_type="connector",
            connector_name="databricks",
            connector_config={"workspace": "test"},
        )
        with pytest.raises(NotImplementedError, match="not yet supported"):
            discover(inp, ledger)
