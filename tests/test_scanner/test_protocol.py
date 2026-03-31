"""Tests for Scanner protocol and ModelCandidate."""

from datetime import datetime

from model_ledger.scanner.protocol import (
    EnrichableScanner,
    ModelCandidate,
    Scanner,
)
from model_ledger.scanner.report import ScanReport


class TestModelCandidate:
    def test_create(self):
        c = ModelCandidate(
            name="fraud-rule-1", owner="risk-team",
            model_type="heuristic", platform="squarewave",
            platform_id="job-123", metadata={"schedule": "daily"},
        )
        assert c.name == "fraud-rule-1"
        assert c.platform == "squarewave"

    def test_owner_optional(self):
        c = ModelCandidate(
            name="unknown-rule", model_type="heuristic",
            platform="squarewave", metadata={},
        )
        assert c.owner is None

    def test_parent_name(self):
        c = ModelCandidate(
            name="ruleset-1", owner="risk-team",
            model_type="ruleset", platform="risk-arbiter",
            parent_name="TD-85",
        )
        assert c.parent_name == "TD-85"

    def test_parent_name_defaults_none(self):
        c = ModelCandidate(
            name="model-1", model_type="ml",
            platform="gondola", metadata={},
        )
        assert c.parent_name is None

    def test_external_ids(self):
        c = ModelCandidate(
            name="arr-v3", model_type="ml_model",
            platform="gondola",
            external_ids={"gondola": "arr_v3", "risk_arbiter": "TD-85"},
            metadata={},
        )
        assert c.external_ids["gondola"] == "arr_v3"

    def test_external_ids_defaults_empty(self):
        c = ModelCandidate(
            name="model-1", model_type="ml",
            platform="gondola", metadata={},
        )
        assert c.external_ids == {}


class FakeScanner:
    name = "fake"
    platform_type = "test"

    def __init__(self, candidates: list[ModelCandidate]):
        self._candidates = candidates
        self._changed = True

    def scan(self) -> list[ModelCandidate]:
        return self._candidates

    def has_changed(self, last_scan: datetime) -> bool:
        return self._changed


class TestScannerProtocol:
    def test_implements_protocol(self):
        scanner = FakeScanner([])
        assert isinstance(scanner, Scanner)

    def test_scan_returns_candidates(self):
        candidates = [
            ModelCandidate(
                name="m1", model_type="ml", platform="fake", metadata={},
            ),
            ModelCandidate(
                name="m2", model_type="ml", platform="fake", metadata={},
            ),
        ]
        scanner = FakeScanner(candidates)
        result = scanner.scan()
        assert len(result) == 2


class FakeEnrichableScanner:
    name = "enrichable"
    platform_type = "test"

    def scan(self) -> list[ModelCandidate]:
        return []

    def has_changed(self, last_scan: datetime) -> bool:
        return True

    def enrich(self, candidate: ModelCandidate) -> dict:
        return {"enriched": True, "name": candidate.name}


class TestEnrichableScanner:
    def test_implements_protocol(self):
        scanner = FakeEnrichableScanner()
        assert isinstance(scanner, EnrichableScanner)

    def test_enrich_returns_dict(self):
        scanner = FakeEnrichableScanner()
        c = ModelCandidate(
            name="test", model_type="ml", platform="x", metadata={},
        )
        result = scanner.enrich(c)
        assert result["enriched"] is True


class TestScanReport:
    def test_create(self):
        report = ScanReport(
            platform="gondola",
            total_found=10,
            new_models=3,
            updated_models=1,
            not_found_models=0,
            candidates=[],
        )
        assert report.total_found == 10
        assert report.new_models == 3
        assert report.timestamp is not None
