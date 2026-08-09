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
from .privacy import (
    _EXTERNAL_SCHEMES,
    _HTML_LINK_RE,
    _LINK_FILE_SUFFIXES,
    _MARKDOWN_LINK_RE,
    _WIKI_LINK_RE,
    _iter_public_files,
)

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


