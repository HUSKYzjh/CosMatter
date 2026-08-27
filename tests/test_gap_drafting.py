import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.deepseek import DraftCompletion
from cosmatter.facilities import DiscrepancyRow
from cosmatter.gap_drafting import GapDraftingError, research_gap_drafting_prompts, write_untrusted_research_gap_draft
from cosmatter.models import MissionBrief


class GapDraftingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief("why", "BiFeO3", "phase stability", "thin films", mission_id="mission_gap_draft")
        self.rows = (
            DiscrepancyRow("sample_form=film", ("evidence_support",), ("evidence_contradict",), ("strain_percent",), ()),
        )

    def test_prompt_is_structural_and_explicitly_untrusted(self) -> None:
        system, user = research_gap_drafting_prompts(self.mission, self.rows)
        payload = json.loads(user)

        self.assertIn("untrusted JSON brainstorming draft", system)
        self.assertIn("cannot be a Research Gap candidate", user)
        self.assertEqual(payload["structural_discrepancy_rows"][0]["evidence_ids"], ["evidence_support", "evidence_contradict"])
        self.assertNotIn("quote", user.lower())
        self.assertNotIn("citation", user.lower())

    def test_writer_keeps_only_counts_of_structural_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_untrusted_research_gap_draft(
                Path(directory),
                self.mission,
                DraftCompletion("untrusted private brainstorming", "fixture-model", "request_fixture"),
                self.rows,
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["trust_status"], "untrusted_llm_research_gap_draft_not_a_candidate_or_finding")
        self.assertEqual(payload["input_summary"], {"condition_row_count": 1, "evidence_id_count": 2})
        self.assertNotIn("condition_cluster", payload)
        self.assertNotIn("evidence_support", json.dumps(payload))

    def test_rejects_rows_without_distinguishing_conditions(self) -> None:
        invalid = (DiscrepancyRow("film", ("a",), ("b",), (), ()),)
        with self.assertRaises(GapDraftingError):
            research_gap_drafting_prompts(self.mission, invalid)


if __name__ == "__main__":
    unittest.main()
