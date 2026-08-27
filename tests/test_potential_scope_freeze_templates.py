from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.potential_scope_freeze_templates import build_freeze_template_pack, write_freeze_template_pack


class PotentialScopeFreezeTemplateTests(unittest.TestCase):
    def test_pack_carries_only_source_ids_and_remains_unfrozen(self) -> None:
        registry = {
            "schema_version": "1.0",
            "mission_id": "mission_01",
            "trust_status": "human_reviewed_private_source_registry_not_evidence",
            "sources": [{"source_id": "ps_src_0123456789abcdef", "document_id": "private_document", "source_markdown_sha256": "a" * 64, "task_id_sha256": "b" * 64, "selection_sha256": "c" * 64, "selected_segment_count": 1}],
            "review_boundary": "Registry only.",
        }
        pack = build_freeze_template_pack(reviewed_source_registry=registry)
        self.assertEqual(pack["system_spec_template"]["literature_source_ids"], ["ps_src_0123456789abcdef"])
        self.assertEqual(pack["trust_status"], "template_requires_human_literature_model_review_not_frozen")
        serialized = json.dumps(pack, ensure_ascii=False)
        self.assertNotIn("private_document", serialized)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "freeze.template.json"
            write_freeze_template_pack(output, pack)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
