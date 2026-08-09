"""Source records and append-only event audit."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .schema import utc_now

def add_event(
    connection: sqlite3.Connection,
    event_type: str,
    *,
    source_id: Optional[str] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> None:
    connection.execute(
        """
        INSERT INTO events(happened_at, event_type, source_id, details_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            utc_now(),
            event_type,
            source_id,
            json.dumps(dict(details or {}), ensure_ascii=False, sort_keys=True),
        ),
    )


def source_by_hash(
    connection: sqlite3.Connection, sha256: str
) -> Optional[sqlite3.Row]:
    return connection.execute(
        "SELECT * FROM sources WHERE sha256 = ?", (sha256,)
    ).fetchone()


def source_by_id(
    connection: sqlite3.Connection, source_id: str
) -> Optional[sqlite3.Row]:
    return connection.execute(
        "SELECT * FROM sources WHERE id = ?", (source_id,)
    ).fetchone()


def insert_source(
    connection: sqlite3.Connection,
    record: Mapping[str, Any],
    *,
    max_attempts: int,
) -> bool:
    """Insert a source and its first stage. Return False for a duplicate."""

    now = utc_now()
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO sources(
            id, kind, origin, original_name, raw_path, sha256, mime_type,
            size_bytes, imported_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')
        """,
        (
            record["id"],
            record["kind"],
            record["origin"],
            record["original_name"],
            record["raw_path"],
            record["sha256"],
            record["mime_type"],
            record["size_bytes"],
            now,
        ),
    )
    inserted = cursor.rowcount == 1
    if inserted:
        connection.execute(
            """
            INSERT INTO jobs(
                source_id, stage, status, attempts, max_attempts,
                available_at, created_at, updated_at
            ) VALUES (?, 'extract', 'queued', 0, ?, ?, ?, ?)
            """,
            (record["id"], max_attempts, now, now, now),
        )
        add_event(
            connection,
            "source_ingested",
            source_id=record["id"],
            details={"sha256": record["sha256"]},
        )
    connection.commit()
    return inserted



