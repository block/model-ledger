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


class FakeChangelessScanner:
    def __init__(self, name: str, candidates: list[ModelCandidate]):
        self.name = name
        self.platform_type = "test"
        self._candidates = candidates

    def scan(self) -> list[ModelCandidate]:
        return self._candidates

    def has_changed(self, last_scan: datetime) -> bool:
        return False


class FakeEnrichableScanner:
    def __init__(self, name: str, candidates: list[ModelCandidate]):
        self.name = name
        self.platform_type = "test"
        self._candidates = candidates

    def scan(self) -> list[ModelCandidate]:
        return self._candidates

    def has_changed(self, last_scan: datetime) -> bool:
        return True

    def enrich(self, candidate: ModelCandidate) -> dict:
        return {"enriched": True, "features": ["f1", "f2"]}


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


class TestFilterFn:
    def test_filter_excludes_candidates(self, ledger):
        scanner = FakeScanner("etl_engine", [
            ModelCandidate(
                name="risk-job", owner="t", model_type="heuristic",
                platform="etl_engine", metadata={"subject_area": "Risk"},
            ),
            ModelCandidate(
                name="hr-job", owner="t", model_type="heuristic",
                platform="etl_engine", metadata={"subject_area": "HR"},
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
        scanner = FakeScanner("ml_platform", [
            ModelCandidate(
                name="m1", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [scanner])
        reports = inv.discover_all()
        assert reports[0].scan_run_id is not None
        assert reports[0].scan_run_id.startswith("ml_platform:")

    def test_scan_run_id_in_snapshot_payloads(self, ledger):
        scanner = FakeScanner("ml_platform", [
            ModelCandidate(
                name="m1", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
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
        scanner = FakeScanner("ml_platform", [
            ModelCandidate(
                name="model-a", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
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
        s1 = FakeScanner("ml_platform", [
            ModelCandidate(
                name="model-a", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
            ),
        ])
        s2 = FakeScanner("etl_engine", [
            ModelCandidate(
                name="rule-b", owner="t", model_type="heuristic",
                platform="etl_engine", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [s1, s2])
        inv.discover_all()

        # model-a disappears from ml_platform — rule-b should NOT get not_found
        s1._candidates = []
        reports = inv.discover_all()
        ml_platform_report = [r for r in reports if r.platform == "ml_platform"][0]
        assert ml_platform_report.not_found_models == 1

        snaps = ledger.history("rule-b")
        not_found = [s for s in snaps if s.event_type == "not_found"]
        assert len(not_found) == 0

    def test_rediscovered_model_gets_confirmed(self, ledger):
        scanner = FakeScanner("ml_platform", [
            ModelCandidate(
                name="model-a", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
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
                platform="ml_platform", metadata={},
            ),
        ]
        inv.discover_all()

        snaps = ledger.history("model-a")
        events = [s.event_type for s in snaps]
        assert "not_found" in events
        assert "scan_confirmed" in events


class TestHasChanged:
    def test_skips_scanner_when_not_changed(self, ledger):
        # First scan to establish last_scan time
        first_scanner = FakeScanner("ml_platform", [
            ModelCandidate(
                name="existing", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
            ),
        ])
        inv1 = InventoryScanner(ledger, [first_scanner])
        inv1.discover_all()
        assert len(ledger.list()) == 1

        # Second scan with changeless scanner — should be skipped
        changeless = FakeChangelessScanner("ml_platform", [
            ModelCandidate(
                name="new-model", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
            ),
        ])
        inv2 = InventoryScanner(ledger, [changeless])
        reports = inv2.discover_all()
        assert reports[0].total_found == 0
        # new-model should NOT have been registered
        assert len(ledger.list()) == 1

    def test_runs_scanner_when_changed(self, ledger):
        scanner = FakeScanner("ml_platform", [
            ModelCandidate(
                name="m1", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [scanner])
        reports = inv.discover_all()
        assert reports[0].total_found == 1


class TestEnrichment:
    def test_enrichable_scanner_creates_enriched_snapshot(self, ledger):
        scanner = FakeEnrichableScanner("ml_platform", [
            ModelCandidate(
                name="m1", owner="t", model_type="ml",
                platform="ml_platform", metadata={},
            ),
        ])
        inv = InventoryScanner(ledger, [scanner])
        inv.discover_all()

        snaps = ledger.history("m1")
        enriched = [s for s in snaps if s.event_type == "enriched"]
        assert len(enriched) == 1
        assert enriched[0].payload["features"] == ["f1", "f2"]
