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
        source_root = Path(__file__).resolve().parents[1] / "src" / "knowledge_os"
        oversized = []
        for path in source_root.rglob("*.py"):
            lines = path.read_text(encoding="utf-8").count("\n") + 1
            if lines > 600:
                oversized.append(f"{path.relative_to(source_root)}:{lines}")
        self.assertEqual(oversized, [], "模块超过600行，应按职责继续拆分")


if __name__ == "__main__":
    unittest.main()
