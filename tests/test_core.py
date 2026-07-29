from __future__ import annotations

import json
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from knowledge_os import db
from knowledge_os.ai import KnowledgeExtraction, RuleBasedAdapter
from knowledge_os.config import (
    ConfigError,
    ProjectPaths,
    initialize_layout,
    load_runtime,
    load_taxonomy,
    validate_taxonomy,
)
from knowledge_os.ingest import (
    IngestError,
    discover_files,
    ingest_file,
    ingest_text,
)
from knowledge_os.knowledge import (
    build_site_data,
    classify_document,
    process_jobs,
)
from knowledge_os.site import normalize_site_data


class CorePipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.paths = ProjectPaths.from_root(self.root)
        initialize_layout(self.paths)
        self.assertTrue((self.paths.inbox_dir / "files").is_dir())
        self.runtime = load_runtime(self.paths)
        self.runtime["pipeline"]["retry_base_seconds"] = 0
        self.taxonomy = load_taxonomy(self.paths)
        self.connection = db.connect(self.paths.database_file)
        db.initialize_database(self.connection)
        db.sync_taxonomy(self.connection, self.taxonomy)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary.cleanup()

    def test_end_to_end_java_g1_and_duplicate(self) -> None:
        source_file = self.root / "input.md"
        source_file.write_text(
            "# 深入理解 G1 GC\n\n"
            "Java JVM 的垃圾回收器 G1 使用 Region，并通过 Mixed GC "
            "控制应用停顿时间。本文说明垃圾回收和性能调优。",
            encoding="utf-8",
        )
        first = ingest_file(
            self.connection, self.paths, source_file, self.runtime
        )
        second = ingest_file(
            self.connection, self.paths, source_file, self.runtime
        )
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        self.assertEqual(first.source_id, second.source_id)

        raw = self.paths.root / first.raw_path
        before = raw.read_bytes()
        summary = process_jobs(
            self.connection,
            self.paths,
            self.runtime,
            self.taxonomy,
            RuleBasedAdapter(),
            max_jobs=20,
        )
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.completed, 3)
        self.assertEqual(raw.read_bytes(), before)

        placement = self.connection.execute(
            """
            SELECT n.id, n.path_json
            FROM placements p JOIN nodes n ON n.id=p.node_id
            WHERE p.document_id=?
            """,
            (first.source_id,),
        ).fetchone()
        self.assertEqual(
            placement["id"], "technology-programmer-java-jvm-gc-g1"
        )
        self.assertIn("G1", json.loads(placement["path_json"]))
        results = db.query_documents(self.connection, "G1", limit=10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], first.source_id)

        canonical = build_site_data(
            self.connection,
            self.paths,
            self.taxonomy,
            self.runtime,
            visibility="private",
        )
        self.assertEqual(canonical["schema_version"], 1)
        self.assertEqual(len(canonical["documents"]), 1)
        document = canonical["documents"][0]
        self.assertEqual(
            document["path"],
            ["技术", "程序员", "Java开发", "JVM", "垃圾回收", "G1"],
        )
        self.assertEqual(document["visibility"], "private")
        self.assertTrue(document["evidence"])
        self.assertTrue(document["evidence"][0]["excerpt"])
        self.assertEqual(document["source"]["origin"], "local-file")
        self.assertNotIn(str(self.root), json.dumps(document, ensure_ascii=False))
        self.assertTrue((self.paths.site_data_dir / "site-data.json").is_file())
        self.assertTrue((self.paths.vault_dir / "技术" / "_index.md").is_file())

    def test_unknown_text_goes_to_uncategorized(self) -> None:
        result = ingest_text(
            self.connection,
            self.paths,
            "这是一份关于烘焙面包与天然酵母的个人记录。",
            self.runtime,
            title="周末烘焙",
        )
        summary = process_jobs(
            self.connection,
            self.paths,
            self.runtime,
            self.taxonomy,
            RuleBasedAdapter(),
            max_jobs=10,
        )
        self.assertEqual(summary.failed, 0)
        node = self.connection.execute(
            "SELECT node_id FROM placements WHERE document_id=?",
            (result.source_id,),
        ).fetchone()
        self.assertEqual(node["node_id"], "uncategorized")

    def test_invalid_adapter_path_cannot_break_parent_chain(self) -> None:
        extraction = KnowledgeExtraction(
            summary="test",
            suggested_path_ids=["root", "technology", "ai-agent"],
        )
        result = classify_document(
            title="ZGC 调优",
            body="Java JVM ZGC 垃圾回收",
            extraction=extraction,
            taxonomy=self.taxonomy,
        )
        self.assertEqual(
            result.node_id, "technology-programmer-java-jvm-gc-zgc"
        )
        self.assertEqual(result.method, "rules-stepwise")

    def test_binary_failure_is_retried_then_quarantined(self) -> None:
        self.runtime["pipeline"]["max_attempts"] = 2
        source_file = self.root / "opaque.bin"
        source_file.write_bytes(b"\x00\x01\x02\x00binary\x00")
        result = ingest_file(
            self.connection, self.paths, source_file, self.runtime
        )
        summary = process_jobs(
            self.connection,
            self.paths,
            self.runtime,
            self.taxonomy,
            RuleBasedAdapter(),
            max_jobs=10,
        )
        self.assertEqual(summary.failed, 1)
        self.assertEqual(summary.retried, 1)
        job = self.connection.execute(
            "SELECT status, attempts FROM jobs WHERE source_id=?",
            (result.source_id,),
        ).fetchone()
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["attempts"], 2)
        self.assertTrue(
            (self.paths.quarantine_dir / f"{result.source_id}.json").is_file()
        )

    def test_taxonomy_validation_rejects_duplicate_ids(self) -> None:
        invalid = {
            "version": 1,
            "rules": {"uncertain_destination": "same"},
            "root": {
                "id": "same",
                "name": "root",
                "children": [{"id": "same", "name": "child"}],
            },
        }
        with self.assertRaises(ConfigError):
            validate_taxonomy(invalid)

    def test_retired_taxonomy_node_moves_document_to_uncategorized(self) -> None:
        source_file = self.root / "g1.md"
        source_file.write_text(
            "# G1\nJava JVM G1 Region Mixed GC 垃圾回收",
            encoding="utf-8",
        )
        result = ingest_file(
            self.connection, self.paths, source_file, self.runtime
        )
        process_jobs(
            self.connection,
            self.paths,
            self.runtime,
            self.taxonomy,
            RuleBasedAdapter(),
            max_jobs=20,
        )
        changed = copy.deepcopy(self.taxonomy)
        jvm = (
            changed["root"]["children"][2]["children"][0]["children"][0][
                "children"
            ][1]
        )
        garbage_collection = next(
            child for child in jvm["children"] if child["name"] == "垃圾回收"
        )
        garbage_collection["children"] = [
            child
            for child in garbage_collection.get("children", [])
            if child["name"] != "G1"
        ]
        db.sync_taxonomy(self.connection, changed)
        placement = self.connection.execute(
            "SELECT node_id, method FROM placements WHERE document_id=?",
            (result.source_id,),
        ).fetchone()
        self.assertEqual(placement["node_id"], "uncategorized")
        self.assertEqual(placement["method"], "taxonomy-node-retired")
        canonical = build_site_data(
            self.connection,
            self.paths,
            changed,
            self.runtime,
            visibility="private",
        )
        node_ids = {node["id"] for node in canonical["nodes"]}
        self.assertTrue(
            all(item["node_id"] in node_ids for item in canonical["documents"])
        )
        normalize_site_data(canonical, visibility="private")

    def test_symlink_input_is_not_followed(self) -> None:
        outside = self.root / "outside-secret.md"
        outside.write_text("PRIVATE_OUTSIDE_SENTINEL", encoding="utf-8")
        inbox = self.root / "scan"
        inbox.mkdir()
        linked = inbox / "innocent.md"
        linked.symlink_to(outside)
        self.assertEqual(
            list(discover_files((inbox,), self.paths, recursive=True)),
            [],
        )
        with self.assertRaises(IngestError):
            ingest_file(self.connection, self.paths, linked, self.runtime)

    def test_tampered_raw_path_cannot_escape_project(self) -> None:
        self.runtime["pipeline"]["max_attempts"] = 1
        source_file = self.root / "input.md"
        source_file.write_text("# Safe\nJava", encoding="utf-8")
        result = ingest_file(
            self.connection, self.paths, source_file, self.runtime
        )
        outside = self.root.parent / (
            self.root.name + "-outside-raw-sentinel.md"
        )
        outside.write_text("SHOULD_NOT_BE_IMPORTED", encoding="utf-8")
        self.addCleanup(outside.unlink, missing_ok=True)
        self.connection.execute(
            "UPDATE sources SET raw_path=? WHERE id=?",
            ("../" + outside.name, result.source_id),
        )
        self.connection.commit()
        summary = process_jobs(
            self.connection,
            self.paths,
            self.runtime,
            self.taxonomy,
            RuleBasedAdapter(),
            max_jobs=5,
        )
        self.assertEqual(summary.failed, 1)
        self.assertIsNone(
            self.connection.execute(
                "SELECT id FROM documents WHERE id=?", (result.source_id,)
            ).fetchone()
        )


if __name__ == "__main__":
    unittest.main()
