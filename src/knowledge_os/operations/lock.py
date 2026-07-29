"""A small, process-safe project lock.

The lock uses ``flock`` because the supported scheduler target is macOS.  The
lock file remains in place after release; ownership is represented by the
kernel lock, not by the mere presence of the file.  This avoids unsafe stale
lock deletion.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any, Dict, Optional, Union

try:
    import fcntl
except ImportError:  # pragma: no cover - the supported target is macOS/Unix.
    fcntl = None  # type: ignore[assignment]


PathLike = Union[str, os.PathLike]


class LockUnavailable(RuntimeError):
    """Raised when another process owns the project lock."""


class ProjectLock:
    """Serialize state-changing operations inside one project root.

    Parameters
    ----------
    project_root:
        Knowledge OS project directory.
    path:
        Optional explicit lock path.  The default is private state under
        ``data/state/knowledge-os.lock``.
    timeout:
        Maximum seconds to wait.  The safe default, ``0``, never blocks.
    poll_interval:
        Delay between non-blocking attempts when a timeout is requested.
    purpose:
        A short, non-secret label stored as diagnostic metadata.
    """

    def __init__(
        self,
        project_root: PathLike,
        path: Optional[PathLike] = None,
        timeout: float = 0.0,
        poll_interval: float = 0.1,
        purpose: str = "operation",
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = (
            Path(path).expanduser().resolve()
            if path is not None
            else self.project_root / "data" / "state" / "knowledge-os.lock"
        )
        self.timeout = max(0.0, float(timeout))
        self.poll_interval = max(0.01, float(poll_interval))
        self.purpose = purpose[:80]
        self._handle: Optional[IO[str]] = None
        self._token: Optional[str] = None

    @property
    def acquired(self) -> bool:
        return self._handle is not None

    def acquire(self) -> "ProjectLock":
        if self.acquired:
            return self
        if fcntl is None:
            raise RuntimeError("ProjectLock requires fcntl on this platform")

        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_RDWR | os.O_CREAT
        descriptor = os.open(str(self.path), flags, 0o600)
        handle = os.fdopen(descriptor, "r+", encoding="utf-8")
        deadline = time.monotonic() + self.timeout

        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    owner = self._read_owner(handle)
                    handle.close()
                    owner_text = self._format_owner(owner)
                    raise LockUnavailable(
                        "Knowledge OS project is already locked{}".format(owner_text)
                    )
                time.sleep(min(self.poll_interval, max(0.0, deadline - time.monotonic())))

        token = uuid.uuid4().hex
        metadata: Dict[str, Any] = {
            "schema_version": 1,
            "pid": os.getpid(),
            "purpose": self.purpose,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
            "token": token,
        }
        handle.seek(0)
        handle.truncate()
        json.dump(metadata, handle, ensure_ascii=True, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

        self._handle = handle
        self._token = token
        return self

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        self._token = None
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self) -> "ProjectLock":
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()

    @staticmethod
    def _read_owner(handle: IO[str]) -> Dict[str, Any]:
        try:
            handle.seek(0)
            value = json.load(handle)
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _format_owner(owner: Dict[str, Any]) -> str:
        parts = []
        if isinstance(owner.get("pid"), int):
            parts.append("pid={}".format(owner["pid"]))
        if isinstance(owner.get("purpose"), str):
            parts.append("purpose={}".format(owner["purpose"][:80]))
        return " ({})".format(", ".join(parts)) if parts else ""

