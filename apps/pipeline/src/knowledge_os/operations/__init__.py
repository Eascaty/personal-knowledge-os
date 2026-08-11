"""Local-only operational safeguards for Knowledge OS.

The public API in this package deliberately defaults to read-only checks,
offline operation, and dry-run behaviour.  Callers must opt in explicitly to
any external side effect.
"""

from .checks import CheckResult, CheckStatus
from .gate import GateResult, run_prebuild_gate
from .health import (
    HealthReport,
    render_health_markdown,
    run_health_checks,
    write_health_report,
)
from .lock import LockUnavailable, ProjectLock
from .snapshot import SnapshotResult, create_sqlite_snapshot

__all__ = [
    "CheckResult",
    "CheckStatus",
    "GateResult",
    "HealthReport",
    "LockUnavailable",
    "ProjectLock",
    "SnapshotResult",
    "create_sqlite_snapshot",
    "render_health_markdown",
    "run_health_checks",
    "run_prebuild_gate",
    "write_health_report",
]
