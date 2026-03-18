"""SQLite storage backend with audit trail and backend-level immutability."""

from __future__ import annotations

import json
import sqlite3

from model_ledger.core.enums import VersionStatus
from model_ledger.core.exceptions import ImmutableVersionError
from model_ledger.core.models import AuditEvent, Model, ModelVersion


class SQLiteBackend:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS models (
                name TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS versions (
                model_name TEXT NOT NULL,
                version TEXT NOT NULL,
                status TEXT NOT NULL,
                data TEXT NOT NULL,
                PRIMARY KEY (model_name, version)
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                version TEXT,
                data TEXT NOT NULL
            );
        """)

    def save_model(self, model: Model) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO models (name, data) VALUES (?, ?)",
            (model.name, model.model_dump_json()),
        )
        self._conn.commit()

    def get_model(self, name: str) -> Model | None:
        row = self._conn.execute(
            "SELECT data FROM models WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return Model.model_validate_json(row[0])

    def list_models(self) -> list[Model]:
        rows = self._conn.execute("SELECT data FROM models").fetchall()
        return [Model.model_validate_json(row[0]) for row in rows]

    def save_version(self, model_name: str, version: ModelVersion) -> None:
        existing = self._conn.execute(
            "SELECT status FROM versions WHERE model_name = ? AND version = ?",
            (model_name, version.version),
        ).fetchone()
        if existing is not None and existing[0] == VersionStatus.PUBLISHED.value:
            raise ImmutableVersionError(model_name, version.version)
        self._conn.execute(
            "INSERT OR REPLACE INTO versions (model_name, version, status, data) VALUES (?, ?, ?, ?)",
            (model_name, version.version, version.status.value, version.model_dump_json()),
        )
        self._conn.commit()

    def force_save_version(self, model_name: str, version: ModelVersion) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO versions (model_name, version, status, data) VALUES (?, ?, ?, ?)",
            (model_name, version.version, version.status.value, version.model_dump_json()),
        )
        self._conn.commit()

    def get_version(self, model_name: str, version: str) -> ModelVersion | None:
        row = self._conn.execute(
            "SELECT data FROM versions WHERE model_name = ? AND version = ?",
            (model_name, version),
        ).fetchone()
        if row is None:
            return None
        return ModelVersion.model_validate_json(row[0])

    def append_audit_event(self, event: AuditEvent) -> None:
        self._conn.execute(
            "INSERT INTO audit_log (model_name, version, data) VALUES (?, ?, ?)",
            (event.model_name, event.version, event.model_dump_json()),
        )
        self._conn.commit()

    def get_audit_log(
        self, model_name: str, version: str | None = None
    ) -> list[AuditEvent]:
        if version is not None:
            rows = self._conn.execute(
                "SELECT data FROM audit_log WHERE model_name = ? AND version = ? ORDER BY id",
                (model_name, version),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT data FROM audit_log WHERE model_name = ? ORDER BY id",
                (model_name,),
            ).fetchall()
        return [AuditEvent.model_validate_json(row[0]) for row in rows]
