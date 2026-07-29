from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_os.site import SiteDataError, build_site


def sample_data():
    return {
        "schema_version": 1,
        "generated_at": "2026-07-27T00:00:00Z",
        "root": "root",
        "site": {"title": "测试知识库"},
        "nodes": [
            {
                "id": "root",
                "parent_id": None,
                "name": "我的知识体系",
                "path": [],
            },
            {
                "id": "tech",
                "parent_id": "root",
                "name": "技术",
                "path": ["技术"],
            },
        ],
        "documents": [
            {
                "id": "public",
                "title": "公开文档",
                "summary": "公开摘要",
                "content": "PUBLIC_ONLY",
                "path": ["技术"],
                "node_id": "tech",
                "source": {
                    "origin": "https://example.com/a?X-Amz-Signature=secret",
                    "original_name": "public.md",
                },
                "evidence": [],
                "tags": ["公开"],
                "visibility": "public",
            },
            {
                "id": "private",
                "title": "私密文档",
                "summary": "私密摘要",
                "content": "PRIVATE_SENTINEL",
                "path": ["技术"],
                "node_id": "tech",
                "source": {"origin": "local-file", "original_name": "private.md"},
                "evidence": [],
                "tags": ["私密"],
                "visibility": "private",
            },
        ],
        "relations": [],
    }


class SiteBuilderTests(unittest.TestCase):
    def test_public_filters_private_and_drops_url_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "public"
            result = build_site(
                sample_data(),
                output,
                visibility="public",
                allow_indexing=True,
            )
            payload = (output / "data" / "site-data.json").read_text(
                encoding="utf-8"
            )
            self.assertEqual(result.document_count, 1)
            self.assertNotIn("PRIVATE_SENTINEL", payload)
            self.assertNotIn("X-Amz-Signature", payload)
            self.assertNotIn("secret", payload)

    def test_private_bundle_is_noindex_and_does_not_cache_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "private"
            build_site(sample_data(), output, visibility="private")
            headers = (output / "_headers").read_text(encoding="utf-8")
            worker = (output / "service-worker.js").read_text(encoding="utf-8")
            self.assertIn("X-Robots-Tag: noindex", headers)
            self.assertIn("private, no-store", headers)
            self.assertNotIn("./data/site-data.json", worker)
            self.assertIn('cache: "no-store"', worker)

    def test_bad_canonical_does_not_replace_old_site(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dist"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("old", encoding="utf-8")
            with self.assertRaises((SiteDataError, ValueError)):
                build_site(
                    {"schema_version": 1, "nodes": [], "documents": []},
                    output,
                )
            self.assertEqual(marker.read_text(encoding="utf-8"), "old")


if __name__ == "__main__":
    unittest.main()
