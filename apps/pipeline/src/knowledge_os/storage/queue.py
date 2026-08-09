"""Retryable processing queue operations."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .schema import utc_now
from .records import add_event

def enqueue_job(
    connection: sqlite3.Connection,
    source_id: str,
    stage: str,
    *,
    max_attempts: int,
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT OR IGNORE INTO jobs(
            source_id, stage, status, attempts, max_attempts,
            available_at, created_at, updated_at
        ) VALUES (?, ?, 'queued', 0, ?, ?, ?, ?)
        """,
        (source_id, stage, max_attempts, now, now, now),
    )
    connection.commit()


def recover_stale_jobs(
    connection: sqlite3.Connection, stale_minutes: int
) -> int:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=max(1, stale_minutes))
    ).replace(microsecond=0).isoformat()
    cursor = connection.execute(
        """
        UPDATE jobs
        SET status='retry', available_at=?, updated_at=?,
            last_error=COALESCE(last_error, 'worker interrupted')
        WHERE status='running' AND updated_at < ?
        """,
        (utc_now(), utc_now(), cutoff),
    )
    connection.commit()
    return cursor.rowcount


def claim_next_job(connection: sqlite3.Connection) -> Optional[sqlite3.Row]:
    now = utc_now()
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute(
            """
            SELECT * FROM jobs
            WHERE status IN ('queued', 'retry')
              AND attempts < max_attempts
              AND available_at <= ?
            ORDER BY id
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if row is None:
            connection.commit()
            return None
        connection.execute(
            """
            UPDATE jobs
            SET status='running', attempts=attempts + 1, updated_at=?
            WHERE id=? AND status IN ('queued', 'retry')
            """,
            (now, row["id"]),
        )
        connection.commit()
        return connection.execute(
            "SELECT * FROM jobs WHERE id=?", (row["id"],)
        ).fetchone()
    except Exception:
        connection.rollback()
        raise


def finish_job(connection: sqlite3.Connection, job_id: int) -> None:
    now = utc_now()
    row = connection.execute(
        "SELECT source_id, stage FROM jobs WHERE id=?", (job_id,)
    ).fetchone()
    connection.execute(
        "UPDATE jobs SET status='done', last_error=NULL, updated_at=? WHERE id=?",
        (now, job_id),
    )
    if row is not None:
        add_event(
            connection,
            "job_completed",
            source_id=row["source_id"],
            details={"stage": row["stage"]},
        )
    connection.commit()


def fail_job(
    connection: sqlite3.Connection,
    job_id: int,
    error: str,
    *,
    retry_base_seconds: int,
) -> str:
    row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise KeyError(f"unknown job: {job_id}")
    final = int(row["attempts"]) >= int(row["max_attempts"])
    status = "failed" if final else "retry"
    delay = max(0, retry_base_seconds) * (2 ** max(0, int(row["attempts"]) - 1))
    available = (
        datetime.now(timezone.utc) + timedelta(seconds=delay)
    ).replace(microsecond=0).isoformat()
    now = utc_now()
    connection.execute(
        """
        UPDATE jobs
        SET status=?, available_at=?, last_error=?, updated_at=?
        WHERE id=?
        """,
        (status, available, error[:4000], now, job_id),
    )
    connection.execute(
        "UPDATE sources SET status=?, last_error=? WHERE id=?",
        (status, error[:4000], row["source_id"]),
    )
    add_event(
        connection,
        "job_failed" if final else "job_retry_scheduled",
        source_id=row["source_id"],
        details={"stage": row["stage"], "error": error[:1000]},
    )
    connection.commit()
    return status



