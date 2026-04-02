"""Scanner protocol — DEPRECATED in v0.4.0.

Use SourceConnector + DataNode + Ledger.add()/connect() instead.
Scanner and InventoryScanner still work but will be removed in v0.5.0.
"""

from model_ledger.scanner.connection import DBConnection
from model_ledger.scanner.orchestrator import InventoryScanner
from model_ledger.scanner.protocol import (
    EnrichableScanner,
    ModelCandidate,
    Scanner,
)
from model_ledger.scanner.report import ScanReport

__all__ = [
    "DBConnection",
    "EnrichableScanner",
    "InventoryScanner",
    "ModelCandidate",
    "ScanReport",
    "Scanner",
]
