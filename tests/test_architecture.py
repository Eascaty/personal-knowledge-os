from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from knowledge_os import __version__, db, knowledge
from knowledge_os.processing import service as processing_service
from knowledge_os.site import builder as site_builder
from knowledge_os.site.build import builder as site_build_impl
from knowledge_os.storage import sqlite as sqlite_storage


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_project_versions_stay_aligned(self):
        root = Path(__file__).resolve().parents[1]
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
        self.assertIsNotNone(match, "pyproject.toml 缺少项目版本")
        python_version = match.group(1)

        pom_root = ElementTree.parse(root / "apps" / "api" / "pom.xml").getroot()
        namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
        java_version = pom_root.findtext("m:version", namespaces=namespace)

        self.assertEqual(__version__, python_version)
        self.assertEqual(java_version, python_version)
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {python_version} —", changelog)
        java_import = (root / "scripts" / "java-import").read_text(encoding="utf-8")
        self.assertIn("-DskipTests clean package", java_import)
        self.assertIn("personal-knowledge-service-*.jar", java_import)
        self.assertIn("! -name '*.jar.original'", java_import)

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
