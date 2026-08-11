from __future__ import annotations

import unittest
from pathlib import Path

from knowledge_os import db, knowledge
from knowledge_os.processing import service as processing_service
from knowledge_os.site import builder as site_builder
from knowledge_os.site.build import builder as site_build_impl
from knowledge_os.storage import sqlite as sqlite_storage


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_legacy_facades_keep_public_entrypoints(self):
        self.assertIs(db.connect, sqlite_storage.connect)
        self.assertIs(knowledge.process_jobs, processing_service.process_jobs)
        self.assertIs(site_builder.build_site, site_build_impl.build_site)

    def test_python_implementation_modules_stay_reviewable(self):
        source_root = (
            Path(__file__).resolve().parents[1]
            / "apps"
            / "pipeline"
            / "src"
            / "knowledge_os"
        )
        oversized = []
        for path in source_root.rglob("*.py"):
            lines = path.read_text(encoding="utf-8").count("\n") + 1
            if lines > 600:
                oversized.append(f"{path.relative_to(source_root)}:{lines}")
        self.assertEqual(oversized, [], "模块超过600行，应按职责继续拆分")

    def test_python_sources_have_stable_line_endings(self):
        source_root = (
            Path(__file__).resolve().parents[1]
            / "apps"
            / "pipeline"
            / "src"
            / "knowledge_os"
        )
        violations = []
        for path in source_root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            relative_path = path.relative_to(source_root)
            if not content.endswith("\n") or content.endswith("\n\n"):
                violations.append(f"{relative_path}:文件末尾应恰好保留一个换行")
            for line_number, line in enumerate(content.splitlines(), start=1):
                if line.endswith((" ", "\t")):
                    violations.append(f"{relative_path}:{line_number}:存在行尾空白")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_http_controller_depends_on_application_service(self):
        root = Path(__file__).resolve().parents[1]
        controller = (
            root
            / "apps"
            / "api"
            / "src"
            / "main"
            / "java"
            / "io"
            / "github"
            / "eascaty"
            / "knowledge"
            / "api"
            / "KnowledgeController.java"
        ).read_text(encoding="utf-8")
        self.assertIn("KnowledgeQueryService", controller)
        self.assertNotIn("KnowledgeQueryRepository", controller)


if __name__ == "__main__":
    unittest.main()
