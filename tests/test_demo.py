from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_os.demo import DEMO_FIXTURES, build_public_demo


class PublicDemoTests(unittest.TestCase):
    def test_demo_uses_only_synthetic_public_fixtures(self):
        repository = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "public-demo"
            result = build_public_demo(repository, output)
            self.assertTrue(result.ok)
            self.assertEqual(result.documents, len(DEMO_FIXTURES))
            self.assertEqual(result.jobs_completed, len(DEMO_FIXTURES) * 3)
            self.assertTrue(result.gate_allowed)

            payload = json.loads(
                (output / "data" / "site-data.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["site"]["visibility"], "public")
            self.assertEqual(
                {item["source"]["original_name"] for item in payload["documents"]},
                set(DEMO_FIXTURES),
            )
            self.assertTrue(
                all(item["visibility"] == "public" for item in payload["documents"])
            )
            self.assertTrue(
                all(item["visibility"] == "public" for item in payload["nodes"])
            )
            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn(str(Path.home()), serialized)
            self.assertNotIn("PRIVATE_SENTINEL", serialized)
            self.assertEqual(
                json.loads((output / "build-meta.json").read_text(encoding="utf-8"))[
                    "document_count"
                ],
                len(DEMO_FIXTURES),
            )


if __name__ == "__main__":
    unittest.main()
