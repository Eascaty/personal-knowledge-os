from __future__ import annotations

import json
import unittest
from pathlib import Path

from knowledge_os.contracts import (
    CANONICAL_SCHEMA,
    CONTRACT_DIR,
    ContractError,
    validate_canonical_contract,
)


class SharedContractTests(unittest.TestCase):
    def test_shared_example_satisfies_canonical_schema(self):
        example = json.loads(
            (CONTRACT_DIR / "examples" / "canonical-v1.json").read_text(
                encoding="utf-8"
            )
        )
        validate_canonical_contract(example)

    def test_contract_rejects_missing_document_identity(self):
        example = json.loads(
            (CONTRACT_DIR / "examples" / "canonical-v1.json").read_text(
                encoding="utf-8"
            )
        )
        del example["documents"][0]["id"]
        with self.assertRaisesRegex(ContractError, "缺少必填字段：id"):
            validate_canonical_contract(example)

    def test_contract_files_are_versioned_and_api_routes_are_declared(self):
        schema = json.loads(CANONICAL_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        openapi = (CONTRACT_DIR / "openapi.yaml").read_text(encoding="utf-8")
        for route in ("/health:", "/taxonomy:", "/documents:", "/documents/{id}:", "/search:"):
            self.assertIn(route, openapi)


if __name__ == "__main__":
    unittest.main()
