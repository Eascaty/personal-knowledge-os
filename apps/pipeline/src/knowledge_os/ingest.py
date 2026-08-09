"""Immutable, content-addressed local ingestion."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from .config import ProjectPaths
from . import db


class IngestError(RuntimeError):
    pass


@dataclass(frozen=True)
class IngestResult:
    source_id: str
    sha256: str
    original_name: str
    raw_path: str
    duplicate: bool


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[\x00-\x1f/\\:]+", "-", name).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or "source.bin")[:180]


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _copy_immutable(source: Path, target: Path, expected_hash: str) -> None:
    """Atomically create target without ever overwriting an existing raw file."""

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha256_file(target) != expected_hash:
            raise IngestError(f"immutable raw path has unexpected content: {target}")
        return
    fd, temporary_name = tempfile.mkstemp(
        prefix=".incoming-", suffix=".tmp", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with source.open("rb") as source_handle, os.fdopen(fd, "wb") as target_handle:
            shutil.copyfileobj(source_handle, target_handle, length=1024 * 1024)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        if sha256_file(temporary) != expected_hash:
            raise IngestError(f"content changed while reading: {source}")
        try:
            os.link(str(temporary), str(target))
        except FileExistsError:
            if sha256_file(target) != expected_hash:
                raise IngestError(
                    f"immutable raw path has unexpected content: {target}"
                )
    finally:
        if temporary.exists():
            temporary.unlink()


def ingest_file(
    connection: Any,
    paths: ProjectPaths,
    source_path: Path,
    runtime: Mapping[str, Any],
) -> IngestResult:
    source_path = source_path.expanduser()
    if source_path.is_symlink():
        raise IngestError(f"symbolic links are not accepted as sources: {source_path}")
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise IngestError(f"not a regular file: {source_path}")
    maximum_mb = int(runtime.get("pipeline", {}).get("max_file_mb", 512))
    size_bytes = source_path.stat().st_size
    if size_bytes > maximum_mb * 1024 * 1024:
        raise IngestError(
            f"file exceeds configured {maximum_mb} MiB limit: {source_path}"
        )
    digest = sha256_file(source_path)
    source_id = f"sha256-{digest}"
    existing = db.source_by_hash(connection, digest)
    if existing is not None:
        existing_raw = paths.root / str(existing["raw_path"])
        # Re-ingesting the original can safely repair an accidentally missing
        # raw blob, but it can never replace a different existing blob.
        _copy_immutable(source_path, existing_raw, digest)
        return IngestResult(
            source_id=str(existing["id"]),
            sha256=digest,
            original_name=str(existing["original_name"]),
            raw_path=str(existing["raw_path"]),
            duplicate=True,
        )

    safe_name = _safe_filename(source_path.name)
    target = paths.raw_dir / digest[:2] / digest / safe_name
    _copy_immutable(source_path, target, digest)
    mime_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
    record = {
        "id": source_id,
        "kind": "file",
        "origin": str(source_path),
        "original_name": source_path.name,
        "raw_path": _relative_to_root(target, paths.root),
        "sha256": digest,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
    }
    inserted = db.insert_source(
        connection,
        record,
        max_attempts=int(runtime.get("pipeline", {}).get("max_attempts", 3)),
    )
    return IngestResult(
        source_id=source_id,
        sha256=digest,
        original_name=source_path.name,
        raw_path=record["raw_path"],
        duplicate=not inserted,
    )


def ingest_text(
    connection: Any,
    paths: ProjectPaths,
    text: str,
    runtime: Mapping[str, Any],
    *,
    title: str = "手工笔记",
) -> IngestResult:
    encoded = text.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    existing = db.source_by_hash(connection, digest)
    if existing is not None:
        existing_raw = paths.root / str(existing["raw_path"])
        if not existing_raw.exists():
            existing_raw.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                str(existing_raw), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        elif sha256_file(existing_raw) != digest:
            raise IngestError(
                f"immutable raw path has unexpected content: {existing_raw}"
            )
        return IngestResult(
            source_id=str(existing["id"]),
            sha256=digest,
            original_name=str(existing["original_name"]),
            raw_path=str(existing["raw_path"]),
            duplicate=True,
        )
    safe_name = _safe_filename(title)
    if not safe_name.lower().endswith(".md"):
        safe_name += ".md"
    target = paths.raw_dir / digest[:2] / digest / safe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(str(target), flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            if target.exists():
                target.unlink()
            raise
    elif sha256_file(target) != digest:
        raise IngestError(f"immutable raw path has unexpected content: {target}")
    record = {
        "id": f"sha256-{digest}",
        "kind": "text",
        "origin": "manual",
        "original_name": safe_name,
        "raw_path": _relative_to_root(target, paths.root),
        "sha256": digest,
        "mime_type": "text/markdown",
        "size_bytes": len(encoded),
    }
    inserted = db.insert_source(
        connection,
        record,
        max_attempts=int(runtime.get("pipeline", {}).get("max_attempts", 3)),
    )
    return IngestResult(
        source_id=record["id"],
        sha256=digest,
        original_name=safe_name,
        raw_path=record["raw_path"],
        duplicate=not inserted,
    )


def discover_files(
    inputs: Sequence[Path], paths: ProjectPaths, *, recursive: bool = True
) -> Iterator[Path]:
    excluded = {
        paths.data_dir.resolve(),
        paths.vault_dir.resolve(),
        paths.site_dir.resolve(),
        paths.exports_dir.resolve(),
    }
    seen: set[str] = set()

    def excluded_path(candidate: Path) -> bool:
        resolved = candidate.resolve()
        for directory in excluded:
            try:
                resolved.relative_to(directory)
                return True
            except ValueError:
                continue
        return False

    for input_path in inputs:
        unresolved = input_path.expanduser()
        if unresolved.is_symlink():
            raise IngestError(f"symbolic links are not accepted as inputs: {unresolved}")
        candidate = unresolved.resolve()
        if candidate.is_file():
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                yield candidate
            continue
        if not candidate.is_dir():
            raise IngestError(f"input does not exist: {candidate}")
        iterator: Iterable[Path]
        iterator = candidate.rglob("*") if recursive else candidate.glob("*")
        for child in sorted(iterator):
            if child.is_symlink():
                continue
            if child.is_file() and not excluded_path(child):
                resolved_child = child.resolve()
                try:
                    resolved_child.relative_to(candidate)
                except ValueError:
                    continue
                key = str(resolved_child)
                if key not in seen:
                    seen.add(key)
                    yield resolved_child
