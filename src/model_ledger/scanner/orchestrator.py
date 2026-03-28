"""InventoryScanner — orchestrates multiple scanners, deduplicates, registers."""

from __future__ import annotations

from model_ledger.scanner.protocol import ModelCandidate, Scanner
from model_ledger.scanner.report import ScanReport
from model_ledger.sdk.ledger import Ledger, ModelNotFoundError


class InventoryScanner:
    def __init__(self, ledger: Ledger, scanners: list[Scanner]) -> None:
        self._ledger = ledger
        self._scanners = {s.name: s for s in scanners}

    def discover_all(self) -> list[ScanReport]:
        reports = []
        for scanner in self._scanners.values():
            report = self._run_scanner(scanner)
            reports.append(report)
        return reports

    def scan_platform(self, platform: str) -> ScanReport:
        scanner = self._scanners.get(platform)
        if scanner is None:
            raise ValueError(f"Unknown platform: {platform}")
        return self._run_scanner(scanner)

    def _run_scanner(self, scanner: Scanner) -> ScanReport:
        candidates = scanner.scan()
        new_count = 0
        updated_count = 0

        for candidate in candidates:
            result = self._register_candidate(candidate)
            if result == "new":
                new_count += 1
            elif result == "updated":
                updated_count += 1

        return ScanReport(
            platform=scanner.name,
            total_found=len(candidates),
            new_models=new_count,
            updated_models=updated_count,
            not_found_models=0,
            candidates=candidates,
        )

    def _register_candidate(self, candidate: ModelCandidate) -> str:
        try:
            existing = self._ledger.get(candidate.name)
        except ModelNotFoundError:
            existing = None

        if existing is None:
            self._ledger.register(
                name=candidate.name,
                owner=candidate.owner or "unknown",
                model_type=candidate.model_type,
                tier="unclassified",
                purpose=f"Discovered on {candidate.platform}",
                actor=f"scanner:{candidate.platform}",
            )
            self._ledger.record(
                candidate.name,
                event="discovered",
                source=candidate.platform,
                payload={
                    "platform_id": candidate.platform_id,
                    **candidate.metadata,
                },
                actor=f"scanner:{candidate.platform}",
            )
            return "new"
        else:
            self._ledger.record(
                existing,
                event="scan_confirmed",
                source=candidate.platform,
                payload={
                    "platform_id": candidate.platform_id,
                    **candidate.metadata,
                },
                actor=f"scanner:{candidate.platform}",
            )
            return "updated"
