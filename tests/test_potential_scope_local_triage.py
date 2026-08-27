from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.potential_scope_local_triage import (
    LOCAL_TRIAGE_TRUST_STATUS,
    build_local_batch_review_template,
    build_local_keyword_triage,
    write_once,
)


class PotentialScopeLocalTriageTests(unittest.TestCase):
    def test_local_draft_is_quote_free_and_untrusted(self) -> None:
        private_quote = "The DFT reference calculation shows a strain-dependent phase boundary."
        pool = {
            "mission_id": "ps_mission",
            "document_id": "ps_doc_01",
            "task_id_sha256": "a" * 64,
            "source_markdown_sha256": "b" * 64,
            "candidate_segments": [{"segment_id": "segment_001", "quote": private_quote}],
        }
        draft = build_local_keyword_triage(pool)
        self.assertEqual(draft["trust_status"], LOCAL_TRIAGE_TRUST_STATUS)
        self.assertNotIn(private_quote, json.dumps(draft))
        self.assertLessEqual(draft["proposals"][0]["confidence"], 0.45)

    def test_batch_sheet_is_blank_and_write_once(self) -> None:
        pool = {
            "mission_id": "ps_mission",
            "document_id": "ps_doc_01",
            "task_id_sha256": "a" * 64,
            "source_markdown_sha256": "b" * 64,
            "candidate_segments": [{"segment_id": "segment_001", "quote": "DFT potential phase structure."}],
        }
        draft = build_local_keyword_triage(pool)
        sheet = build_local_batch_review_template(mission_id="ps_mission", drafts=[draft])
        self.assertEqual(sheet["documents"][0]["decision"], "")
        with tempfile.TemporaryDirectory() as temporary:
            output = write_once(Path(temporary) / "draft.json", draft)
            self.assertTrue(output.exists())
            self.assertNotIn("DFT potential phase structure", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
