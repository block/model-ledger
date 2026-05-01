"""Snowflake LedgerBackend — implements the v0.4.0 LedgerBackend protocol.

Buffers writes and flushes in batches for performance (~16K individual
SQL statements → ~50 batched statements).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag

BATCH_SIZE = 50


def _exec(session: Any, sql: str) -> list[dict[str, Any]]:
    if hasattr(session, "execute"):
        cursor = session.execute(sql)
        if cursor.description:
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        return []
    if hasattr(session, "sql"):
        return session.sql(sql).collect()
    raise TypeError(f"Unsupported session type: {type(session)}")


def _exec_no_result(session: Any, sql: str) -> None:
    if hasattr(session, "execute"):
        session.execute(sql)
    elif hasattr(session, "sql"):
        session.sql(sql).collect()
    else:
        raise TypeError(f"Unsupported session type: {type(session)}")


def _esc(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _row_to_model_ref(row: dict[str, Any]) -> ModelRef:
    metadata = row.get("METADATA") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata) if metadata else {}
    return ModelRef(
        model_hash=row["MODEL_HASH"],
        name=row["NAME"],
        owner=row["OWNER"],
        model_type=row["MODEL_TYPE"],
        model_origin=row.get("MODEL_ORIGIN", "internal"),
        tier=row["TIER"],
        purpose=row.get("PURPOSE") or "",
        status=row.get("STATUS", "active"),
        created_at=row["CREATED_AT"]
        if isinstance(row["CREATED_AT"], datetime)
        else datetime.now(timezone.utc),
        last_seen=row.get("LAST_SEEN") if isinstance(row.get("LAST_SEEN"), datetime) else None,
        metadata=metadata if isinstance(metadata, dict) else {},
    )


def _row_to_snapshot(row: dict[str, Any]) -> Snapshot:
    payload = row.get("PAYLOAD") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    tags = row.get("TAGS") or {}
    if isinstance(tags, str):
        tags = json.loads(tags)
    ts = row.get("TIMESTAMP")
    if not isinstance(ts, datetime):
        ts = datetime.now(timezone.utc)
    return Snapshot(
        snapshot_hash=row["SNAPSHOT_HASH"],
        model_hash=row["MODEL_HASH"],
        parent_hash=row.get("PARENT_HASH"),
        timestamp=ts,
        actor=row["ACTOR"],
        event_type=row["EVENT_TYPE"],
        source=row.get("SOURCE"),
        payload=payload,
        tags=tags,
    )


def _row_to_tag(row: dict[str, Any]) -> Tag:
    return Tag(
        name=row["NAME"],
        model_hash=row["MODEL_HASH"],
        snapshot_hash=row["SNAPSHOT_HASH"],
        updated_at=row.get("UPDATED_AT", datetime.now(timezone.utc)),
    )


class SnowflakeLedgerBackend:
    """Snowflake backend implementing the LedgerBackend protocol.

    Buffers save_model() and append_snapshot() calls, flushing in batches
    of BATCH_SIZE rows. Call flush() after all writes to ensure everything
    is persisted, or use as a context manager.

    Tables: MODELS, SNAPSHOTS, TAGS in the given schema.
    """

    def __init__(
        self,
        connection: Any,
        schema: str = "MODEL_LEDGER",
        read_only: bool = False,
    ) -> None:
        self._session = connection
        self._schema = schema
        self._read_only = read_only
        parts = schema.split(".")
        self._database = parts[0] if len(parts) > 1 else None
        self._schema_name = parts[1] if len(parts) > 1 else parts[0]
        self._model_buffer: list[ModelRef] = []
        self._snapshot_buffer: list[Snapshot] = []
        if not read_only:
            self._ensure_tables()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.flush()

    def flush(self) -> None:
        """Flush all buffered writes to Snowflake."""
        self._flush_models()
        self._flush_snapshots()

    def _flush_models(self) -> None:
        if not self._model_buffer:
            return
        if self._flush_models_pandas():
            self._model_buffer.clear()
            return
        self._flush_models_sql()
        self._model_buffer.clear()

    def _flush_models_pandas(self) -> bool:
        """Bulk write via write_pandas + MERGE. Returns False if session lacks a real connection."""
        try:
            import pandas as pd
            from snowflake.connector.pandas_tools import write_pandas
        except ImportError:
            return False

        conn = self._session._connection if hasattr(self._session, "_connection") else self._session
        if not hasattr(conn, "_session_parameters"):
            return False

        df = pd.DataFrame(
            [
                {
                    "MODEL_HASH": m.model_hash,
                    "NAME": m.name,
                    "OWNER": m.owner,
                    "MODEL_TYPE": m.model_type,
                    "MODEL_ORIGIN": m.model_origin,
                    "TIER": m.tier,
                    "PURPOSE": m.purpose,
                    "STATUS": m.status,
                    "CREATED_AT": m.created_at.isoformat(),
                    "LAST_SEEN": m.last_seen.isoformat() if m.last_seen else None,
                    "METADATA": json.dumps(m.metadata, default=str) if m.metadata else None,
                }
                for m in self._model_buffer
            ]
        )

        staging = f"{self._schema}.MODELS_STAGING"
        _exec_no_result(
            self._session, f"CREATE OR REPLACE TEMPORARY TABLE {staging} LIKE {self._schema}.MODELS"
        )
        wp_kwargs: dict[str, str] = {"schema": self._schema_name}
        if self._database:
            wp_kwargs["database"] = self._database
        write_pandas(conn, df, "MODELS_STAGING", **wp_kwargs)  # type: ignore[arg-type]
        _exec_no_result(
            self._session,
            f"""
            MERGE INTO {self._schema}.MODELS t USING {staging} s ON t.MODEL_HASH = s.MODEL_HASH
            WHEN MATCHED THEN UPDATE SET
                NAME=s.NAME, OWNER=s.OWNER, MODEL_TYPE=s.MODEL_TYPE,
                MODEL_ORIGIN=s.MODEL_ORIGIN, TIER=s.TIER, PURPOSE=s.PURPOSE, STATUS=s.STATUS,
                LAST_SEEN=s.LAST_SEEN, METADATA=PARSE_JSON(s.METADATA)
            WHEN NOT MATCHED THEN INSERT
                (MODEL_HASH, NAME, OWNER, MODEL_TYPE, MODEL_ORIGIN, TIER, PURPOSE, STATUS, CREATED_AT, LAST_SEEN, METADATA)
                VALUES (s.MODEL_HASH, s.NAME, s.OWNER, s.MODEL_TYPE, s.MODEL_ORIGIN,
                        s.TIER, s.PURPOSE, s.STATUS, s.CREATED_AT, s.LAST_SEEN, PARSE_JSON(s.METADATA))""",
        )
        _exec_no_result(self._session, f"DROP TABLE IF EXISTS {staging}")
        return True

    def _flush_models_sql(self) -> None:
        """SQL MERGE fallback — works with any session type."""
        for batch in [
            self._model_buffer[i : i + BATCH_SIZE]
            for i in range(0, len(self._model_buffer), BATCH_SIZE)
        ]:
            unions = " UNION ALL ".join(
                f"SELECT {_esc(m.model_hash)} AS model_hash, {_esc(m.name)} AS name, "
                f"{_esc(m.owner)} AS owner, {_esc(m.model_type)} AS model_type, "
                f"{_esc(m.model_origin)} AS model_origin, {_esc(m.tier)} AS tier, "
                f"{_esc(m.purpose)} AS purpose, {_esc(m.status)} AS status, "
                f"{_esc(m.created_at.isoformat())} AS created_at, "
                f"{_esc(m.last_seen.isoformat()) if m.last_seen else 'NULL'} AS last_seen, "
                f"{_esc(json.dumps(m.metadata, default=str)) if m.metadata else 'NULL'} AS metadata"
                for m in batch
            )
            _exec_no_result(
                self._session,
                f"""
                MERGE INTO {self._schema}.MODELS t USING ({unions}) s ON t.MODEL_HASH = s.model_hash
                WHEN MATCHED THEN UPDATE SET
                    NAME=s.name, OWNER=s.owner, MODEL_TYPE=s.model_type,
                    MODEL_ORIGIN=s.model_origin, TIER=s.tier, PURPOSE=s.purpose, STATUS=s.status,
                    LAST_SEEN=s.last_seen, METADATA=PARSE_JSON(s.metadata)
                WHEN NOT MATCHED THEN INSERT
                    (MODEL_HASH, NAME, OWNER, MODEL_TYPE, MODEL_ORIGIN, TIER, PURPOSE, STATUS, CREATED_AT, LAST_SEEN, METADATA)
                    VALUES (s.model_hash, s.name, s.owner, s.model_type, s.model_origin,
                            s.tier, s.purpose, s.status, s.created_at, s.last_seen, PARSE_JSON(s.metadata))""",
            )

    def _flush_snapshots(self) -> None:
        if not self._snapshot_buffer:
            return
        if self._flush_snapshots_pandas():
            self._snapshot_buffer.clear()
            return
        self._flush_snapshots_sql()
        self._snapshot_buffer.clear()

    def _flush_snapshots_pandas(self) -> bool:
        """Bulk write via write_pandas + INSERT. Returns False if session lacks a real connection."""
        try:
            import pandas as pd
            from snowflake.connector.pandas_tools import write_pandas
        except ImportError:
            return False

        conn = self._session._connection if hasattr(self._session, "_connection") else self._session
        if not hasattr(conn, "_session_parameters"):
            return False

        df = pd.DataFrame(
            [
                {
                    "SNAPSHOT_HASH": s.snapshot_hash,
                    "MODEL_HASH": s.model_hash,
                    "PARENT_HASH": s.parent_hash,
                    "TIMESTAMP": s.timestamp.isoformat(),
                    "ACTOR": s.actor,
                    "EVENT_TYPE": s.event_type,
                    "SOURCE": s.source,
                    "PAYLOAD": json.dumps(s.payload, default=str) if s.payload else None,
                    "TAGS": json.dumps(s.tags, default=str) if s.tags else None,
                }
                for s in self._snapshot_buffer
            ]
        )

        staging = f"{self._schema}.SNAPSHOTS_STAGING"
        _exec_no_result(
            self._session,
            f"""
            CREATE OR REPLACE TEMPORARY TABLE {staging} (
                SNAPSHOT_HASH VARCHAR, MODEL_HASH VARCHAR, PARENT_HASH VARCHAR,
                TIMESTAMP VARCHAR, ACTOR VARCHAR, EVENT_TYPE VARCHAR,
                SOURCE VARCHAR, PAYLOAD VARCHAR, TAGS VARCHAR)""",
        )
        wp_kwargs: dict[str, str] = {"schema": self._schema_name}
        if self._database:
            wp_kwargs["database"] = self._database
        write_pandas(conn, df, "SNAPSHOTS_STAGING", **wp_kwargs)  # type: ignore[arg-type]
        _exec_no_result(
            self._session,
            f"""
            INSERT INTO {self._schema}.SNAPSHOTS
            (SNAPSHOT_HASH, MODEL_HASH, PARENT_HASH, TIMESTAMP, ACTOR, EVENT_TYPE, SOURCE, PAYLOAD, TAGS)
            SELECT SNAPSHOT_HASH, MODEL_HASH, PARENT_HASH, TIMESTAMP::TIMESTAMP_TZ, ACTOR, EVENT_TYPE, SOURCE,
                   PARSE_JSON(PAYLOAD), PARSE_JSON(TAGS)
            FROM {staging} s
            WHERE NOT EXISTS (SELECT 1 FROM {self._schema}.SNAPSHOTS t WHERE t.SNAPSHOT_HASH = s.SNAPSHOT_HASH)""",
        )
        _exec_no_result(self._session, f"DROP TABLE IF EXISTS {staging}")
        return True

    def _flush_snapshots_sql(self) -> None:
        """SQL INSERT fallback — works with any session type."""
        for batch in [
            self._snapshot_buffer[i : i + BATCH_SIZE]
            for i in range(0, len(self._snapshot_buffer), BATCH_SIZE)
        ]:
            unions = " UNION ALL ".join(
                f"SELECT {_esc(s.snapshot_hash)}, {_esc(s.model_hash)}, "
                f"{_esc(s.parent_hash)}, {_esc(s.timestamp.isoformat())}, "
                f"{_esc(s.actor)}, {_esc(s.event_type)}, {_esc(s.source)}"
                for s in batch
            )
            _exec_no_result(
                self._session,
                f"""
                INSERT INTO {self._schema}.SNAPSHOTS
                (SNAPSHOT_HASH, MODEL_HASH, PARENT_HASH, TIMESTAMP, ACTOR, EVENT_TYPE, SOURCE)
                SELECT * FROM ({unions}) s
                WHERE NOT EXISTS (SELECT 1 FROM {self._schema}.SNAPSHOTS t WHERE t.SNAPSHOT_HASH = s.$1)""",
            )

    def _ensure_tables(self) -> None:
        _exec_no_result(self._session, f"CREATE SCHEMA IF NOT EXISTS {self._schema}")
        _exec_no_result(
            self._session,
            f"""
            CREATE TABLE IF NOT EXISTS {self._schema}.MODELS (
                MODEL_HASH VARCHAR PRIMARY KEY, NAME VARCHAR UNIQUE NOT NULL,
                OWNER VARCHAR NOT NULL, MODEL_TYPE VARCHAR NOT NULL,
                MODEL_ORIGIN VARCHAR DEFAULT 'internal', TIER VARCHAR NOT NULL,
                PURPOSE VARCHAR, STATUS VARCHAR DEFAULT 'active',
                CREATED_AT TIMESTAMP_TZ NOT NULL,
                LAST_SEEN TIMESTAMP_TZ,
                METADATA VARIANT)""",
        )
        # Add METADATA column to existing tables (backward compat). New deployments
        # include METADATA in CREATE TABLE; this ALTER is a no-op there. Only swallow
        # the "already exists" case — other DDL errors (missing permission, transient
        # failure) must surface so startup doesn't silently leave MERGEs broken.
        try:
            _exec_no_result(
                self._session,
                f"ALTER TABLE {self._schema}.MODELS ADD COLUMN METADATA VARIANT",
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
        _exec_no_result(
            self._session,
            f"""
            CREATE TABLE IF NOT EXISTS {self._schema}.SNAPSHOTS (
                SNAPSHOT_HASH VARCHAR PRIMARY KEY, MODEL_HASH VARCHAR NOT NULL,
                PARENT_HASH VARCHAR, TIMESTAMP TIMESTAMP_TZ NOT NULL,
                ACTOR VARCHAR NOT NULL, EVENT_TYPE VARCHAR NOT NULL,
                SOURCE VARCHAR, PAYLOAD VARIANT, TAGS VARIANT)""",
        )
        _exec_no_result(
            self._session,
            f"""
            CREATE TABLE IF NOT EXISTS {self._schema}.TAGS (
                MODEL_HASH VARCHAR NOT NULL, NAME VARCHAR NOT NULL,
                SNAPSHOT_HASH VARCHAR NOT NULL, UPDATED_AT TIMESTAMP_TZ NOT NULL,
                PRIMARY KEY (MODEL_HASH, NAME))""",
        )

    def save_model(self, model: ModelRef) -> None:
        self._model_buffer.append(model)

    def get_model(self, model_hash: str) -> ModelRef | None:
        self._flush_models()
        rows = _exec(
            self._session,
            f"SELECT * FROM {self._schema}.MODELS WHERE MODEL_HASH = {_esc(model_hash)}",
        )
        return _row_to_model_ref(rows[0]) if rows else None

    def get_model_by_name(self, name: str) -> ModelRef | None:
        for m in self._model_buffer:
            if m.name == name:
                return m
        rows = _exec(
            self._session, f"SELECT * FROM {self._schema}.MODELS WHERE NAME = {_esc(name)}"
        )
        return _row_to_model_ref(rows[0]) if rows else None

    def list_models(self, **filters: str) -> list[ModelRef]:
        self._flush_models()
        limit = filters.pop("limit", None)
        offset = filters.pop("offset", None)
        text = filters.pop("text", None)

        sql = f"SELECT * FROM {self._schema}.MODELS"
        conditions = [f"{k.upper()} = {_esc(v)}" for k, v in filters.items()]
        if text:
            conditions.append(
                f"(LOWER(NAME) LIKE {_esc(f'%{text.lower()}%')}"
                f" OR LOWER(PURPOSE) LIKE {_esc(f'%{text.lower()}%')})"
            )
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY NAME"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        if offset is not None:
            sql += f" OFFSET {int(offset)}"
        return [_row_to_model_ref(r) for r in _exec(self._session, sql)]

    def count_models(self, **filters: str) -> int:
        """Count models matching filters without fetching all rows."""
        self._flush_models()
        text = filters.pop("text", None)
        filters.pop("limit", None)
        filters.pop("offset", None)

        sql = f"SELECT COUNT(*) AS CNT FROM {self._schema}.MODELS"
        conditions = [f"{k.upper()} = {_esc(v)}" for k, v in filters.items()]
        if text:
            conditions.append(
                f"(LOWER(NAME) LIKE {_esc(f'%{text.lower()}%')}"
                f" OR LOWER(PURPOSE) LIKE {_esc(f'%{text.lower()}%')})"
            )
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        rows = _exec(self._session, sql)
        return rows[0]["CNT"] if rows else 0

    def update_model(self, model: ModelRef) -> None:
        self.save_model(model)

    def append_snapshot(self, snapshot: Snapshot) -> None:
        self._snapshot_buffer.append(snapshot)

    def get_snapshot(self, snapshot_hash: str) -> Snapshot | None:
        self._flush_snapshots()
        rows = _exec(
            self._session,
            f"SELECT * FROM {self._schema}.SNAPSHOTS WHERE SNAPSHOT_HASH = {_esc(snapshot_hash)}",
        )
        return _row_to_snapshot(rows[0]) if rows else None

    def list_snapshots(self, model_hash: str, **filters: str) -> list[Snapshot]:
        self._flush_snapshots()
        sql = f"SELECT * FROM {self._schema}.SNAPSHOTS WHERE MODEL_HASH = {_esc(model_hash)}"
        for k, v in filters.items():
            sql += f" AND {k.upper()} = {_esc(v)}"
        sql += " ORDER BY TIMESTAMP"
        return [_row_to_snapshot(r) for r in _exec(self._session, sql)]

    def list_all_snapshots(self, event_type: str | None = None) -> list[Snapshot]:
        """Bulk load all snapshots — 1 query instead of N per-model queries."""
        self._flush_snapshots()
        sql = f"SELECT * FROM {self._schema}.SNAPSHOTS"
        if event_type:
            sql += f" WHERE EVENT_TYPE = {_esc(event_type)}"
        return [_row_to_snapshot(r) for r in _exec(self._session, sql)]

    def list_snapshot_content_hashes(self, event_type: str | None = None) -> dict[str, str]:
        """Read _content_hash from payloads — returns {model_hash: content_hash}.

        Extracts just the hash field, not the full payload. Fast and lightweight.
        """
        self._flush_snapshots()
        where = f"WHERE EVENT_TYPE = {_esc(event_type)}" if event_type else ""
        sql = f"""
            SELECT MODEL_HASH, PAYLOAD:_content_hash::VARCHAR AS CONTENT_HASH
            FROM {self._schema}.SNAPSHOTS
            {where}
            QUALIFY ROW_NUMBER() OVER (PARTITION BY MODEL_HASH ORDER BY TIMESTAMP DESC) = 1
        """
        return {
            r["MODEL_HASH"]: r["CONTENT_HASH"]
            for r in _exec(self._session, sql)
            if r.get("CONTENT_HASH")
        }

    def composite_summary(
        self,
        model_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Query V_COMPOSITES view — single query replaces N+1 per-model calls."""
        self._flush_models()
        self._flush_snapshots()
        target_types = model_types or ["composite"]
        placeholders = ", ".join(_esc(t) for t in target_types)
        sql = (
            f"SELECT NAME, OWNER, TIER, STATUS, MODEL_TYPE, MEMBER_COUNT,"
            f" LAST_VALIDATED, OPEN_OBSERVATION_COUNT,"
            f" VERSION, BUSINESS_UNIT, IN_504_SCOPE"
            f" FROM {self._schema}.V_COMPOSITES"
            f" WHERE MODEL_TYPE IN ({placeholders})"
            f" ORDER BY NAME"
        )
        rows = _exec(self._session, sql)
        return [
            {
                "name": r["NAME"],
                "owner": r["OWNER"],
                "tier": r["TIER"],
                "status": r["STATUS"],
                "model_type": r["MODEL_TYPE"],
                "member_count": r["MEMBER_COUNT"] or 0,
                "last_validated": r.get("LAST_VALIDATED"),
                "open_observation_count": r["OPEN_OBSERVATION_COUNT"] or 0,
                "version": r.get("VERSION"),
                "business_unit": r.get("BUSINESS_UNIT"),
                "in_504_scope": r.get("IN_504_SCOPE"),
            }
            for r in rows
        ]

    def latest_snapshot(self, model_hash: str, tag: str | None = None) -> Snapshot | None:
        self._flush_snapshots()
        if tag:
            t = self.get_tag(model_hash, tag)
            if t:
                return self.get_snapshot(t.snapshot_hash)
            return None
        rows = _exec(
            self._session,
            f"SELECT * FROM {self._schema}.SNAPSHOTS WHERE MODEL_HASH = {_esc(model_hash)} ORDER BY TIMESTAMP DESC LIMIT 1",
        )
        return _row_to_snapshot(rows[0]) if rows else None

    def list_snapshots_before(
        self,
        model_hash: str,
        before: datetime,
        event_type: str | None = None,
    ) -> list[Snapshot]:
        self._flush_snapshots()
        sql = (
            f"SELECT * FROM {self._schema}.SNAPSHOTS "
            f"WHERE MODEL_HASH = {_esc(model_hash)} AND TIMESTAMP < {_esc(before.isoformat())}"
        )
        if event_type:
            sql += f" AND EVENT_TYPE = {_esc(event_type)}"
        sql += " ORDER BY TIMESTAMP"
        return [_row_to_snapshot(r) for r in _exec(self._session, sql)]

    def set_tag(self, tag: Tag) -> None:
        _exec_no_result(
            self._session,
            f"""
            MERGE INTO {self._schema}.TAGS t
            USING (SELECT {_esc(tag.model_hash)} AS model_hash, {_esc(tag.name)} AS name,
                   {_esc(tag.snapshot_hash)} AS snapshot_hash,
                   {_esc(tag.updated_at.isoformat())} AS updated_at) s
            ON t.MODEL_HASH = s.model_hash AND t.NAME = s.name
            WHEN MATCHED THEN UPDATE SET SNAPSHOT_HASH = s.snapshot_hash, UPDATED_AT = s.updated_at
            WHEN NOT MATCHED THEN INSERT (MODEL_HASH, NAME, SNAPSHOT_HASH, UPDATED_AT)
                VALUES (s.model_hash, s.name, s.snapshot_hash, s.updated_at)""",
        )

    def get_tag(self, model_hash: str, name: str) -> Tag | None:
        rows = _exec(
            self._session,
            f"SELECT * FROM {self._schema}.TAGS WHERE MODEL_HASH = {_esc(model_hash)} AND NAME = {_esc(name)}",
        )
        return _row_to_tag(rows[0]) if rows else None

    def list_tags(self, model_hash: str) -> list[Tag]:
        return [
            _row_to_tag(r)
            for r in _exec(
                self._session,
                f"SELECT * FROM {self._schema}.TAGS WHERE MODEL_HASH = {_esc(model_hash)} ORDER BY NAME",
            )
        ]

    def count_all_snapshots(self) -> int:
        """Count all snapshots in a single query."""
        self._flush_snapshots()
        rows = _exec(
            self._session,
            f"SELECT COUNT(*) AS CNT FROM {self._schema}.SNAPSHOTS",
        )
        return rows[0]["CNT"] if rows else 0

    def model_summaries(
        self,
        model_hashes: list[str],
    ) -> dict[str, dict]:
        """Batch enrichment: last_event, event_count, platform per model."""
        if not model_hashes:
            return {}
        self._flush_snapshots()
        in_clause = ", ".join(_esc(h) for h in model_hashes)

        agg_rows = _exec(
            self._session,
            f"""
            SELECT MODEL_HASH,
                   MAX(TIMESTAMP) AS LAST_EVENT,
                   COUNT(*) AS EVENT_COUNT
            FROM {self._schema}.SNAPSHOTS
            WHERE MODEL_HASH IN ({in_clause})
            GROUP BY MODEL_HASH""",
        )

        plat_rows = _exec(
            self._session,
            f"""
            SELECT MODEL_HASH,
                   COALESCE(PAYLOAD:platform::VARCHAR, SOURCE) AS PLATFORM
            FROM {self._schema}.SNAPSHOTS
            WHERE MODEL_HASH IN ({in_clause})
              AND (
                  (EVENT_TYPE = 'discovered'
                   AND PAYLOAD:platform::VARCHAR IS NOT NULL)
                  OR SOURCE IS NOT NULL
              )
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY MODEL_HASH
                ORDER BY
                    CASE WHEN EVENT_TYPE = 'discovered'
                              AND PAYLOAD:platform::VARCHAR IS NOT NULL
                         THEN 0 ELSE 1 END,
                    TIMESTAMP DESC
            ) = 1""",
        )

        platform_map: dict[str, str | None] = {r["MODEL_HASH"]: r["PLATFORM"] for r in plat_rows}
        agg_map = {r["MODEL_HASH"]: r for r in agg_rows}

        result: dict[str, dict] = {}
        for mh in model_hashes:
            if mh in agg_map:
                row = agg_map[mh]
                last_event = row["LAST_EVENT"]
                if last_event is not None and not isinstance(last_event, datetime):
                    last_event = datetime.fromisoformat(str(last_event))
                result[mh] = {
                    "last_event": last_event,
                    "event_count": row["EVENT_COUNT"],
                    "platform": platform_map.get(mh),
                }
            else:
                result[mh] = {
                    "last_event": None,
                    "event_count": 0,
                    "platform": None,
                }
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
        """Server-side filtered, sorted, paginated changelog."""
        self._flush_snapshots()
        self._flush_models()

        conditions: list[str] = []
        if since is not None:
            conditions.append(f"s.TIMESTAMP >= {_esc(since.isoformat())}")
        if until is not None:
            conditions.append(f"s.TIMESTAMP <= {_esc(until.isoformat())}")
        if event_type is not None:
            conditions.append(f"s.EVENT_TYPE = {_esc(event_type)}")
        if model_hash is not None:
            conditions.append(f"s.MODEL_HASH = {_esc(model_hash)}")

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        count_rows = _exec(
            self._session,
            f"SELECT COUNT(*) AS CNT FROM {self._schema}.SNAPSHOTS s{where}",
        )
        total = count_rows[0]["CNT"] if count_rows else 0

        data_rows = _exec(
            self._session,
            f"""
            SELECT s.SNAPSHOT_HASH, s.MODEL_HASH, s.PARENT_HASH,
                   s.TIMESTAMP, s.ACTOR, s.EVENT_TYPE, s.SOURCE,
                   s.PAYLOAD, s.TAGS, m.NAME AS MODEL_NAME
            FROM {self._schema}.SNAPSHOTS s
            JOIN {self._schema}.MODELS m ON s.MODEL_HASH = m.MODEL_HASH
            {where}
            ORDER BY s.TIMESTAMP DESC, s.SNAPSHOT_HASH DESC
            LIMIT {int(limit)} OFFSET {int(offset)}""",
        )

        events: list[dict] = []
        for row in data_rows:
            payload = row.get("PAYLOAD") or {}
            if isinstance(payload, str):
                payload = json.loads(payload)
            ts = row.get("TIMESTAMP")
            if not isinstance(ts, datetime):
                ts = datetime.fromisoformat(str(ts)) if ts else datetime.now(timezone.utc)
            events.append(
                {
                    "model_hash": row["MODEL_HASH"],
                    "model_name": row["MODEL_NAME"],
                    "event_type": row["EVENT_TYPE"],
                    "timestamp": ts,
                    "actor": row.get("ACTOR"),
                    "summary": payload.get("summary") if isinstance(payload, dict) else None,
                    "payload": payload,
                }
            )

        return events, total

    def batch_dependencies(
        self,
        model_hash: str,
    ) -> dict[str, list[dict]]:
        """All dependency edges for a model via VARIANT path extraction."""
        self._flush_snapshots()
        self._flush_models()

        dep_rows = _exec(
            self._session,
            f"""
            SELECT
                EVENT_TYPE,
                PAYLOAD:upstream_hash::VARCHAR AS UPSTREAM_HASH,
                PAYLOAD:upstream::VARCHAR AS UPSTREAM_NAME,
                PAYLOAD:downstream_hash::VARCHAR AS DOWNSTREAM_HASH,
                PAYLOAD:downstream::VARCHAR AS DOWNSTREAM_NAME,
                COALESCE(PAYLOAD:relationship::VARCHAR, 'depends_on') AS RELATIONSHIP
            FROM {self._schema}.SNAPSHOTS
            WHERE MODEL_HASH = {_esc(model_hash)}
              AND EVENT_TYPE IN ('depends_on', 'has_dependent')""",
        )

        if not dep_rows:
            return {"upstream": [], "downstream": []}

        lookup_hashes: set[str] = set()
        lookup_names: set[str] = set()
        for row in dep_rows:
            if row["EVENT_TYPE"] == "depends_on":
                if row.get("UPSTREAM_HASH"):
                    lookup_hashes.add(row["UPSTREAM_HASH"])
                if row.get("UPSTREAM_NAME"):
                    lookup_names.add(row["UPSTREAM_NAME"])
            else:
                if row.get("DOWNSTREAM_HASH"):
                    lookup_hashes.add(row["DOWNSTREAM_HASH"])
                if row.get("DOWNSTREAM_NAME"):
                    lookup_names.add(row["DOWNSTREAM_NAME"])

        model_by_hash: dict[str, str] = {}
        model_by_name: dict[str, dict[str, str]] = {}
        all_lookups = lookup_hashes | lookup_names
        if all_lookups:
            hash_cond = (
                f"MODEL_HASH IN ({', '.join(_esc(h) for h in lookup_hashes)})"
                if lookup_hashes
                else None
            )
            name_cond = (
                f"NAME IN ({', '.join(_esc(n) for n in lookup_names)})" if lookup_names else None
            )
            or_clause = " OR ".join(filter(None, [hash_cond, name_cond]))
            model_rows = _exec(
                self._session,
                f"SELECT MODEL_HASH, NAME FROM {self._schema}.MODELS WHERE {or_clause}",
            )
            model_by_hash = {r["MODEL_HASH"]: r["NAME"] for r in model_rows}
            model_by_name = {
                r["NAME"]: {"MODEL_HASH": r["MODEL_HASH"], "NAME": r["NAME"]} for r in model_rows
            }

        upstream: list[dict[str, Any]] = []
        downstream: list[dict[str, Any]] = []
        for row in dep_rows:
            if row["EVENT_TYPE"] == "depends_on":
                rh = row.get("UPSTREAM_HASH") or ""
                rn = row.get("UPSTREAM_NAME") or ""
            else:
                rh = row.get("DOWNSTREAM_HASH") or ""
                rn = row.get("DOWNSTREAM_NAME") or ""

            if rh and rh in model_by_hash:
                verified_hash = rh
                verified_name = model_by_hash[rh]
            elif rn and rn in model_by_name:
                verified_hash = model_by_name[rn]["MODEL_HASH"]
                verified_name = model_by_name[rn]["NAME"]
            else:
                continue

            entry = {
                "model_hash": verified_hash,
                "model_name": verified_name,
                "relationship": row["RELATIONSHIP"],
            }
            if row["EVENT_TYPE"] == "depends_on":
                upstream.append(entry)
            else:
                downstream.append(entry)

        return {"upstream": upstream, "downstream": downstream}

    def batch_platforms(
        self,
        model_hashes: list[str],
    ) -> dict[str, str | None]:
        """Platform lookup for multiple models via VARIANT path extraction."""
        if not model_hashes:
            return {}
        self._flush_snapshots()
        in_clause = ", ".join(_esc(h) for h in model_hashes)

        plat_rows = _exec(
            self._session,
            f"""
            SELECT MODEL_HASH,
                   COALESCE(PAYLOAD:platform::VARCHAR, SOURCE) AS PLATFORM
            FROM {self._schema}.SNAPSHOTS
            WHERE MODEL_HASH IN ({in_clause})
              AND (
                  (EVENT_TYPE = 'discovered'
                   AND PAYLOAD:platform::VARCHAR IS NOT NULL)
                  OR SOURCE IS NOT NULL
              )
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY MODEL_HASH
                ORDER BY
                    CASE WHEN EVENT_TYPE = 'discovered'
                              AND PAYLOAD:platform::VARCHAR IS NOT NULL
                         THEN 0 ELSE 1 END,
                    TIMESTAMP DESC
            ) = 1""",
        )

        result: dict[str, str | None] = {mh: None for mh in model_hashes}
        for row in plat_rows:
            result[row["MODEL_HASH"]] = row["PLATFORM"]
        return result
