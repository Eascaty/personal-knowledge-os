"""Build a public demo exclusively from checked-in synthetic fixtures."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

from . import db
from .ai import adapter_from_runtime
from .config import (
    ProjectPaths,
    atomic_write_json,
    initialize_layout,
    load_json_file,
    load_runtime,
    load_taxonomy,
)
from .ingest import ingest_file
from .knowledge import build_site_data, process_jobs
from .operations import run_prebuild_gate
from .site import build_site


DEMO_FIXTURES: Tuple[str, ...] = (
    "agent_memory.md",
    "credit_card_us_stock.md",
    "java_g1.md",
)


@dataclass(frozen=True)
class DemoBuildResult:
    output_dir: str
    documents: int
    jobs_completed: int
    gate_allowed: bool
    gate_summary: str
    network_requests: int = 0

    @property
    def ok(self) -> bool:
        return self.documents == len(DEMO_FIXTURES) and self.gate_allowed

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["ok"] = self.ok
        return payload


def _copy_public_demo_inputs(repository_root: Path, demo_paths: ProjectPaths) -> None:
    source_config = repository_root / "config"
    config_files = {}
    for name in ("taxonomy.json", "runtime.json"):
        candidate = source_config / name
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError(f"Demo 配置缺失或不是普通文件：{name}")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(repository_root)
        except ValueError as exc:
            raise ValueError(f"Demo 配置越过仓库目录：{name}") from exc
        config_files[name] = resolved
    taxonomy = load_json_file(config_files["taxonomy.json"])
    runtime = deepcopy(load_json_file(config_files["runtime.json"]))
    runtime.setdefault("site", {})["title"] = "Personal Knowledge OS · 公开演示"
    runtime["site"]["visibility"] = "public"

    demo_paths.config_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(demo_paths.taxonomy_file, taxonomy)
    atomic_write_json(demo_paths.runtime_file, runtime)
    initialize_layout(demo_paths)

    fixture_candidate = repository_root / "tests" / "fixtures"
    if fixture_candidate.is_symlink() or not fixture_candidate.is_dir():
        raise ValueError("Demo 固定样例目录缺失或不是普通目录")
    fixture_root = fixture_candidate.resolve()
    try:
        fixture_root.relative_to(repository_root)
    except ValueError as exc:
        raise ValueError("Demo 固定样例目录越过仓库目录") from exc
    inbox = demo_paths.inbox_dir / "files"
    for name in DEMO_FIXTURES:
        candidate = fixture_root / name
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError(f"Demo 样例缺失或不是普通文件：{name}")
        source = candidate.resolve()
        try:
            source.relative_to(fixture_root)
        except ValueError as exc:
            raise ValueError(f"Demo 样例越过固定目录：{name}") from exc
        shutil.copyfile(source, inbox / name)


def build_public_demo(repository_root: Path, output_dir: Path) -> DemoBuildResult:
    """Build and gate a public site without reading the user's local knowledge."""

    repository = repository_root.expanduser().resolve()
    output = output_dir.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="knowledge-os-public-demo-") as temporary:
        demo_paths = ProjectPaths.from_root(Path(temporary))
        _copy_public_demo_inputs(repository, demo_paths)
        taxonomy = load_taxonomy(demo_paths)
        runtime = load_runtime(demo_paths)
        connection = db.connect(demo_paths.database_file)
        try:
            db.initialize_database(connection)
            db.sync_taxonomy(connection, taxonomy)
            for name in DEMO_FIXTURES:
                ingest_file(
                    connection,
                    demo_paths,
                    demo_paths.inbox_dir / "files" / name,
                    runtime,
                )
            summary = process_jobs(
                connection,
                demo_paths,
                runtime,
                taxonomy,
                adapter_from_runtime(runtime),
                max_jobs=len(DEMO_FIXTURES) * 3,
            )
            expected_jobs = len(DEMO_FIXTURES) * 3
            if (
                summary.completed != expected_jobs
                or summary.claimed != expected_jobs
                or summary.failed
                or summary.retried
            ):
                raise RuntimeError(
                    "Demo 处理结果异常：claimed={} completed={} failed={} "
                    "retried={} expected={}".format(
                        summary.claimed,
                        summary.completed,
                        summary.failed,
                        summary.retried,
                        expected_jobs,
                    )
                )
            connection.execute("UPDATE documents SET visibility='public'")
            connection.commit()
            canonical = build_site_data(
                connection,
                demo_paths,
                taxonomy,
                runtime,
                visibility="public",
            )
            for node in canonical["nodes"]:
                node["visibility"] = "public"
        finally:
            connection.close()

        if len(canonical["documents"]) != len(DEMO_FIXTURES):
            raise RuntimeError(
                "Demo 文档数量异常：{}（期望 {}）".format(
                    len(canonical["documents"]), len(DEMO_FIXTURES)
                )
            )
        build_site(
            canonical,
            output,
            visibility="public",
            allow_indexing=True,
        )
        gate = run_prebuild_gate(
            demo_paths.root,
            canonical_path=output / "data" / "site-data.json",
            candidate_roots=(output,),
            expected_visibility="public",
        )
        if not gate.allowed:
            details = [detail for check in gate.failed for detail in check.details]
            raise RuntimeError(
                "Demo 发布门禁失败：{}{}".format(
                    gate.summary,
                    "；" + "；".join(details) if details else "",
                )
            )

    return DemoBuildResult(
        output_dir=str(output),
        documents=len(canonical["documents"]),
        jobs_completed=summary.completed,
        gate_allowed=gate.allowed,
        gate_summary=gate.summary,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m knowledge_os.demo",
        description="仅使用仓库虚构样例构建可公开发布的 GitHub Pages Demo",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = build_public_demo(arguments.repository_root, arguments.output)
    except Exception as exc:
        print(f"knowledge-os demo: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
