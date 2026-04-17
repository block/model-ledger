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
        self._has_json_extract = self._check_json_extract()

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
            CREATE INDEX IF NOT EXISTS idx_snapshots_model_ts ON snapshots(model_hash, timestamp);
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

    def _check_json_extract(self) -> bool:
        try:
            self._conn.execute("SELECT json_extract('{}', '$')").fetchone()
            return True
        except sqlite3.OperationalError:
            return False

    def _resolve_platforms_sql(
        self,
        model_hashes: list[str],
    ) -> dict[str, str | None]:
        """Resolve platform for each model hash using SQL.

        Priority: discovered event payload.platform > snapshot.source > None.
        Matches the resolution logic in ``batch_fallbacks._resolve_platform``.
        """
        if not model_hashes:
            return {}

        result: dict[str, str | None] = {mh: None for mh in model_hashes}
        placeholders = ",".join("?" * len(model_hashes))

        if self._has_json_extract:
            rows = self._conn.execute(
                f"SELECT s.model_hash, s.event_type, s.source, "
                f"json_extract(s.payload, '$.platform') AS platform "
                f"FROM snapshots s "
                f"WHERE s.model_hash IN ({placeholders}) "
                f"AND (s.event_type = 'discovered' OR s.source IS NOT NULL) "
                f"ORDER BY s.timestamp DESC",
                model_hashes,
            ).fetchall()
        else:
            rows = self._conn.execute(
                f"SELECT s.model_hash, s.event_type, s.source, s.payload "
                f"FROM snapshots s "
                f"WHERE s.model_hash IN ({placeholders}) "
                f"AND (s.event_type = 'discovered' OR s.source IS NOT NULL) "
                f"ORDER BY s.timestamp DESC",
                model_hashes,
            ).fetchall()

        platform_found: set[str] = set()
        source_fallback: dict[str, str] = {}

        for row in rows:
            mh = row["model_hash"]
            if mh in platform_found:
                continue

            if self._has_json_extract:
                platform = row["platform"]
            else:
                payload = json.loads(row["payload"]) if row["payload"] else {}
                platform = payload.get("platform")

            if row["event_type"] == "discovered" and platform:
                result[mh] = str(platform)
                platform_found.add(mh)
            elif row["source"] and mh not in source_fallback:
                source_fallback[mh] = str(row["source"])

        for mh, source in source_fallback.items():
            if mh not in platform_found:
                result[mh] = source

        return result

    def count_all_snapshots(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS cnt FROM snapshots").fetchone()
        return int(row["cnt"])

    def model_summaries(
        self,
        model_hashes: list[str],
    ) -> dict[str, dict]:
        if not model_hashes:
            return {}

        result: dict[str, dict] = {}
        for mh in model_hashes:
            result[mh] = {"last_event": None, "event_count": 0, "platform": None}

        placeholders = ",".join("?" * len(model_hashes))
        rows = self._conn.execute(
            f"SELECT s.model_hash, MAX(s.timestamp) AS last_event, COUNT(*) AS event_count "
            f"FROM snapshots s "
            f"WHERE s.model_hash IN ({placeholders}) "
            f"GROUP BY s.model_hash",
            model_hashes,
        ).fetchall()

        for row in rows:
            mh = row["model_hash"]
            result[mh]["last_event"] = datetime.fromisoformat(row["last_event"])
            result[mh]["event_count"] = row["event_count"]

        platforms = self._resolve_platforms_sql(model_hashes)
        for mh, platform in platforms.items():
            if mh in result:
                result[mh]["platform"] = platform

        return result

    def changelog_page(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        event_type: str | None = None,
        model_hash: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        conditions: list[str] = []
        params: list[str | int] = []

        if since is not None:
            conditions.append("s.timestamp >= ?")
            params.append(since.isoformat())
        if until is not None:
            conditions.append("s.timestamp <= ?")
            params.append(until.isoformat())
        if event_type is not None:
            conditions.append("s.event_type = ?")
            params.append(event_type)
        if model_hash is not None:
            conditions.append("s.model_hash = ?")
            params.append(model_hash)

        where = " AND ".join(conditions) if conditions else "1=1"

        count_row = self._conn.execute(
            f"SELECT COUNT(*) AS cnt FROM snapshots s WHERE {where}",
            params,
        ).fetchone()
        total: int = count_row["cnt"]

        data_rows = self._conn.execute(
            f"SELECT s.*, m.name AS model_name FROM snapshots s "
            f"LEFT JOIN models m ON s.model_hash = m.model_hash "
            f"WHERE {where} "
            f"ORDER BY s.timestamp DESC, s.snapshot_hash DESC "
            f"LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

        events: list[dict] = []
        for row in data_rows:
            payload = json.loads(row["payload"]) if row["payload"] else {}
            events.append(
                {
                    "model_hash": row["model_hash"],
                    "model_name": row["model_name"] or row["model_hash"],
                    "event_type": row["event_type"],
                    "timestamp": datetime.fromisoformat(row["timestamp"]),
                    "actor": row["actor"],
                    "summary": payload.get("summary"),
                    "payload": payload,
                }
            )

        return events, total

    def batch_dependencies(
        self,
        model_hash: str,
    ) -> dict[str, list[dict]]:
        upstream: list[dict] = []
        downstream: list[dict] = []

        if self._has_json_extract:
            rows = self._conn.execute(
                "SELECT s.event_type, "
                "json_extract(s.payload, '$.upstream_hash') AS upstream_hash, "
                "json_extract(s.payload, '$.upstream') AS upstream_name, "
                "json_extract(s.payload, '$.downstream_hash') AS downstream_hash, "
                "json_extract(s.payload, '$.downstream') AS downstream_name, "
                "json_extract(s.payload, '$.relationship') AS relationship "
                "FROM snapshots s "
                "WHERE s.model_hash = ? "
                "AND s.event_type IN ('depends_on', 'has_dependent')",
                (model_hash,),
            ).fetchall()

            for row in rows:
                if row["event_type"] == "depends_on":
                    related_hash = row["upstream_hash"] or ""
                    related_name = row["upstream_name"] or ""
                else:
                    related_hash = row["downstream_hash"] or ""
                    related_name = row["downstream_name"] or ""
                relationship = row["relationship"] or "depends_on"

                related = self.get_model(related_hash) if related_hash else None
                if related is None and related_name:
                    related = self.get_model_by_name(related_name)
                if related is None:
                    continue

                entry = {
                    "model_hash": related.model_hash,
                    "model_name": related.name,
                    "relationship": relationship,
                }
                if row["event_type"] == "depends_on":
                    upstream.append(entry)
                else:
                    downstream.append(entry)
        else:
            rows = self._conn.execute(
                "SELECT s.event_type, s.payload "
                "FROM snapshots s "
                "WHERE s.model_hash = ? "
                "AND s.event_type IN ('depends_on', 'has_dependent')",
                (model_hash,),
            ).fetchall()

            for row in rows:
                payload = json.loads(row["payload"]) if row["payload"] else {}
                if row["event_type"] == "depends_on":
                    related_hash = payload.get("upstream_hash", "")
                    related_name = payload.get("upstream", "")
                else:
                    related_hash = payload.get("downstream_hash", "")
                    related_name = payload.get("downstream", "")
                relationship = payload.get("relationship", "depends_on")

                related = self.get_model(related_hash) if related_hash else None
                if related is None and related_name:
                    related = self.get_model_by_name(related_name)
                if related is None:
                    continue

                entry = {
                    "model_hash": related.model_hash,
                    "model_name": related.name,
                    "relationship": relationship,
                }
                if row["event_type"] == "depends_on":
                    upstream.append(entry)
                else:
                    downstream.append(entry)

        return {"upstream": upstream, "downstream": downstream}

    def batch_platforms(
        self,
        model_hashes: list[str],
    ) -> dict[str, str | None]:
        return self._resolve_platforms_sql(model_hashes)
