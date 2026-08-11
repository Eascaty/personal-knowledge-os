"""Focused health and release checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import unquote, urlsplit

from .model import CheckResult, CheckStatus, _duration_ms, _label, _path_within

def check_disk(
    project_root: PathLike,
    minimum_free_bytes: int = 2 * 1024**3,
    warning_free_bytes: int = 10 * 1024**3,
) -> CheckResult:
    """Check free space on the filesystem containing the project."""

    started = time.monotonic()
    root = Path(project_root).expanduser().resolve()
    try:
        usage = shutil.disk_usage(str(root))
    except OSError as exc:
        return CheckResult(
            "disk",
            CheckStatus.FAIL,
            "无法读取项目所在磁盘容量",
            (type(exc).__name__,),
            duration_ms=_duration_ms(started),
        )

    metrics = {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "free_percent": round((usage.free / usage.total) * 100, 2)
        if usage.total
        else 0.0,
        "minimum_free_bytes": minimum_free_bytes,
        "warning_free_bytes": warning_free_bytes,
    }
    if usage.free < minimum_free_bytes:
        status = CheckStatus.FAIL
        summary = "磁盘剩余空间低于安全下限"
    elif usage.free < warning_free_bytes:
        status = CheckStatus.WARN
        summary = "磁盘剩余空间偏低"
    else:
        status = CheckStatus.PASS
        summary = "磁盘剩余空间充足"
    return CheckResult(
        "disk", status, summary, metrics=metrics, duration_ms=_duration_ms(started)
    )


def _sqlite_readonly_uri(path: Path) -> str:
    # pathlib.as_uri() percent-encodes characters and yields the URI SQLite
    # expects.  Appending mode=ro prevents accidental database creation.
    return "{}?mode=ro".format(path.resolve().as_uri())


def check_database(
    database_path: PathLike,
    required_tables: Sequence[str] = (),
    full_integrity_check: bool = False,
) -> CheckResult:
    """Run SQLite integrity, schema, and foreign-key checks without writes."""

    started = time.monotonic()
    path = Path(database_path).expanduser().resolve()
    if not path.exists():
        return CheckResult(
            "database",
            CheckStatus.FAIL,
            "SQLite 数据库不存在",
            (path.name,),
            duration_ms=_duration_ms(started),
        )
    if not path.is_file():
        return CheckResult(
            "database",
            CheckStatus.FAIL,
            "SQLite 路径不是普通文件",
            (path.name,),
            duration_ms=_duration_ms(started),
        )

    pragma = "integrity_check" if full_integrity_check else "quick_check"
    details: List[str] = []
    metrics: Dict[str, Any] = {"database_bytes": path.stat().st_size, "check": pragma}
    status = CheckStatus.PASS
    summary = "SQLite 数据库健康"

    try:
        connection = sqlite3.connect(
            _sqlite_readonly_uri(path), uri=True, timeout=2.0
        )
        try:
            connection.execute("PRAGMA query_only = ON")
            integrity_rows = [
                str(row[0]) for row in connection.execute("PRAGMA {}".format(pragma))
            ]
            integrity_ok = integrity_rows == ["ok"]
            metrics["integrity_ok"] = integrity_ok
            if not integrity_ok:
                status = CheckStatus.FAIL
                summary = "SQLite 完整性检查失败"
                details.extend(
                    "integrity: {}".format(value[:160]) for value in integrity_rows[:10]
                )

            foreign_key_rows = list(
                connection.execute("PRAGMA foreign_key_check").fetchmany(101)
            )
            metrics["foreign_key_violations"] = len(foreign_key_rows)
            if foreign_key_rows:
                status = CheckStatus.FAIL
                summary = "SQLite 外键检查失败"
                details.append(
                    "foreign_key_check reported {} violation(s){}".format(
                        min(len(foreign_key_rows), 100),
                        "+" if len(foreign_key_rows) > 100 else "",
                    )
                )

            table_rows = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            tables = {str(row[0]) for row in table_rows}
            metrics["user_table_count"] = len(tables)
            missing = sorted(set(required_tables) - tables)
            metrics["missing_required_tables"] = missing
            if missing:
                status = CheckStatus.FAIL
                summary = "SQLite 缺少必需数据表"
                details.append("missing tables: {}".format(", ".join(missing)))
            elif not tables and status != CheckStatus.FAIL:
                status = CheckStatus.WARN
                summary = "SQLite 可读取，但尚无业务数据表"

            page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
            freelist_count = int(
                connection.execute("PRAGMA freelist_count").fetchone()[0]
            )
            metrics["page_count"] = page_count
            metrics["freelist_count"] = freelist_count
        finally:
            connection.close()
    except (sqlite3.Error, OSError) as exc:
        status = CheckStatus.FAIL
        summary = "SQLite 数据库无法安全读取"
        details.append("{}: {}".format(type(exc).__name__, str(exc)[:160]))

    return CheckResult(
        "database",
        status,
        summary,
        tuple(details),
        metrics,
        _duration_ms(started),
    )


_FORBIDDEN_SUFFIXES = {
    ".db",
    ".db3",
    ".key",
    ".log",
    ".mobileprovision",
    ".p12",
    ".pem",
    ".pfx",
    ".sqlite",
    ".sqlite3",
}
_FORBIDDEN_NAMES = {
    ".env",
    ".env.local",
    "cookies",
    "cookies.sqlite",
    "credentials",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
    "secrets.json",
}
_FORBIDDEN_PARTS = {
    ".git",
    "cache",
    "inbox",
    "logs",
    "private",
    "quarantine",
    "raw",
    "state",
}
_TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".htm",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".svg",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
_SECRET_PATTERNS = (
    (
        "private-key",
        re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    ),
    (
        "authorization-bearer",
        re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    ),
    (
        "credential-assignment",
        re.compile(
            r"""(?ix)
            \b(?:api[_-]?key|api[_-]?token|access[_-]?token|auth[_-]?token|
            client[_-]?secret|password|passwd|cookie)\b
            \s*[:=]\s*
            ["']?[A-Za-z0-9._~+/=-]{12,}
            """
        ),
    ),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "github-token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ),
)
