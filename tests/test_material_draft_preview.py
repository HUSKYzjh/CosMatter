import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.material_draft_preview import MaterialDraftPreviewError, preview_untrusted_material_draft
import hashlib


QUOTE = "A strained BiFeO3 film was measured at 300 K."
SOURCE_MAP = {
    "schema_version": "1.0", "mission_id": "mission_material", "trust_status": "human_reviewed_parser_selection",
    "document_id": "doc_material", "provider": "mineru", "task_id_sha256": "a" * 64,
    "segments": [{"segment_id": "seg_1", "locator": "page:3 paragraph:2", "kind": "paragraph", "quote": QUOTE, "quote_sha256": hashlib.sha256(QUOTE.encode("utf-8")).hexdigest()}],
}


def draft(document_id: str = "doc_material") -> str:
    return json.dumps({"document_id": document_id, "facts": [
        {"fact_id": "candidate_1", "segment_id": "seg_1", "category": "experimental_condition", "name": "temperature", "value": 300, "unit": "K", "normalized_value": 300, "normalized_unit": "K", "qualifiers": {"sample_form": "film"}}
    ]})


class MaterialDraftPreviewTests(unittest.TestCase):
    def test_preview_is_source_map_linked_but_remains_untrusted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path, count = preview_untrusted_material_draft(Path(directory), "mission_material", SOURCE_MAP, draft())
            artifact = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(count, 1)
        self.assertEqual(artifact["trust_status"], "untrusted_llm_structured_material_fact_candidates_not_evidence")
        self.assertEqual(artifact["facts"][0]["locator"], "page:3 paragraph:2")
        self.assertNotIn("A strained BiFeO3 film", json.dumps(artifact))
        self.assertNotIn("human_reviewed_structured_material_facts", artifact["trust_status"])

    def test_preview_rejects_unlinked_or_non_json_output(self) -> None:
        invalid = json.loads(draft())
        invalid["facts"][0]["segment_id"] = "unselected"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(MaterialDraftPreviewError):
                preview_untrusted_material_draft(root, "mission_material", SOURCE_MAP, json.dumps(invalid))
            with self.assertRaises(MaterialDraftPreviewError):
                preview_untrusted_material_draft(root, "mission_material", SOURCE_MAP, "not JSON")


if __name__ == "__main__":
    unittest.main()
