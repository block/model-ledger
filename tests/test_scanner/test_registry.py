"""Tests for ScannerRegistry — scanner discovery via entry_points."""

from datetime import datetime

import pytest

from model_ledger.scanner.protocol import ModelCandidate, Scanner
from model_ledger.scanner.registry import ScannerRegistry, get_registry, reset_registry


class FakeScanner:
    def __init__(self, name: str):
        self.name = name
        self.platform_type = "test"

    def scan(self) -> list[ModelCandidate]:
        return []

    def has_changed(self, last_scan: datetime) -> bool:
        return True


class TestScannerRegistry:
    def test_register_and_get(self):
        reg = ScannerRegistry()
        scanner = FakeScanner("gondola")
        reg.register(scanner)
        assert reg.get("gondola").name == "gondola"

    def test_get_unknown_raises(self):
        reg = ScannerRegistry()
        with pytest.raises(KeyError):
            reg.get("nonexistent")

    def test_list_scanners(self):
        reg = ScannerRegistry()
        reg.register(FakeScanner("a"))
        reg.register(FakeScanner("b"))
        names = [s.name for s in reg.list_scanners()]
        assert "a" in names
        assert "b" in names

    def test_register_deduplicates_by_name(self):
        reg = ScannerRegistry()
        reg.register(FakeScanner("gondola"))
        reg.register(FakeScanner("gondola"))
        assert len(reg.list_scanners()) == 1

    def test_implements_scanner_protocol(self):
        scanner = FakeScanner("test")
        assert isinstance(scanner, Scanner)


class TestGlobalRegistry:
    def setup_method(self):
        reset_registry()

    def test_get_registry_returns_same_instance(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_reset_registry(self):
        r1 = get_registry()
        reset_registry()
        r2 = get_registry()
        assert r1 is not r2
