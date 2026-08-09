"""Cloudflare Pages adapter.

The default path only returns a plan.  A real deployment requires three
independent explicit confirmations and still runs the offline gate first.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

from ..config import ProjectPaths
from ..operations.gate import GateResult, run_prebuild_gate


PathLike = Union[str, os.PathLike]


class PublishError(RuntimeError):
    """Raised when an explicit publication is unsafe or fails."""


@dataclass(frozen=True)
class PublishResult:
    executed: bool
    ready: bool
    summary: str
    command: Tuple[str, ...]
    gate: GateResult
    stdout: str = ""


def _validated_project_name(value: str) -> str:
    candidate = value.strip()
    if not candidate or len(candidate) > 58:
        raise PublishError("Cloudflare Pages project name is missing or too long")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    if any(character not in allowed for character in candidate):
        raise PublishError(
            "Cloudflare Pages project name may contain lowercase letters, digits and -"
        )
    return candidate


def cloudflare_publish_plan(
    project_root: PathLike,
    *,
    project_name: str,
    visibility: str = "private",
) -> PublishResult:
    root = Path(project_root).expanduser().resolve()
    name = _validated_project_name(project_name)
    if visibility not in ("private", "public"):
        raise PublishError("visibility must be private or public")
    candidate = (
        ProjectPaths.from_root(root).site_dir / "dist"
        if visibility == "private"
        else root / "exports" / "public"
    )
    gate = run_prebuild_gate(
        root,
        canonical_path=candidate / "data" / "site-data.json",
        candidate_roots=(candidate,),
        expected_visibility=visibility,
    )
    command = (
        "wrangler",
        "pages",
        "deploy",
        str(candidate),
        "--project-name",
        name,
    )
    tool_found = shutil.which("wrangler") is not None
    ready = gate.allowed and candidate.is_dir() and tool_found
    reasons = []
    if not gate.allowed:
        reasons.append("本地门禁未通过")
    if not candidate.is_dir():
        reasons.append("站点构建目录不存在")
    if not tool_found:
        reasons.append("未安装 wrangler（不影响本地知识库）")
    return PublishResult(
        executed=False,
        ready=ready,
        summary="；".join(reasons) if reasons else "发布计划已就绪，未执行网络操作",
        command=command,
        gate=gate,
    )


def cloudflare_publish(
    project_root: PathLike,
    *,
    project_name: str,
    visibility: str = "private",
    execute: bool = False,
    allow_network: bool = False,
    access_confirmed: bool = False,
    timeout_seconds: int = 300,
) -> PublishResult:
    """Deploy only after explicit network and access-policy confirmation."""

    plan = cloudflare_publish_plan(
        project_root, project_name=project_name, visibility=visibility
    )
    if not execute:
        return plan
    if not allow_network:
        raise PublishError("real deployment requires allow_network=True")
    if visibility == "private" and not access_confirmed:
        raise PublishError(
            "private deployment requires confirmation that Cloudflare Access is active"
        )
    if not plan.gate.allowed:
        raise PublishError(plan.gate.summary)
    if shutil.which("wrangler") is None:
        raise PublishError("wrangler is not installed")
    completed = subprocess.run(
        list(plan.command),
        cwd=str(Path(project_root).expanduser().resolve()),
        check=False,
        capture_output=True,
        text=True,
        timeout=max(30, int(timeout_seconds)),
        shell=False,
        env=dict(os.environ),
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "unknown error").strip()
        raise PublishError("Cloudflare deployment failed: {}".format(message[:500]))
    return PublishResult(
        executed=True,
        ready=True,
        summary="Cloudflare Pages deployment completed",
        command=plan.command,
        gate=plan.gate,
        stdout=completed.stdout[-4000:],
    )
