"""Command-line entry point for the static site builder."""

from __future__ import annotations

import argparse
from pathlib import Path

from .builder import SiteDataError, build_site
from ..operations.lock import LockUnavailable, ProjectLock


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m knowledge_os.site",
        description="从 canonical knowledge.json 构建离线优先的静态知识网站。",
    )
    parser.add_argument("input", type=Path, help="canonical knowledge.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("workspace/site/dist"),
        help="静态站输出目录（默认：workspace/site/dist）",
    )
    parser.add_argument(
        "--visibility",
        choices=("private", "public"),
        default="private",
        help="private 包含全部整理内容；public 仅包含显式公开内容",
    )
    parser.add_argument(
        "--allow-indexing",
        action="store_true",
        help="允许搜索引擎索引；仅 public 构建可以启用",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        output = args.output.expanduser().absolute()
        project_root = (
            output.parent.parent
            if output.name == "dist" and output.parent.name == "site"
            else output.parent
        )
        with ProjectLock(project_root, purpose="site-build"):
            result = build_site(
                args.input,
                output,
                visibility=args.visibility,
                allow_indexing=args.allow_indexing,
            )
    except (LockUnavailable, OSError, SiteDataError, ValueError) as exc:
        raise SystemExit(f"网站构建失败：{exc}") from exc

    print(
        f"网站构建完成：{result.output_dir} "
        f"({result.document_count} 篇，{result.node_count} 个节点，"
        f"{result.visibility})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
