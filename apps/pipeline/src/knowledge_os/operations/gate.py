"""Offline pre-publication gate."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

from ..config import ProjectPaths
from .checks import (
    CheckResult,
    CheckStatus,
    check_broken_links,
    check_database,
    check_json_document,
    check_privacy,
    check_site_bundle,
)


PathLike = Union[str, os.PathLike]


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    checks: Tuple[CheckResult, ...]
    summary: str

    @property
    def failed(self) -> Tuple[CheckResult, ...]:
        return tuple(
            check for check in self.checks if check.status == CheckStatus.FAIL
        )


def run_prebuild_gate(
    project_root: PathLike,
    *,
    canonical_path: Optional[PathLike] = None,
    candidate_roots: Optional[Sequence[PathLike]] = None,
    expected_visibility: str = "private",
) -> GateResult:
    """Validate canonical data, SQLite and candidate output without networking."""

    root = Path(project_root).expanduser().resolve()
    paths = ProjectPaths.from_root(root)
    if expected_visibility not in ("private", "public"):
        raise ValueError("expected_visibility must be private or public")
    candidates = (
        tuple(candidate_roots)
        if candidate_roots is not None
        else (
            paths.site_dir / "dist"
            if expected_visibility == "private"
            else root / "exports" / "public"
        ,)
    )
    if len(candidates) != 1:
        raise ValueError("publication gate requires exactly one site bundle")
    candidate = Path(candidates[0]).expanduser().resolve()
    canonical = (
        Path(canonical_path).expanduser().resolve()
        if canonical_path is not None
        else candidate / "data" / "site-data.json"
    )
    checks = (
        check_database(
            paths.database_file,
            required_tables=("documents", "jobs", "nodes", "sources"),
        ),
        check_json_document(canonical, name="canonical-data"),
        check_site_bundle(candidate, expected_visibility=expected_visibility),
        check_privacy((candidate,), project_root=root, max_public_file_bytes=25 * 1024**2),
        check_broken_links((candidate,), project_root=root),
    )
    failed = tuple(
        check for check in checks if check.status == CheckStatus.FAIL
    )
    return GateResult(
        allowed=not failed,
        checks=checks,
        summary=(
            "所有本地发布门禁通过"
            if not failed
            else "发布被 {} 项本地检查阻止".format(len(failed))
        ),
    )
