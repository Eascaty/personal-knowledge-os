"""One-command, offline end-to-end automation."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import db
from .ai import adapter_from_runtime
from .config import (
    ProjectPaths,
    initialize_layout,
    load_runtime,
    load_taxonomy,
)
from .ingest import discover_files, ingest_file
from .knowledge import build_site_data, process_jobs
from .operations import (
    ProjectLock,
    run_health_checks,
    run_prebuild_gate,
    write_health_report,
)
from .site import build_site


@dataclass(frozen=True)
class AutomationResult:
    project_root: str
    ingested: int
    duplicates: int
    jobs_claimed: int
    jobs_completed: int
    jobs_retried: int
    jobs_failed: int
    documents: int
    site_output: str
    gate_allowed: bool
    health_status: str
    health_report: str
    network_requests: int = 0

    @property
    def ok(self) -> bool:
        return (
            self.jobs_failed == 0
            and self.gate_allowed
            and self.health_status != "FAIL"
        )

    def to_dict(self) -> Dict[str, object]:
        value = asdict(self)
        value["ok"] = self.ok
        return value


def _inbox_sources(paths: ProjectPaths) -> List[Path]:
    discovered = list(discover_files((paths.inbox_dir,), paths, recursive=True))
    ignored_root_files = {"readme.md", "urls.txt"}
    return [
        path
        for path in discovered
        if not (
            path.parent == paths.inbox_dir
            and path.name.casefold() in ignored_root_files
        )
    ]


def run_full_pipeline(
    project_root: Path,
    *,
    visibility: str = "private",
    max_jobs: int = 1000,
) -> AutomationResult:
    """Ingest inbox files, process knowledge, build the site and run checks."""

    if visibility not in ("private", "public"):
        raise ValueError("visibility must be private or public")
    paths = ProjectPaths.from_root(project_root)
    with ProjectLock(paths.root, purpose="full-pipeline"):
        initialize_layout(paths)
        connection = db.connect(paths.database_file)
        try:
            db.initialize_database(connection)
            taxonomy = load_taxonomy(paths)
            runtime = load_runtime(paths)
            db.sync_taxonomy(connection, taxonomy)
            ingested = 0
            duplicates = 0
            for source in _inbox_sources(paths):
                result = ingest_file(connection, paths, source, runtime)
                if result.duplicate:
                    duplicates += 1
                else:
                    ingested += 1
            summary = process_jobs(
                connection,
                paths,
                runtime,
                taxonomy,
                adapter_from_runtime(runtime),
                max_jobs=max_jobs,
            )
            canonical = build_site_data(
                connection,
                paths,
                taxonomy,
                runtime,
                visibility=visibility,
            )
            document_count = len(canonical["documents"])
        finally:
            connection.close()

        site_output = (
            paths.site_dir / "dist"
            if visibility == "private"
            else paths.exports_dir / "public"
        )
        site_result = build_site(
            paths.site_data_dir / "site-data.json",
            site_output,
            visibility=visibility,
        )
        gate = run_prebuild_gate(
            paths.root,
            canonical_path=site_output / "data" / "site-data.json",
            candidate_roots=(site_output,),
            expected_visibility=visibility,
        )
        health = run_health_checks(paths.root)
        health_path = write_health_report(health)

    return AutomationResult(
        project_root=str(paths.root),
        ingested=ingested,
        duplicates=duplicates,
        jobs_claimed=summary.claimed,
        jobs_completed=summary.completed,
        jobs_retried=summary.retried,
        jobs_failed=summary.failed,
        documents=document_count,
        site_output=str(site_result.output_dir),
        gate_allowed=gate.allowed,
        health_status=health.status.value,
        health_report=str(health_path),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m knowledge_os.automation",
        description="扫描 inbox 并离线完成入库、整理、网站构建和健康检查",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--visibility", choices=("private", "public"), default="private"
    )
    parser.add_argument("--max-jobs", type=int, default=1000)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = run_full_pipeline(
            arguments.root,
            visibility=arguments.visibility,
            max_jobs=arguments.max_jobs,
        )
    except Exception as exc:
        print(
            "knowledge-os automation: {}: {}".format(type(exc).__name__, exc),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
