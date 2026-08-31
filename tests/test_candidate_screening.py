import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.candidate_screening import (
    CandidateScreeningError,
    candidate_screening_from_automated_trial,
    candidate_screening_from_review,
    candidate_screening_template,
    require_document_screened_for_fulltext,
    write_candidate_screening,
    write_automated_trial_candidate_screening,
)


def candidates() -> dict[str, object]:
    return {
        "candidates": [
            {"document_id": "doc_include", "title": "Relevant"},
            {"document_id": "doc_exclude", "title": "Outside scope"},
            {"document_id": "doc_review", "title": "Incomplete metadata"},
        ]
    }


def reviewed() -> dict[str, object]:
    return {
        "decisions": [
            {"document_id": "doc_include", "decision": "include_for_fulltext", "reason_codes": ["material_match", "scope_match"]},
            {"document_id": "doc_exclude", "decision": "exclude", "reason_codes": ["out_of_scope_property"]},
            {"document_id": "doc_review", "decision": "needs_metadata_review", "reason_codes": ["not_enough_metadata"]},
        ]
    }


class CandidateScreeningTests(unittest.TestCase):
    def test_template_has_one_unreviewed_slot_per_candidate(self) -> None:
        template = candidate_screening_template("mission_screen", candidates())

        self.assertEqual(template["trust_status"], "blank_human_candidate_screening_template_not_a_result")
        self.assertEqual([item["document_id"] for item in template["decisions"]], ["doc_include", "doc_exclude", "doc_review"])
        self.assertTrue(all(item["decision"] == "unreviewed" for item in template["decisions"]))
        self.assertEqual(len(template["candidate_fingerprint"]), 64)

    def test_review_requires_complete_scope_compatible_decisions(self) -> None:
        artifact = candidate_screening_from_review("mission_screen", candidates(), reviewed())

        self.assertEqual(artifact["candidate_count"], 3)
        self.assertEqual(artifact["trust_status"], "human_reviewed_candidate_screening_not_scientific_evidence")
        invalid = reviewed()
        invalid["decisions"] = invalid["decisions"][:-1]
        with self.assertRaises(CandidateScreeningError):
            candidate_screening_from_review("mission_screen", candidates(), invalid)

    def test_fulltext_gate_rejects_stale_or_nonincluded_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            artifact = candidate_screening_from_review("mission_screen", candidates(), reviewed())
            write_candidate_screening(run_dir, artifact)
            require_document_screened_for_fulltext(run_dir, "mission_screen", candidates(), "doc_include")
            with self.assertRaises(CandidateScreeningError):
                require_document_screened_for_fulltext(run_dir, "mission_screen", candidates(), "doc_exclude")
            stale = {"candidates": candidates()["candidates"][:2]}
            with self.assertRaises(CandidateScreeningError):
                require_document_screened_for_fulltext(run_dir, "mission_screen", stale, "doc_include")
            changed_metadata = candidates()
            changed_metadata["candidates"][0]["title"] = "Relevant revised metadata"
            with self.assertRaisesRegex(CandidateScreeningError, "stale"):
                require_document_screened_for_fulltext(run_dir, "mission_screen", changed_metadata, "doc_include")

    def test_screening_artifact_does_not_contain_titles_or_query_text(self) -> None:
        artifact = candidate_screening_from_review("mission_screen", candidates(), reviewed())
        serialized = json.dumps(artifact)
        self.assertNotIn("Relevant", serialized)
        self.assertNotIn("Outside scope", serialized)

    def test_delegated_automated_trial_is_separate_and_requires_explicit_gate_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            automated = candidate_screening_from_automated_trial("mission_screen", candidates(), reviewed())
            self.assertEqual(automated["trust_status"], "delegated_automated_trial_screening_not_scientific_evidence")
            write_automated_trial_candidate_screening(run_dir, automated)
            with self.assertRaises(CandidateScreeningError):
                require_document_screened_for_fulltext(run_dir, "mission_screen", candidates(), "doc_include")
            require_document_screened_for_fulltext(
                run_dir,
                "mission_screen",
                candidates(),
                "doc_include",
                allow_delegated_automated_trial=True,
            )


if __name__ == "__main__":
    unittest.main()
