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
        s1 = FakeScanner("gondola", [
            ModelCandidate(
                name="ml-1", owner="t", model_type="ml_model",
                platform="gondola", metadata={},
            ),
        ])
        s2 = FakeScanner("squarewave", [
            ModelCandidate(
                name="rule-1", owner="t", model_type="heuristic",
                platform="squarewave", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [s1, s2])
        reports = inv.discover_all()
        assert len(reports) == 2
        assert len(ledger.list()) == 2

    def test_dedup_same_name_same_owner(self, ledger):
        s1 = FakeScanner("gondola", [
            ModelCandidate(
                name="shared-model", owner="team-a",
                model_type="ml_model", platform="gondola",
                metadata={"source": "gondola"},
            ),
        ])
        s2 = FakeScanner("squarewave", [
            ModelCandidate(
                name="shared-model", owner="team-a",
                model_type="ml_model", platform="squarewave",
                metadata={"source": "squarewave"},
            ),
        ])
        inv = InventoryScanner(ledger, [s1, s2])
        inv.discover_all()
        assert len(ledger.list()) == 1
        snaps = ledger.history("shared-model")
        # registered + discovered from gondola + scan_confirmed from squarewave
        assert len(snaps) >= 2


class TestScanPlatform:
    def test_scan_single_platform(self, ledger):
        s1 = FakeScanner("gondola", [
            ModelCandidate(
                name="ml-1", owner="t", model_type="ml",
                platform="gondola", metadata={},
            ),
        ])
        s2 = FakeScanner("squarewave", [
            ModelCandidate(
                name="rule-1", owner="t", model_type="heuristic",
                platform="squarewave", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [s1, s2])
        report = inv.scan_platform("gondola")
        assert report.total_found == 1
        assert len(ledger.list()) == 1

    def test_scan_unknown_platform_raises(self, ledger):
        inv = InventoryScanner(ledger, [])
        with pytest.raises(ValueError, match="Unknown platform"):
            inv.scan_platform("nonexistent")


class TestFilterFn:
    def test_filter_excludes_candidates(self, ledger):
        scanner = FakeScanner("squarewave", [
            ModelCandidate(
                name="risk-job", owner="t", model_type="heuristic",
                platform="squarewave", metadata={"subject_area": "Risk"},
            ),
            ModelCandidate(
                name="hr-job", owner="t", model_type="heuristic",
                platform="squarewave", metadata={"subject_area": "HR"},
            ),
        ])

        def risk_only(c: ModelCandidate) -> bool:
            return c.metadata.get("subject_area") == "Risk"

        inv = InventoryScanner(ledger, [scanner], filter_fn=risk_only)
        reports = inv.discover_all()
        assert reports[0].total_found == 1
        assert len(ledger.list()) == 1
        assert ledger.get("risk-job").name == "risk-job"

    def test_no_filter_registers_all(self, ledger):
        scanner = FakeScanner("p", [
            ModelCandidate(
                name="a", owner="t", model_type="ml",
                platform="p", metadata={},
            ),
            ModelCandidate(
                name="b", owner="t", model_type="ml",
                platform="p", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [scanner])
        inv.discover_all()
        assert len(ledger.list()) == 2


class TestScanRunId:
    def test_scan_run_id_in_report(self, ledger):
        scanner = FakeScanner("gondola", [
            ModelCandidate(
                name="m1", owner="t", model_type="ml",
                platform="gondola", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [scanner])
        reports = inv.discover_all()
        assert reports[0].scan_run_id is not None
        assert reports[0].scan_run_id.startswith("gondola:")

    def test_scan_run_id_in_snapshot_payloads(self, ledger):
        scanner = FakeScanner("gondola", [
            ModelCandidate(
                name="m1", owner="t", model_type="ml",
                platform="gondola", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [scanner])
        reports = inv.discover_all()
        scan_run_id = reports[0].scan_run_id

        snaps = ledger.history("m1")
        discovered = [s for s in snaps if s.event_type == "discovered"]
        assert discovered[0].payload["scan_run_id"] == scan_run_id


class TestNotFoundTracking:
    def test_not_found_recorded_for_missing_model(self, ledger):
        scanner = FakeScanner("gondola", [
            ModelCandidate(
                name="model-a", owner="t", model_type="ml",
                platform="gondola", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [scanner])
        inv.discover_all()

        # Second scan: model-a is gone
        scanner._candidates = []
        reports = inv.discover_all()
        assert reports[0].not_found_models == 1

        snaps = ledger.history("model-a")
        not_found = [s for s in snaps if s.event_type == "not_found"]
        assert len(not_found) == 1

    def test_not_found_only_for_same_platform(self, ledger):
        s1 = FakeScanner("gondola", [
            ModelCandidate(
                name="model-a", owner="t", model_type="ml",
                platform="gondola", metadata={},
            ),
        ])
        s2 = FakeScanner("squarewave", [
            ModelCandidate(
                name="rule-b", owner="t", model_type="heuristic",
                platform="squarewave", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [s1, s2])
        inv.discover_all()

        # model-a disappears from gondola — rule-b should NOT get not_found
        s1._candidates = []
        reports = inv.discover_all()
        gondola_report = [r for r in reports if r.platform == "gondola"][0]
        assert gondola_report.not_found_models == 1

        snaps = ledger.history("rule-b")
        not_found = [s for s in snaps if s.event_type == "not_found"]
        assert len(not_found) == 0

    def test_rediscovered_model_gets_confirmed(self, ledger):
        scanner = FakeScanner("gondola", [
            ModelCandidate(
                name="model-a", owner="t", model_type="ml",
                platform="gondola", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [scanner])
        inv.discover_all()

        # Disappear
        scanner._candidates = []
        inv.discover_all()

        # Reappear
        scanner._candidates = [
            ModelCandidate(
                name="model-a", owner="t", model_type="ml",
                platform="gondola", metadata={},
            ),
        ]
        inv.discover_all()

        snaps = ledger.history("model-a")
        events = [s.event_type for s in snaps]
        assert "not_found" in events
        assert "scan_confirmed" in events
