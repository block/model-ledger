"""JSON file LedgerBackend — human-readable, git-friendly persistence.

Stores each entity as an indented JSON file in a directory tree:

    root/
    ├── models/           # one file per ModelRef (filename: sanitized name.json)
    ├── snapshots/        # one file per Snapshot (filename: snapshot_hash.json)
    └── tags/             # organized by model_hash
        └── {model_hash}/
            └── {tag_name}.json

    >>> from model_ledger.backends.json_files import JsonFileLedgerBackend
    >>> backend = JsonFileLedgerBackend("./ledger-data")
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag

_SANITIZE_RE = re.compile(r"[/\\\s]")


def _sanitize(name: str) -> str:
    """Replace /, \\, and whitespace with underscores for safe filenames."""
    return _SANITIZE_RE.sub("_", name)


class JsonFileLedgerBackend:
    """LedgerBackend backed by a directory of JSON files."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._models_dir = self._root / "models"
        self._snapshots_dir = self._root / "snapshots"
        self._tags_dir = self._root / "tags"
        for d in (self._models_dir, self._snapshots_dir, self._tags_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    def _model_path(self, name: str) -> Path:
        return self._models_dir / f"{_sanitize(name)}.json"

    def save_model(self, model: ModelRef) -> None:
        path = self._model_path(model.name)
        path.write_text(model.model_dump_json(indent=2))

    def get_model(self, model_hash: str) -> ModelRef | None:
        for path in self._models_dir.iterdir():
            if path.suffix != ".json":
                continue
            m = ModelRef.model_validate_json(path.read_text())
            if m.model_hash == model_hash:
                return m
        return None

    def get_model_by_name(self, name: str) -> ModelRef | None:
        path = self._model_path(name)
        if path.exists():
            return ModelRef.model_validate_json(path.read_text())
        return None

    def list_models(self, **filters: str) -> list[ModelRef]:
        results: list[ModelRef] = []
        for path in sorted(self._models_dir.iterdir()):
            if path.suffix != ".json":
                continue
            m = ModelRef.model_validate_json(path.read_text())
            results.append(m)
        for key, value in filters.items():
            results = [m for m in results if getattr(m, key, None) == value]
        return results

    def update_model(self, model: ModelRef) -> None:
        self.save_model(model)

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def _snapshot_path(self, snapshot_hash: str) -> Path:
        return self._snapshots_dir / f"{snapshot_hash}.json"

    def append_snapshot(self, snapshot: Snapshot) -> None:
        path = self._snapshot_path(snapshot.snapshot_hash)
        path.write_text(snapshot.model_dump_json(indent=2))

    def get_snapshot(self, snapshot_hash: str) -> Snapshot | None:
        path = self._snapshot_path(snapshot_hash)
        if path.exists():
            return Snapshot.model_validate_json(path.read_text())
        return None

    def _iter_snapshots(self, model_hash: str) -> list[Snapshot]:
        results: list[Snapshot] = []
        for path in self._snapshots_dir.iterdir():
            if path.suffix != ".json":
                continue
            s = Snapshot.model_validate_json(path.read_text())
            if s.model_hash == model_hash:
                results.append(s)
        return results

    def list_snapshots(self, model_hash: str, **filters: str) -> list[Snapshot]:
        results = self._iter_snapshots(model_hash)
        for key, value in filters.items():
            results = [s for s in results if getattr(s, key, None) == value]
        return sorted(results, key=lambda s: s.timestamp, reverse=True)

    def latest_snapshot(self, model_hash: str, tag: str | None = None) -> Snapshot | None:
        if tag:
            t = self.get_tag(model_hash, tag)
            if t:
                return self.get_snapshot(t.snapshot_hash)
            return None
        snaps = self.list_snapshots(model_hash)
        return snaps[0] if snaps else None

    def list_snapshots_before(
        self,
        model_hash: str,
        before: datetime,
        event_type: str | None = None,
    ) -> list[Snapshot]:
        results = [s for s in self._iter_snapshots(model_hash) if s.timestamp < before]
        if event_type is not None:
            results = [s for s in results if s.event_type == event_type]
        return results

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def _tag_dir(self, model_hash: str) -> Path:
        d = self._tags_dir / model_hash
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _tag_path(self, model_hash: str, name: str) -> Path:
        return self._tag_dir(model_hash) / f"{_sanitize(name)}.json"

    def set_tag(self, tag: Tag) -> None:
        path = self._tag_path(tag.model_hash, tag.name)
        path.write_text(tag.model_dump_json(indent=2))

    def get_tag(self, model_hash: str, name: str) -> Tag | None:
        path = self._tag_path(model_hash, name)
        if path.exists():
            return Tag.model_validate_json(path.read_text())
        return None

    def list_tags(self, model_hash: str) -> list[Tag]:
        tag_dir = self._tags_dir / model_hash
        if not tag_dir.exists():
            return []
        results: list[Tag] = []
        for path in sorted(tag_dir.iterdir()):
            if path.suffix != ".json":
                continue
            results.append(Tag.model_validate_json(path.read_text()))
        return results
