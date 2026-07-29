"""SQLite state, queue, taxonomy, and full-text index."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    try:
        connection.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        # Some in-memory/read-only SQLite contexts cannot switch journal modes.
        pass
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    metadata_exists = connection.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='metadata'
        """
    ).fetchone()
    if metadata_exists is not None:
        version_row = connection.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()
        if version_row is None:
            raise RuntimeError(
                "existing database has no schema_version; refusing implicit migration"
            )
        try:
            existing_version = int(version_row[0])
        except (TypeError, ValueError) as exc:
            raise RuntimeError("database schema_version is invalid") from exc
        if existing_version != SCHEMA_VERSION:
            raise RuntimeError(
                "unsupported database schema_version {} (expected {})".format(
                    existing_version, SCHEMA_VERSION
                )
            )
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            parent_id TEXT REFERENCES nodes(id),
            name TEXT NOT NULL,
            level INTEGER NOT NULL CHECK (level >= 0),
            path_json TEXT NOT NULL,
            locked INTEGER NOT NULL DEFAULT 0 CHECK (locked IN (0, 1)),
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            UNIQUE(parent_id, name)
        );

        CREATE INDEX IF NOT EXISTS nodes_parent_idx ON nodes(parent_id, sort_order);

        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            origin TEXT NOT NULL,
            original_name TEXT NOT NULL,
            raw_path TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            mime_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            imported_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            last_error TEXT
        );

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
            source_id TEXT NOT NULL UNIQUE REFERENCES sources(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            normalized_path TEXT NOT NULL,
            body TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            key_points_json TEXT NOT NULL DEFAULT '[]',
            tags_json TEXT NOT NULL DEFAULT '[]',
            visibility TEXT NOT NULL DEFAULT 'private'
                CHECK (visibility IN ('private', 'public')),
            model_name TEXT NOT NULL DEFAULT 'rules-v1',
            prompt_version TEXT NOT NULL DEFAULT 'extract-v1',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS placements (
            document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
            node_id TEXT NOT NULL REFERENCES nodes(id),
            confidence REAL NOT NULL DEFAULT 0,
            method TEXT NOT NULL,
            classified_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS relations (
            id TEXT PRIMARY KEY,
            from_node_id TEXT NOT NULL REFERENCES nodes(id),
            to_node_id TEXT NOT NULL REFERENCES nodes(id),
            relation_type TEXT NOT NULL,
            label TEXT NOT NULL,
            document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
            confidence REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            stage TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'retry', 'done', 'failed')),
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            available_at TEXT NOT NULL,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source_id, stage)
        );

        CREATE INDEX IF NOT EXISTS jobs_ready_idx
        ON jobs(status, available_at, id);

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            happened_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            source_id TEXT,
            details_json TEXT NOT NULL DEFAULT '{}'
        );
        """
    )
    # Trigram supports substring-style Chinese search.  It is part of FTS5 on
    # the target macOS SQLite; fail loudly if FTS5 itself is unavailable.
    try:
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                document_id UNINDEXED,
                title,
                body,
                tags,
                taxonomy_path,
                tokenize='trigram'
            )
            """
        )
        tokenizer = "trigram"
    except sqlite3.OperationalError as exc:
        if "tokenize" not in str(exc).lower():
            raise RuntimeError("SQLite must be compiled with FTS5 support") from exc
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                document_id UNINDEXED,
                title,
                body,
                tags,
                taxonomy_path,
                tokenize='unicode61'
            )
            """
        )
        tokenizer = "unicode61"
    connection.execute(
        "INSERT OR IGNORE INTO metadata(key, value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES('fts_tokenizer', ?)",
        (tokenizer,),
    )
    connection.commit()


def sync_taxonomy(
    connection: sqlite3.Connection, taxonomy: Mapping[str, Any]
) -> None:
    connection.execute("UPDATE nodes SET active = 0")

    def visit(
        node: Mapping[str, Any],
        parent_id: Optional[str],
        level: int,
        path: List[str],
        order: int,
    ) -> None:
        current_path = path + [str(node["name"])]
        connection.execute(
            """
            INSERT INTO nodes(
                id, parent_id, name, level, path_json, locked, sort_order, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                parent_id=excluded.parent_id,
                name=excluded.name,
                level=excluded.level,
                path_json=excluded.path_json,
                locked=excluded.locked,
                sort_order=excluded.sort_order,
                active=1
            """,
            (
                node["id"],
                parent_id,
                node["name"],
                level,
                json.dumps(current_path, ensure_ascii=False),
                1 if node.get("locked", False) else 0,
                order,
            ),
        )
        for child_order, child in enumerate(node.get("children", [])):
            visit(child, str(node["id"]), level + 1, current_path, child_order)

    visit(taxonomy["root"], None, 0, [], 0)
    # A taxonomy edit may retire a node that already owns documents.  Never
    # leave those placements pointing at an inactive node: move them to the
    # configured review bucket and queue enrichment/indexing again.
    uncertain_id = str(taxonomy["rules"]["uncertain_destination"])
    orphaned = connection.execute(
        """
        SELECT p.document_id
        FROM placements p
        JOIN nodes n ON n.id=p.node_id
        WHERE n.active=0
        ORDER BY p.document_id
        """
    ).fetchall()
    now = utc_now()
    for row in orphaned:
        document_id = str(row["document_id"])
        connection.execute(
            """
            UPDATE placements
            SET node_id=?, confidence=0, method='taxonomy-node-retired',
                classified_at=?
            WHERE document_id=?
            """,
            (uncertain_id, now, document_id),
        )
        connection.execute(
            "DELETE FROM documents_fts WHERE document_id=?", (document_id,)
        )
        connection.execute(
            "UPDATE sources SET status='queued', last_error=NULL WHERE id=?",
            (document_id,),
        )
        for stage in ("enrich", "index"):
            connection.execute(
                """
                INSERT INTO jobs(
                    source_id, stage, status, attempts, max_attempts,
                    available_at, created_at, updated_at
                ) VALUES (?, ?, 'queued', 0, 3, ?, ?, ?)
                ON CONFLICT(source_id, stage) DO UPDATE SET
                    status='queued', attempts=0, available_at=excluded.available_at,
                    last_error=NULL, updated_at=excluded.updated_at
                """,
                (document_id, stage, now, now, now),
            )
        add_event(
            connection,
            "placement_retired",
            source_id=document_id,
            details={"destination": uncertain_id},
        )
    connection.commit()


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


def upsert_document(
    connection: sqlite3.Connection, document: Mapping[str, Any]
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO documents(
            id, source_id, title, normalized_path, body, summary,
            key_points_json, tags_json, visibility, model_name,
            prompt_version, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            normalized_path=excluded.normalized_path,
            body=excluded.body,
            summary=excluded.summary,
            key_points_json=excluded.key_points_json,
            tags_json=excluded.tags_json,
            visibility=excluded.visibility,
            model_name=excluded.model_name,
            prompt_version=excluded.prompt_version,
            updated_at=excluded.updated_at
        """,
        (
            document["id"],
            document["source_id"],
            document["title"],
            document["normalized_path"],
            document["body"],
            document.get("summary", ""),
            json.dumps(document.get("key_points", []), ensure_ascii=False),
            json.dumps(document.get("tags", []), ensure_ascii=False),
            document.get("visibility", "private"),
            document.get("model_name", "rules-v1"),
            document.get("prompt_version", "extract-v1"),
            document.get("created_at", now),
            now,
        ),
    )
    connection.execute(
        "UPDATE sources SET status='normalized', last_error=NULL WHERE id=?",
        (document["source_id"],),
    )
    connection.commit()


def place_document(
    connection: sqlite3.Connection,
    document_id: str,
    node_id: str,
    confidence: float,
    method: str,
) -> None:
    connection.execute(
        """
        INSERT INTO placements(
            document_id, node_id, confidence, method, classified_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(document_id) DO UPDATE SET
            node_id=excluded.node_id,
            confidence=excluded.confidence,
            method=excluded.method,
            classified_at=excluded.classified_at
        """,
        (document_id, node_id, confidence, method, utc_now()),
    )
    connection.execute(
        "UPDATE sources SET status='classified', last_error=NULL WHERE id=?",
        (document_id,),
    )
    connection.commit()


def update_document_enrichment(
    connection: sqlite3.Connection,
    document_id: str,
    *,
    summary: str,
    key_points: Sequence[str],
    tags: Sequence[str],
    model_name: str,
    prompt_version: str,
) -> None:
    connection.execute(
        """
        UPDATE documents
        SET summary=?, key_points_json=?, tags_json=?, model_name=?,
            prompt_version=?, updated_at=?
        WHERE id=?
        """,
        (
            summary,
            json.dumps(list(key_points), ensure_ascii=False),
            json.dumps(list(tags), ensure_ascii=False),
            model_name,
            prompt_version,
            utc_now(),
            document_id,
        ),
    )
    connection.commit()


def index_document(connection: sqlite3.Connection, document_id: str) -> None:
    row = connection.execute(
        """
        SELECT d.id, d.title, d.body, d.tags_json, n.path_json
        FROM documents d
        JOIN placements p ON p.document_id=d.id
        JOIN nodes n ON n.id=p.node_id
        WHERE d.id=?
        """,
        (document_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"document is not ready for indexing: {document_id}")
    connection.execute(
        "DELETE FROM documents_fts WHERE document_id=?", (document_id,)
    )
    connection.execute(
        """
        INSERT INTO documents_fts(
            document_id, title, body, tags, taxonomy_path
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            row["id"],
            row["title"],
            row["body"],
            " ".join(json.loads(row["tags_json"])),
            " / ".join(json.loads(row["path_json"])),
        ),
    )
    connection.execute(
        "UPDATE sources SET status='completed', last_error=NULL WHERE id=?",
        (document_id,),
    )
    add_event(connection, "document_indexed", source_id=document_id)
    connection.commit()


def query_documents(
    connection: sqlite3.Connection, query: str, limit: int = 20
) -> List[Dict[str, Any]]:
    cleaned = query.strip()
    if not cleaned:
        return []
    safe_limit = max(1, min(int(limit), 100))
    tokenizer_row = connection.execute(
        "SELECT value FROM metadata WHERE key='fts_tokenizer'"
    ).fetchone()
    tokenizer = tokenizer_row["value"] if tokenizer_row else "trigram"
    rows: Iterable[sqlite3.Row]
    if tokenizer == "trigram" and len(cleaned) >= 3:
        expression = '"' + cleaned.replace('"', '""') + '"'
        try:
            rows = connection.execute(
                """
                SELECT d.id, d.title, d.summary, d.tags_json, d.updated_at,
                       n.id AS node_id, n.path_json,
                       bm25(documents_fts) AS rank,
                       snippet(documents_fts, 2, '<mark>', '</mark>', '…', 20)
                           AS snippet
                FROM documents_fts
                JOIN documents d ON d.id=documents_fts.document_id
                JOIN placements p ON p.document_id=d.id
                JOIN nodes n ON n.id=p.node_id
                WHERE documents_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (expression, safe_limit),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    else:
        rows = []
    materialized = list(rows)
    if not materialized:
        pattern = f"%{cleaned}%"
        materialized = connection.execute(
            """
            SELECT d.id, d.title, d.summary, d.tags_json, d.updated_at,
                   n.id AS node_id, n.path_json, 0.0 AS rank,
                   substr(d.body, 1, 300) AS snippet
            FROM documents d
            JOIN placements p ON p.document_id=d.id
            JOIN nodes n ON n.id=p.node_id
            WHERE d.title LIKE ? OR d.body LIKE ? OR d.tags_json LIKE ?
            ORDER BY d.updated_at DESC
            LIMIT ?
            """,
            (pattern, pattern, pattern, safe_limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "summary": row["summary"],
            "tags": json.loads(row["tags_json"]),
            "node_id": row["node_id"],
            "path": json.loads(row["path_json"]),
            "rank": row["rank"],
            "snippet": row["snippet"],
            "updated_at": row["updated_at"],
        }
        for row in materialized
    ]


def status_summary(connection: sqlite3.Connection) -> Dict[str, Any]:
    def grouped(table: str, column: str) -> Dict[str, int]:
        return {
            str(row[0]): int(row[1])
            for row in connection.execute(
                f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column}"
            )
        }

    counts = {
        "sources": int(connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]),
        "documents": int(
            connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        ),
        "nodes": int(
            connection.execute("SELECT COUNT(*) FROM nodes WHERE active=1").fetchone()[0]
        ),
        "relations": int(
            connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "counts": counts,
        "source_status": grouped("sources", "status"),
        "job_status": grouped("jobs", "status"),
        "last_event_at": connection.execute(
            "SELECT MAX(happened_at) FROM events"
        ).fetchone()[0],
    }
