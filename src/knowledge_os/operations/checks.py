"""Offline health and publication-safety checks."""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import unquote, urlsplit


PathLike = Union[str, os.PathLike]


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class CheckResult:
    """One structured health-check result."""

    name: str
    status: CheckStatus
    summary: str
    details: Tuple[str, ...] = field(default_factory=tuple)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    @property
    def passed(self) -> bool:
        return self.status in (CheckStatus.PASS, CheckStatus.SKIP)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "summary": self.summary,
            "details": list(self.details),
            "metrics": dict(self.metrics),
            "duration_ms": self.duration_ms,
        }


def _duration_ms(started: float) -> int:
    return max(0, int(round((time.monotonic() - started) * 1000)))


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _label(path: Path, project_root: Optional[Path]) -> str:
    if project_root is not None:
        try:
            return path.resolve().relative_to(project_root.resolve()).as_posix()
        except (OSError, ValueError):
            pass
    return path.name


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


def _iter_public_files(root: Path) -> Iterable[Tuple[Path, bool]]:
    """Yield files and symlinks without following symlinked directories."""

    for current, directories, files in os.walk(str(root), followlinks=False):
        current_path = Path(current)
        kept_directories = []
        for directory in directories:
            candidate = current_path / directory
            if candidate.is_symlink():
                yield candidate, True
            else:
                kept_directories.append(directory)
        directories[:] = kept_directories
        for filename in files:
            candidate = current_path / filename
            yield candidate, candidate.is_symlink()


def check_privacy(
    roots: Sequence[PathLike],
    project_root: Optional[PathLike] = None,
    max_public_file_bytes: int = 5 * 1024**2,
    max_secret_scan_bytes: int = 5 * 1024**2,
) -> CheckResult:
    """Reject private artifacts, symlinks, oversized bundles, and secrets.

    Only the supplied candidate-public roots are scanned.  No network or
    external service is contacted.
    """

    started = time.monotonic()
    base = (
        Path(project_root).expanduser().resolve()
        if project_root is not None
        else None
    )
    existing = [
        Path(root).expanduser().resolve()
        for root in roots
        if Path(root).expanduser().exists()
    ]
    if not existing:
        return CheckResult(
            "privacy",
            CheckStatus.SKIP,
            "没有可扫描的公开候选目录",
            metrics={"roots_scanned": 0, "files_scanned": 0},
            duration_ms=_duration_ms(started),
        )

    issues: List[str] = []
    issue_count = 0
    files_scanned = 0
    bytes_considered = 0
    secret_matches = 0
    oversized_files = 0
    symlinks = 0

    def add_issue(message: str) -> None:
        nonlocal issue_count
        issue_count += 1
        if len(issues) < 100:
            issues.append(message)

    for root in existing:
        if not root.is_dir():
            add_issue("{}: 公开候选根目录不是目录".format(_label(root, base)))
            continue
        for path, is_symlink in _iter_public_files(root):
            relative = path.relative_to(root)
            display = _label(path, base)
            if is_symlink:
                symlinks += 1
                add_issue("{}: 公开产物不得包含符号链接".format(display))
                continue
            if not path.is_file():
                continue
            files_scanned += 1
            lowered_parts = {part.casefold() for part in relative.parts[:-1]}
            name = path.name.casefold()
            suffix = path.suffix.casefold()
            if lowered_parts & _FORBIDDEN_PARTS:
                add_issue("{}: 路径包含私密目录名".format(display))
            if name in _FORBIDDEN_NAMES or suffix in _FORBIDDEN_SUFFIXES:
                add_issue("{}: 文件类型或名称禁止发布".format(display))

            try:
                size = path.stat().st_size
            except OSError as exc:
                add_issue(
                    "{}: 无法读取文件属性 ({})".format(display, type(exc).__name__)
                )
                continue
            bytes_considered += size
            if size > max_public_file_bytes:
                oversized_files += 1
                add_issue(
                    "{}: 文件超过公开包上限 {} bytes".format(
                        display, max_public_file_bytes
                    )
                )
            if suffix not in _TEXT_SUFFIXES or size > max_secret_scan_bytes:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                add_issue("{}: 无法扫描内容 ({})".format(display, type(exc).__name__))
                continue
            for pattern_name, pattern in _SECRET_PATTERNS:
                for match in pattern.finditer(content):
                    secret_matches += 1
                    line = content.count("\n", 0, match.start()) + 1
                    add_issue(
                        "{}:{}: 疑似凭据 ({})，值已隐藏".format(
                            display, line, pattern_name
                        )
                    )

    metrics = {
        "roots_scanned": len(existing),
        "files_scanned": files_scanned,
        "bytes_considered": bytes_considered,
        "issues": issue_count,
        "secret_matches": secret_matches,
        "oversized_files": oversized_files,
        "symlinks": symlinks,
        "max_public_file_bytes": max_public_file_bytes,
    }
    if issue_count:
        summary = "公开候选内容未通过隐私检查（{} 项）".format(issue_count)
        status = CheckStatus.FAIL
        if issue_count > len(issues):
            issues.append("其余 {} 项已省略".format(issue_count - len(issues)))
    else:
        summary = "公开候选内容未发现凭据或私密文件"
        status = CheckStatus.PASS
    return CheckResult(
        "privacy",
        status,
        summary,
        tuple(issues),
        metrics,
        _duration_ms(started),
    )


_MARKDOWN_LINK_RE = re.compile(
    r"""!?\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+["'][^)]*["'])?\s*\)"""
)
_WIKI_LINK_RE = re.compile(r"(?<!!)\[\[([^\]]+)\]\]")
_HTML_LINK_RE = re.compile(
    r"""(?is)\b(?:href|src)\s*=\s*["']([^"']+)["']"""
)
_LINK_FILE_SUFFIXES = {".html", ".htm", ".md", ".markdown"}
_EXTERNAL_SCHEMES = {
    "data",
    "ftp",
    "http",
    "https",
    "irc",
    "javascript",
    "mailto",
    "news",
    "sms",
    "tel",
}


def _extract_links(path: Path, text: str) -> Iterable[Tuple[str, str]]:
    suffix = path.suffix.casefold()
    if suffix in {".md", ".markdown"}:
        for match in _MARKDOWN_LINK_RE.finditer(text):
            yield "markdown", match.group(1) or match.group(2)
        for match in _WIKI_LINK_RE.finditer(text):
            yield "wiki", match.group(1)
    if suffix in {".html", ".htm"}:
        for match in _HTML_LINK_RE.finditer(text):
            yield "html", match.group(1)


def _normal_target(raw: str) -> Optional[str]:
    target = raw.strip()
    if not target or target.startswith("#"):
        return None
    if "{{" in target or "}}" in target or "<%" in target or "%>" in target:
        return None
    parsed = urlsplit(target)
    if parsed.scheme.casefold() in _EXTERNAL_SCHEMES or target.startswith("//"):
        return None
    return unquote(parsed.path)


def _resolve_normal_link(
    source: Path, target: str, roots: Sequence[Path]
) -> Optional[Path]:
    root = roots[0]
    candidate = root / target.lstrip("/") if target.startswith("/") else source.parent / target
    candidates = [candidate]
    if not candidate.suffix:
        candidates.extend(
            [
                candidate.with_suffix(".md"),
                candidate.with_suffix(".html"),
                candidate / "index.md",
                candidate / "index.html",
            ]
        )
    elif target.endswith("/"):
        candidates.extend([candidate / "index.md", candidate / "index.html"])

    for item in candidates:
        resolved = item.resolve()
        if any(_path_within(resolved, allowed) for allowed in roots) and resolved.exists():
            return resolved
    return None


def _resolve_wiki_link(
    source: Path,
    raw_target: str,
    roots: Sequence[Path],
    markdown_by_stem: Mapping[str, Sequence[Path]],
) -> Optional[Path]:
    target = raw_target.split("|", 1)[0].split("#", 1)[0].split("^", 1)[0].strip()
    if not target:
        return source
    candidate = source.parent / target
    candidates = [candidate]
    if not candidate.suffix:
        candidates.append(candidate.with_suffix(".md"))
    for item in candidates:
        resolved = item.resolve()
        if any(_path_within(resolved, allowed) for allowed in roots) and resolved.exists():
            return resolved
    matches = markdown_by_stem.get(Path(target).stem.casefold(), ())
    return matches[0] if len(matches) == 1 else None


def check_broken_links(
    roots: Sequence[PathLike],
    project_root: Optional[PathLike] = None,
) -> CheckResult:
    """Check local Markdown/wiki/HTML links without making HTTP requests."""

    started = time.monotonic()
    base = (
        Path(project_root).expanduser().resolve()
        if project_root is not None
        else None
    )
    existing = [
        Path(root).expanduser().resolve()
        for root in roots
        if Path(root).expanduser().exists()
    ]
    if not existing:
        return CheckResult(
            "broken-links",
            CheckStatus.SKIP,
            "没有可扫描的链接目录",
            metrics={"roots_scanned": 0, "documents_scanned": 0},
            duration_ms=_duration_ms(started),
        )

    files: List[Path] = []
    markdown_by_stem: Dict[str, List[Path]] = {}
    for root in existing:
        if not root.is_dir():
            continue
        for path, is_symlink in _iter_public_files(root):
            if (
                not is_symlink
                and path.is_file()
                and path.suffix.casefold() in _LINK_FILE_SUFFIXES
            ):
                resolved = path.resolve()
                files.append(resolved)
                if resolved.suffix.casefold() in {".md", ".markdown"}:
                    markdown_by_stem.setdefault(
                        resolved.stem.casefold(), []
                    ).append(resolved)

    broken: List[str] = []
    broken_count = 0
    local_links = 0
    external_or_anchor_skipped = 0
    for source in sorted(set(files)):
        try:
            text = source.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            broken_count += 1
            if len(broken) < 100:
                broken.append(
                    "{}: 无法读取 ({})".format(_label(source, base), type(exc).__name__)
                )
            continue
        for kind, raw in _extract_links(source, text):
            if kind == "wiki":
                local_links += 1
                resolved = _resolve_wiki_link(
                    source, raw, existing, markdown_by_stem
                )
            else:
                target = _normal_target(raw)
                if target is None:
                    external_or_anchor_skipped += 1
                    continue
                local_links += 1
                resolved = _resolve_normal_link(source, target, existing)
            if resolved is None:
                broken_count += 1
                if len(broken) < 100:
                    safe_target = raw.replace("\n", " ")[:160]
                    broken.append(
                        "{}: 缺失链接 {}".format(_label(source, base), safe_target)
                    )

    if broken_count > len(broken):
        broken.append("其余 {} 项已省略".format(broken_count - len(broken)))
    metrics = {
        "roots_scanned": len(existing),
        "documents_scanned": len(set(files)),
        "local_links_checked": local_links,
        "external_or_anchor_links_skipped": external_or_anchor_skipped,
        "broken_links": broken_count,
        "network_requests": 0,
    }
    if broken_count:
        status = CheckStatus.FAIL
        summary = "发现 {} 个本地断链".format(broken_count)
    else:
        status = CheckStatus.PASS
        summary = "本地链接完整（外部链接按离线策略跳过）"
    return CheckResult(
        "broken-links",
        status,
        summary,
        tuple(broken),
        metrics,
        _duration_ms(started),
    )


def check_json_document(
    path: PathLike,
    name: str = "canonical-data",
    max_bytes: int = 5 * 1024**2,
) -> CheckResult:
    """Validate that a canonical build input is present and parseable JSON."""

    started = time.monotonic()
    json_path = Path(path).expanduser().resolve()
    if not json_path.exists():
        return CheckResult(
            name,
            CheckStatus.FAIL,
            "规范化构建数据不存在",
            (json_path.name,),
            duration_ms=_duration_ms(started),
        )
    if not json_path.is_file():
        return CheckResult(
            name,
            CheckStatus.FAIL,
            "规范化构建数据不是普通文件",
            (json_path.name,),
            duration_ms=_duration_ms(started),
        )
    size = json_path.stat().st_size
    if size > max_bytes:
        return CheckResult(
            name,
            CheckStatus.FAIL,
            "规范化构建数据超过单包上限",
            ("{} bytes > {} bytes".format(size, max_bytes),),
            metrics={"bytes": size, "max_bytes": max_bytes},
            duration_ms=_duration_ms(started),
        )
    try:
        value = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return CheckResult(
            name,
            CheckStatus.FAIL,
            "规范化构建数据不是有效 JSON",
            ("{}: {}".format(type(exc).__name__, str(exc)[:160]),),
            metrics={"bytes": size},
            duration_ms=_duration_ms(started),
        )
    if not isinstance(value, (dict, list)):
        return CheckResult(
            name,
            CheckStatus.FAIL,
            "规范化构建数据顶层必须是对象或数组",
            metrics={"bytes": size, "top_level_type": type(value).__name__},
            duration_ms=_duration_ms(started),
        )
    item_count = len(value)
    return CheckResult(
        name,
        CheckStatus.PASS,
        "规范化构建数据可读取",
        metrics={
            "bytes": size,
            "top_level_type": type(value).__name__,
            "top_level_items": item_count,
        },
        duration_ms=_duration_ms(started),
    )


_SITE_BUNDLE_FILES = {
    "_headers",
    "assets/app.js",
    "assets/styles.css",
    "build-meta.json",
    "data/graph.json",
    "data/search-index.json",
    "data/site-data.json",
    "data/taxonomy.json",
    "icons/icon-192.png",
    "icons/icon-512.png",
    "index.html",
    "manifest.webmanifest",
    "offline.html",
    "robots.txt",
    "service-worker.js",
}


def check_site_bundle(
    root: PathLike,
    *,
    expected_visibility: str,
) -> CheckResult:
    """Verify that a candidate is one complete, unmodified site build."""

    started = time.monotonic()
    bundle = Path(root).expanduser().resolve()
    if expected_visibility not in {"private", "public"}:
        return CheckResult(
            "site-bundle",
            CheckStatus.FAIL,
            "期望可见性必须是 private 或 public",
            duration_ms=_duration_ms(started),
        )
    if not bundle.is_dir():
        return CheckResult(
            "site-bundle",
            CheckStatus.FAIL,
            "候选站点目录不存在",
            (bundle.name,),
            duration_ms=_duration_ms(started),
        )
    issues: List[str] = []
    actual_files = {
        path.relative_to(bundle).as_posix()
        for path, is_symlink in _iter_public_files(bundle)
        if path.is_file() and not is_symlink
    }
    missing = sorted(_SITE_BUNDLE_FILES - actual_files)
    unexpected = sorted(actual_files - _SITE_BUNDLE_FILES)
    if missing:
        issues.append("缺少构建文件: {}".format(", ".join(missing)))
    if unexpected:
        issues.append("存在非构建器文件: {}".format(", ".join(unexpected[:20])))

    meta_path = bundle / "build-meta.json"
    data_path = bundle / "data" / "site-data.json"
    metadata: Any = {}
    site_data: Any = {}
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        site_data = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issues.append("无法读取构建清单: {}: {}".format(type(exc).__name__, str(exc)[:120]))

    if isinstance(metadata, dict) and isinstance(site_data, dict):
        if metadata.get("visibility") != expected_visibility:
            issues.append(
                "build-meta visibility={}，期望 {}".format(
                    metadata.get("visibility"), expected_visibility
                )
            )
        site_visibility = site_data.get("site", {}).get("visibility")
        if site_visibility != expected_visibility:
            issues.append(
                "site-data visibility={}，期望 {}".format(
                    site_visibility, expected_visibility
                )
            )
        documents = site_data.get("documents", [])
        if not isinstance(documents, list):
            issues.append("site-data documents 必须是数组")
            documents = []
        invalid_documents = [
            str(item.get("id", "<unknown>"))
            for item in documents
            if not isinstance(item, dict)
            or item.get("visibility") != expected_visibility
        ]
        if invalid_documents:
            issues.append(
                "文档可见性与候选包不一致: {}".format(
                    ", ".join(invalid_documents[:20])
                )
            )
        canonical_bytes = (
            json.dumps(site_data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        actual_digest = hashlib.sha256(canonical_bytes).hexdigest()
        if metadata.get("content_digest") != actual_digest:
            issues.append("site-data 内容摘要与 build-meta 不一致")
        expected_counts = {
            "document_count": len(documents),
            "node_count": len(site_data.get("nodes", []))
            if isinstance(site_data.get("nodes", []), list)
            else -1,
            "relation_count": len(site_data.get("relations", []))
            if isinstance(site_data.get("relations", []), list)
            else -1,
        }
        for field, count in expected_counts.items():
            if metadata.get(field) != count:
                issues.append(
                    "{}={}，实际 {}".format(field, metadata.get(field), count)
                )
    elif not issues:
        issues.append("构建清单顶层必须是对象")

    metrics = {
        "expected_visibility": expected_visibility,
        "files": len(actual_files),
        "missing_files": len(missing),
        "unexpected_files": len(unexpected),
        "issues": len(issues),
    }
    return CheckResult(
        "site-bundle",
        CheckStatus.FAIL if issues else CheckStatus.PASS,
        "候选站点构建清单无效" if issues else "候选站点构建清单与内容一致",
        tuple(issues),
        metrics,
        _duration_ms(started),
    )


def offline_network_check() -> CheckResult:
    """Record the intentional absence of online health checks."""

    return CheckResult(
        "online",
        CheckStatus.SKIP,
        "默认离线：未执行网络请求或线上健康检查",
        metrics={"network_requests": 0},
    )
