"""Tests for InventoryScanner — orchestrates scanners, deduplicates, registers."""

from datetime import datetime

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.scanner.orchestrator import InventoryScanner
from model_ledger.scanner.protocol import ModelCandidate
from model_ledger.sdk.ledger import Ledger


class FakeScanner:
    def __init__(self, name: str, candidates: list[ModelCandidate]):
        self.name = name
        self.platform_type = "test"
        self._candidates = candidates

    def scan(self) -> list[ModelCandidate]:
        return self._candidates

    def has_changed(self, last_scan: datetime) -> bool:
        return True


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


class TestDiscoverAll:
    def test_discovers_and_registers(self, ledger):
        scanner = FakeScanner("platform-a", [
            ModelCandidate(
                name="model-1", owner="team-a", model_type="ml_model",
                platform="platform-a", platform_id="id-1",
                metadata={"algo": "xgb"},
            ),
            ModelCandidate(
                name="model-2", owner="team-b", model_type="heuristic",
                platform="platform-a", platform_id="id-2", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [scanner])
        reports = inv.discover_all()
        assert len(reports) == 1
        assert reports[0].total_found == 2
        assert reports[0].new_models == 2
        assert len(ledger.list()) == 2

    def test_idempotent_scan(self, ledger):
        candidates = [
            ModelCandidate(
                name="model-1", owner="team-a", model_type="ml_model",
                platform="p", metadata={},
            ),
        ]
        scanner = FakeScanner("p", candidates)
        inv = InventoryScanner(ledger, [scanner])
        inv.discover_all()
        reports = inv.discover_all()
        assert reports[0].new_models == 0
        assert len(ledger.list()) == 1

    def test_multiple_scanners(self, ledger):
        s1 = FakeScanner("ml_platform", [
            ModelCandidate(
                name="ml-1", owner="t", model_type="ml_model",
                platform="ml_platform", metadata={},
            ),
        ])
        s2 = FakeScanner("etl_engine", [
            ModelCandidate(
                name="rule-1", owner="t", model_type="heuristic",
                platform="etl_engine", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [s1, s2])
        reports = inv.discover_all()
        assert len(reports) == 2
        assert len(ledger.list()) == 2

    def test_dedup_same_name_same_owner(self, ledger):
        s1 = FakeScanner("ml_platform", [
            ModelCandidate(
                name="shared-model", owner="team-a",
                model_type="ml_model", platform="ml_platform",
                metadata={"source": "ml_platform"},
            ),
        ])
        s2 = FakeScanner("etl_engine", [
            ModelCandidate(
                name="shared-model", owner="team-a",
                model_type="ml_model", platform="etl_engine",
                metadata={"source": "etl_engine"},
            ),
        ])
        inv = InventoryScanner(ledger, [s1, s2])
        inv.discover_all()
        assert len(ledger.list()) == 1
        snaps = ledger.history("shared-model")
        # registered + discovered from ml_platform + scan_confirmed from etl_engine
        assert len(snaps) >= 2


class TestScanPlatform:
    def test_scan_single_platform(self, ledger):
        s1 = FakeScanner("ml_platform", [
            ModelCandidate(
                name="ml-1", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
            ),
        ])
        s2 = FakeScanner("etl_engine", [
            ModelCandidate(
                name="rule-1", owner="t", model_type="heuristic",
                platform="etl_engine", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [s1, s2])
        report = inv.scan_platform("ml_platform")
        assert report.total_found == 1
        assert len(ledger.list()) == 1

    def test_scan_unknown_platform_raises(self, ledger):
        inv = InventoryScanner(ledger, [])
        with pytest.raises(ValueError, match="Unknown platform"):
            inv.scan_platform("nonexistent")
