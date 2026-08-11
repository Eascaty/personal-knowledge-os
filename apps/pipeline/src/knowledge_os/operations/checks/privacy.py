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
from .database import (
    _FORBIDDEN_NAMES,
    _FORBIDDEN_PARTS,
    _FORBIDDEN_SUFFIXES,
    _SECRET_PATTERNS,
    _TEXT_SUFFIXES,
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
