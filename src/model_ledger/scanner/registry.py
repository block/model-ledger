"""Scanner registry with lazy entry point discovery."""

from __future__ import annotations

from model_ledger.scanner.protocol import Scanner

ENTRY_POINT_GROUP = "model_ledger.scanners"

_registry: ScannerRegistry | None = None


class ScannerRegistry:
    def __init__(self) -> None:
        self._scanners: dict[str, Scanner] = {}
        self._discovered = False

    def register(self, scanner: Scanner) -> None:
        self._scanners[scanner.name] = scanner

    def get(self, name: str) -> Scanner:
        self._ensure_discovered()
        if name not in self._scanners:
            raise KeyError(f"No scanner registered with name: {name}")
        return self._scanners[name]

    def list_scanners(self) -> list[Scanner]:
        self._ensure_discovered()
        return list(self._scanners.values())

    def _ensure_discovered(self) -> None:
        if self._discovered:
            return
        self._discovered = True
        try:
            from importlib.metadata import entry_points

            eps = entry_points(group=ENTRY_POINT_GROUP)
            for ep in sorted(eps, key=lambda e: e.name):
                try:
                    cls = ep.load()
                    instance = cls()
                    if instance.name not in self._scanners:
                        self._scanners[instance.name] = instance
                except Exception:
                    pass
        except Exception:
            pass


def get_registry() -> ScannerRegistry:
    global _registry
    if _registry is None:
        _registry = ScannerRegistry()
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = None
