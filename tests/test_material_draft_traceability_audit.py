import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.material_draft_traceability_audit import audit_untrusted_material_draft, write_material_draft_traceability_audit


class MaterialDraftTraceabilityAuditTests(unittest.TestCase):
    def test_count_only_audit_never_promotes_candidates(self) -> None:
        quote = "The film thickness was 10 nm."
        source_map = {
            "mission_id": "mission_1", "document_id": "doc_1", "segments": [{
                "segment_id": "s1", "locator": "page:1", "quote": quote,
                "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            }],
        }
        candidates = {
            "schema_version": "1.0", "mission_id": "mission_1",
            "trust_status": "untrusted_llm_structured_material_fact_candidates_not_evidence", "document_id": "doc_1",
            "facts": [{
                "fact_id": "private_candidate", "segment_id": "s1", "category": "experimental_condition", "name": "film thickness",
                "value": "10 nm", "unit": "nm", "normalized_value": "10 nm", "normalized_unit": "nm", "qualifiers": {},
                "locator": "page:1", "source_quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
            }],
        }
        audit = audit_untrusted_material_draft(mission_id="mission_1", source_map=source_map, candidates=candidates)
        self.assertEqual(audit["candidate_fact_count"], 1)
        self.assertEqual(audit["source_linked_fact_count"], 1)
        self.assertEqual(audit["reported_value_verbatim_fact_count"], 1)
        self.assertEqual(audit["automatically_accepted_fact_count"], 0)
        self.assertEqual(audit["review_gate"], "requires_human_scientific_review")
        self.assertNotIn(quote, json.dumps(audit))
        self.assertNotIn("private_candidate", json.dumps(audit))
        with tempfile.TemporaryDirectory() as directory:
            path = write_material_draft_traceability_audit(Path(directory), audit)
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
