"""InventoryScanner — orchestrates multiple scanners, deduplicates, registers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from model_ledger.core.ledger_models import ModelRef
from model_ledger.scanner.protocol import EnrichableScanner, ModelCandidate, Scanner
from model_ledger.scanner.report import ScanReport
from model_ledger.sdk.ledger import Ledger, ModelNotFoundError


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InventoryScanner:
    def __init__(
        self,
        ledger: Ledger,
        scanners: list[Scanner],
        filter_fn: Callable[[ModelCandidate], bool] | None = None,
    ) -> None:
        self._ledger = ledger
        self._scanners = {s.name: s for s in scanners}
        self._filter_fn = filter_fn

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

    def _get_last_scan_time(self, scanner_name: str) -> datetime | None:
        for model in self._ledger.list():
            snaps: list = self._ledger.history(model)  # type: ignore[assignment]
            for s in snaps:
                if s.source == scanner_name:
                    ts: datetime = s.timestamp
                    return ts
        return None

    def _run_scanner(self, scanner: Scanner) -> ScanReport:
        # Check has_changed before running full scan
        last_scan = self._get_last_scan_time(scanner.name)
        if last_scan is not None and not scanner.has_changed(last_scan):
            return ScanReport(
                platform=scanner.name,
                scan_run_id=f"{scanner.name}:{_now().isoformat()}",
                total_found=0,
                new_models=0,
                updated_models=0,
                not_found_models=0,
                candidates=[],
            )

        candidates = scanner.scan()
        if self._filter_fn:
            candidates = [c for c in candidates if self._filter_fn(c)]

        scan_run_id = f"{scanner.name}:{_now().isoformat()}"
        new_count = 0
        updated_count = 0

        found_names = {c.name for c in candidates}

        for candidate in candidates:
            result = self._register_candidate(candidate, scan_run_id)
            if result == "new":
                new_count += 1
            elif result == "updated":
                updated_count += 1

            # Enrich if scanner supports it
            if isinstance(scanner, EnrichableScanner):
                enrichment = scanner.enrich(candidate)
                if enrichment:
                    self._ledger.record(
                        candidate.name,
                        event="enriched",
                        source=scanner.name,
                        payload={**enrichment, "scan_run_id": scan_run_id},
                        actor=f"scanner:{scanner.name}",
                    )

        # Record not_found for models previously discovered on this platform
        not_found_count = 0
        for model in self._ledger.list():
            if model.name in found_names:
                continue
            if self._was_discovered_by(model, scanner.name):
                self._ledger.record(
                    model,
                    event="not_found",
                    source=scanner.name,
                    payload={"scan_run_id": scan_run_id},
                    actor=f"scanner:{scanner.name}",
                )
                not_found_count += 1

        return ScanReport(
            platform=scanner.name,
            scan_run_id=scan_run_id,
            total_found=len(candidates),
            new_models=new_count,
            updated_models=updated_count,
            not_found_models=not_found_count,
            candidates=candidates,
        )

    def _was_discovered_by(self, model: ModelRef, scanner_name: str) -> bool:
        snaps = self._ledger.history(model) or []
        return any(
            s.source == scanner_name and s.event_type in ("discovered", "scan_confirmed")
            for s in snaps
        )

    def _register_candidate(self, candidate: ModelCandidate, scan_run_id: str) -> str:
        try:
            existing = self._ledger.get(candidate.name)
        except ModelNotFoundError:
            existing = None

        payload = {
            "platform_id": candidate.platform_id,
            "scan_run_id": scan_run_id,
            **candidate.metadata,
        }

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
                payload=payload,
                actor=f"scanner:{candidate.platform}",
            )
            return "new"
        else:
            self._ledger.record(
                existing,
                event="scan_confirmed",
                source=candidate.platform,
                payload=payload,
                actor=f"scanner:{candidate.platform}",
            )
            return "updated"
