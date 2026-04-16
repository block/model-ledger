"""SQLite LedgerBackend — persistent, zero-dependency backend.

Uses stdlib sqlite3. Payload and tags stored as JSON TEXT.
WAL mode for concurrent reads. Same schema as SnowflakeLedgerBackend.

    >>> from model_ledger.backends.sqlite_ledger import SQLiteLedgerBackend
    >>> backend = SQLiteLedgerBackend("./inventory.db")
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


class SQLiteLedgerBackend:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS models (
                model_hash TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                owner TEXT NOT NULL,
                model_type TEXT NOT NULL,
                model_origin TEXT DEFAULT 'internal',
                tier TEXT NOT NULL,
                purpose TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_seen TEXT
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_hash TEXT PRIMARY KEY,
                model_hash TEXT NOT NULL,
                parent_hash TEXT,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT,
                payload TEXT,
                tags TEXT
            );
            CREATE TABLE IF NOT EXISTS tags (
                model_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (model_hash, name)
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_model ON snapshots(model_hash);
            CREATE INDEX IF NOT EXISTS idx_snapshots_event ON snapshots(event_type);
        """)

    def _model_to_row(self, m: ModelRef) -> tuple:
        return (
            m.model_hash,
            m.name,
            m.owner,
            m.model_type,
            m.model_origin,
            m.tier,
            m.purpose,
            m.status,
            m.created_at.isoformat(),
            m.last_seen.isoformat() if m.last_seen else None,
        )

    def _row_to_model(self, row: sqlite3.Row) -> ModelRef:
        last_seen = None
        try:
            if row["last_seen"]:
                last_seen = datetime.fromisoformat(row["last_seen"])
        except (KeyError, IndexError):
            pass
        return ModelRef(
            model_hash=row["model_hash"],
            name=row["name"],
            owner=row["owner"],
            model_type=row["model_type"],
            model_origin=row["model_origin"] or "internal",
            tier=row["tier"],
            purpose=row["purpose"] or "",
            status=row["status"] or "active",
            created_at=datetime.fromisoformat(row["created_at"]),
            last_seen=last_seen,
        )

    def _row_to_snapshot(self, row: sqlite3.Row) -> Snapshot:
        payload = json.loads(row["payload"]) if row["payload"] else {}
        tags = json.loads(row["tags"]) if row["tags"] else {}
        return Snapshot(
            snapshot_hash=row["snapshot_hash"],
            model_hash=row["model_hash"],
            parent_hash=row["parent_hash"],
            actor=row["actor"],
            event_type=row["event_type"],
            source=row["source"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            payload=payload,
            tags=tags,
        )

    # --- Models ---

    def save_model(self, model: ModelRef) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO models VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self._model_to_row(model),
        )
        self._conn.commit()

    def get_model(self, model_hash: str) -> ModelRef | None:
        row = self._conn.execute(
            "SELECT * FROM models WHERE model_hash = ?", (model_hash,)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def get_model_by_name(self, name: str) -> ModelRef | None:
        row = self._conn.execute("SELECT * FROM models WHERE name = ?", (name,)).fetchone()
        return self._row_to_model(row) if row else None

    def list_models(self, **filters: str) -> list[ModelRef]:
        sql = "SELECT * FROM models"
        params: list[str] = []
        if filters:
            clauses = []
            for key, value in filters.items():
                clauses.append(f"{key} = ?")
                params.append(value)
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY name"
        return [self._row_to_model(r) for r in self._conn.execute(sql, params)]

    def update_model(self, model: ModelRef) -> None:
        self.save_model(model)

    # --- Snapshots ---

    def append_snapshot(self, snapshot: Snapshot) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot.snapshot_hash,
                snapshot.model_hash,
                snapshot.parent_hash,
                snapshot.timestamp.isoformat(),
                snapshot.actor,
                snapshot.event_type,
                snapshot.source,
                json.dumps(snapshot.payload, default=str) if snapshot.payload else None,
                json.dumps(snapshot.tags, default=str) if snapshot.tags else None,
            ),
        )
        self._conn.commit()

    def get_snapshot(self, snapshot_hash: str) -> Snapshot | None:
        row = self._conn.execute(
            "SELECT * FROM snapshots WHERE snapshot_hash = ?", (snapshot_hash,)
        ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def list_snapshots(self, model_hash: str, **filters: str) -> list[Snapshot]:
        sql = "SELECT * FROM snapshots WHERE model_hash = ?"
        params: list[str] = [model_hash]
        for key, value in filters.items():
            sql += f" AND {key} = ?"
            params.append(value)
        sql += " ORDER BY timestamp"
        return [self._row_to_snapshot(r) for r in self._conn.execute(sql, params)]

    def list_all_snapshots(self, event_type: str | None = None) -> list[Snapshot]:
        if event_type:
            rows = self._conn.execute("SELECT * FROM snapshots WHERE event_type = ?", (event_type,))
        else:
            rows = self._conn.execute("SELECT * FROM snapshots")
        return [self._row_to_snapshot(r) for r in rows]

    def list_snapshot_content_hashes(self, event_type: str | None = None) -> dict[str, str]:
        snaps = self.list_all_snapshots(event_type=event_type)
        result: dict[str, str] = {}
        for s in snaps:
            h = s.payload.get("_content_hash")
            if h:
                result[s.model_hash] = h
        return result

    def latest_snapshot(self, model_hash: str, tag: str | None = None) -> Snapshot | None:
        if tag:
            t = self.get_tag(model_hash, tag)
            if t:
                return self.get_snapshot(t.snapshot_hash)
            return None
        row = self._conn.execute(
            "SELECT * FROM snapshots WHERE model_hash = ? ORDER BY timestamp DESC LIMIT 1",
            (model_hash,),
        ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def list_snapshots_before(
        self,
        model_hash: str,
        before: datetime,
        event_type: str | None = None,
    ) -> list[Snapshot]:
        sql = "SELECT * FROM snapshots WHERE model_hash = ? AND timestamp < ?"
        params: list[str] = [model_hash, before.isoformat()]
        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)
        sql += " ORDER BY timestamp"
        return [self._row_to_snapshot(r) for r in self._conn.execute(sql, params)]

    # --- Tags ---

    def set_tag(self, tag: Tag) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO tags VALUES (?, ?, ?, ?)",
            (tag.model_hash, tag.name, tag.snapshot_hash, tag.updated_at.isoformat()),
        )
        self._conn.commit()

    def get_tag(self, model_hash: str, name: str) -> Tag | None:
        row = self._conn.execute(
            "SELECT * FROM tags WHERE model_hash = ? AND name = ?",
            (model_hash, name),
        ).fetchone()
        if not row:
            return None
        return Tag(
            model_hash=row["model_hash"],
            name=row["name"],
            snapshot_hash=row["snapshot_hash"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_tags(self, model_hash: str) -> list[Tag]:
        rows = self._conn.execute(
            "SELECT * FROM tags WHERE model_hash = ? ORDER BY name",
            (model_hash,),
        )
        return [
            Tag(
                model_hash=r["model_hash"],
                name=r["name"],
                snapshot_hash=r["snapshot_hash"],
                updated_at=datetime.fromisoformat(r["updated_at"]),
            )
            for r in rows
        ]
