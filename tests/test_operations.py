from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from knowledge_os import db
from knowledge_os.operations import (
    LockUnavailable,
    ProjectLock,
    create_sqlite_snapshot,
    render_health_markdown,
    run_health_checks,
    run_prebuild_gate,
)
from knowledge_os.operations.checks import (
    CheckStatus,
    check_broken_links,
    check_privacy,
)
from knowledge_os.publish import cloudflare_publish_plan
from knowledge_os.site import build_site


class OperationsTests(unittest.TestCase):
    def _project(self, root: Path) -> None:
        (root / "data" / "state").mkdir(parents=True)
        (root / "site" / "data").mkdir(parents=True)
        (root / "site" / "dist").mkdir(parents=True)
        (root / "exports" / "public").mkdir(parents=True)
        (root / "vault").mkdir(parents=True)
        connection = db.connect(root / "data" / "state" / "knowledge.sqlite3")
        try:
            db.initialize_database(connection)
        finally:
            connection.close()
        (root / "site" / "data" / "site-data.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "taxonomy": {"id": "root", "name": "知识", "children": []},
                    "nodes": [
                        {
                            "id": "root",
                            "parent_id": None,
                            "name": "知识",
                            "path": [],
                        }
                    ],
                    "documents": [],
                    "relations": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        build_site(
            {
                "schema_version": 1,
                "generated_at": "2026-07-27T00:00:00Z",
                "root": "root",
                "site": {"title": "Knowledge OS"},
                "nodes": [
                    {
                        "id": "root",
                        "parent_id": None,
                        "name": "知识",
                        "path": [],
                    }
                ],
                "documents": [],
                "relations": [],
            },
            root / "site" / "dist",
            visibility="private",
        )

    def test_project_lock_rejects_competitor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with ProjectLock(root, purpose="first"):
                with self.assertRaises(LockUnavailable):
                    ProjectLock(root, purpose="second").acquire()

    def test_sqlite_snapshot_is_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.sqlite3"
            connection = sqlite3.connect(str(source))
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE notes(id INTEGER PRIMARY KEY, body TEXT)")
            connection.execute("INSERT INTO notes(body) VALUES('保留在一致性快照中')")
            connection.commit()
            result = create_sqlite_snapshot(source, root / "backups")
            connection.close()
            self.assertEqual(result.integrity, "ok")
            self.assertEqual(len(result.sha256), 64)
            snapshot = sqlite3.connect(str(result.snapshot))
            try:
                row = snapshot.execute("SELECT body FROM notes").fetchone()
                self.assertEqual(row[0], "保留在一致性快照中")
                self.assertEqual(
                    snapshot.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                )
            finally:
                snapshot.close()
            self.assertEqual(
                list((root / "backups").glob(".snapshot-*.tmp-*")),
                [],
            )

    def test_privacy_report_redacts_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = root / "public"
            public.mkdir()
            token = "ghp_abcdefghijklmnopqrstuvwxyz123456"
            (public / "index.js").write_text(
                'const api_token = "{}";'.format(token), encoding="utf-8"
            )
            result = check_privacy((public,), project_root=root)
            self.assertEqual(result.status, CheckStatus.FAIL)
            rendered = json.dumps(result.to_dict(), ensure_ascii=False)
            self.assertNotIn(token, rendered)
            self.assertIn("值已隐藏", rendered)

    def test_broken_links_never_request_external_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.md").write_text(
                "[外部](https://example.invalid/no-request)\n[缺失](missing.md)",
                encoding="utf-8",
            )
            result = check_broken_links((root,), project_root=root)
            self.assertEqual(result.status, CheckStatus.FAIL)
            self.assertEqual(result.metrics["network_requests"], 0)
            self.assertEqual(result.metrics["broken_links"], 1)

    def test_gate_health_and_publish_plan_are_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._project(root)
            gate = run_prebuild_gate(root)
            self.assertTrue(gate.allowed, gate.summary)
            health = run_health_checks(root)
            self.assertTrue(health.passed)
            self.assertIn("网络请求：`0`", render_health_markdown(health))
            with mock.patch(
                "knowledge_os.publish.cloudflare.shutil.which",
                return_value="/fake/wrangler",
            ), mock.patch(
                "knowledge_os.publish.cloudflare.subprocess.run"
            ) as subprocess_run:
                plan = cloudflare_publish_plan(
                    root, project_name="personal-knowledge"
                )
            subprocess_run.assert_not_called()
            self.assertFalse(plan.executed)
            self.assertTrue(plan.ready)

    def test_public_gate_rejects_private_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._project(root)
            private_data = {
                "schema_version": 1,
                "generated_at": "2026-07-27T00:00:00Z",
                "root": "root",
                "site": {"title": "Private"},
                "nodes": [
                    {
                        "id": "root",
                        "parent_id": None,
                        "name": "知识",
                        "path": [],
                    }
                ],
                "documents": [
                    {
                        "id": "private-note",
                        "title": "私密正文",
                        "summary": "不能公开",
                        "content": "PRIVATE_SENTINEL",
                        "node_id": "root",
                        "path": [],
                        "visibility": "private",
                    }
                ],
                "relations": [],
            }
            public_candidate = root / "exports" / "public"
            build_site(
                private_data,
                public_candidate,
                visibility="private",
            )
            gate = run_prebuild_gate(
                root,
                candidate_roots=(public_candidate,),
                expected_visibility="public",
            )
            self.assertFalse(gate.allowed)
            self.assertTrue(
                any(check.name == "site-bundle" for check in gate.failed)
            )


if __name__ == "__main__":
    unittest.main()
