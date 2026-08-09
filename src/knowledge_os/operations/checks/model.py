"""Shared check result types and path helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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



