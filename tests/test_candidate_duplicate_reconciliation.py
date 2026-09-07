import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.candidate_duplicate_reconciliation import (
    CandidateDuplicateReconciliationError,
    REVIEW_TRUST_STATUS,
    build_candidate_duplicate_queue,
    candidate_duplicate_reconciliation_from_review,
    candidate_duplicate_review_template,
    load_candidate_duplicate_queue,
    load_candidate_duplicate_reconciliation,
    write_candidate_duplicate_queue,
    write_candidate_duplicate_reconciliation,
    write_candidate_duplicate_review_template,
)
from cosmatter.metadata_enrichment import build_metadata_enrichment
from cosmatter.models import PaperCandidate


def candidate(document_id: str, title: str, *, accessible: bool = False, doi: str | None = None) -> dict[str, object]:
    return PaperCandidate(
        document_id=document_id,
        title=title,
        query="bounded query",
        source="Sciverse",
        publication_year=2024,
        is_content_accessible=accessible,
        doi=doi,
    ).to_dict()


def provider(document_id: str, title: str, doi: str) -> PaperCandidate:
    return PaperCandidate(
        document_id=document_id,
        title=title,
        query=title,
        source="Crossref",
        publication_year=2024,
        doi=doi,
    )


class CandidateDuplicateReconciliationTests(unittest.TestCase):
    def test_exact_title_only_creates_review_queue_without_aliasing(self) -> None:
        payload = {"candidates": [
            candidate("doc_1", "A shared title."),
            candidate("doc_2", "  A   SHARED title "),
            candidate("doc_3", "A different title"),
        ]}
        queue = build_candidate_duplicate_queue("mission_1", payload)

        self.assertEqual(queue["group_count"], 1)
        self.assertEqual(queue["groups"][0]["doi_state"], "title_only_review_required")
        self.assertIsNone(queue["groups"][0]["canonical_document_id"])
        self.assertEqual(queue["groups"][0]["alias_document_ids"], [])
        rendered = json.dumps(queue)
        self.assertNotIn("A shared title", rendered)
        self.assertNotIn("bounded query", rendered)

    def test_only_complete_same_doi_allows_an_automatic_alias(self) -> None:
        payload = {"candidates": [
            candidate("doc_1", "A shared title"),
            candidate("doc_2", "A shared title.", accessible=True),
        ]}
        enrichment = build_metadata_enrichment(
            "mission_1", payload, ("doc_1", "doc_2"),
            {
                "doc_1": {"Crossref": (provider("crossref_1", "A shared title", "10.1000/shared"),)},
                "doc_2": {"Crossref": (provider("crossref_2", "A shared title", "10.1000/shared"),)},
            },
        )
        queue = build_candidate_duplicate_queue("mission_1", payload, enrichment)

        group = queue["groups"][0]
        self.assertEqual(group["doi_state"], "same_doi_merge_allowed")
        self.assertEqual(group["canonical_document_id"], "doc_2")
        self.assertEqual(group["alias_document_ids"], ["doc_1"])
        review = candidate_duplicate_review_template(queue)
        self.assertEqual(review["decisions"], [])
        review["trust_status"] = REVIEW_TRUST_STATUS
        reconciliation = candidate_duplicate_reconciliation_from_review(queue, review)
        self.assertEqual(reconciliation["summary"], {
            "same_work_count": 1, "distinct_works_count": 0, "unresolved_count": 0,
            "automatic_doi_count": 1, "human_decision_count": 0,
        })

    def test_partial_or_conflicting_dois_stay_review_required(self) -> None:
        partial = {"candidates": [
            candidate("doc_1", "Same title", doi="10.1000/one"),
            candidate("doc_2", "Same title"),
        ]}
        conflict = {"candidates": [
            candidate("doc_1", "Same title", doi="10.1000/one"),
            candidate("doc_2", "Same title", doi="10.1000/two"),
        ]}
        self.assertEqual(build_candidate_duplicate_queue("mission_1", partial)["groups"][0]["doi_state"], "partial_doi_review_required")
        self.assertEqual(build_candidate_duplicate_queue("mission_1", conflict)["groups"][0]["doi_state"], "conflicting_doi_review_required")

    def test_human_review_may_confirm_or_keep_groups_separate(self) -> None:
        payload = {"candidates": [candidate("doc_1", "Same title"), candidate("doc_2", "Same title")]}
        queue = build_candidate_duplicate_queue("mission_1", payload)
        review = candidate_duplicate_review_template(queue)
        review["trust_status"] = REVIEW_TRUST_STATUS
        review["decisions"][0] = {
            "group_id": queue["groups"][0]["group_id"],
            "decision": "same_work",
            "canonical_document_id": "doc_1",
            "reason_code": "human_bibliographic_confirmation",
        }
        reconciliation = candidate_duplicate_reconciliation_from_review(queue, review)
        self.assertEqual(reconciliation["resolutions"][0]["alias_document_ids"], ["doc_2"])
        self.assertEqual(reconciliation["summary"]["human_decision_count"], 1)

        review["decisions"][0] = {
            "group_id": queue["groups"][0]["group_id"],
            "decision": "distinct_works",
            "canonical_document_id": None,
            "reason_code": "distinct_study_same_title",
        }
        separate = candidate_duplicate_reconciliation_from_review(queue, review)
        self.assertEqual(separate["resolutions"][0]["alias_document_ids"], [])

    def test_review_rejects_missing_group_or_foreign_canonical_document(self) -> None:
        payload = {"candidates": [candidate("doc_1", "Same title"), candidate("doc_2", "Same title")]}
        queue = build_candidate_duplicate_queue("mission_1", payload)
        review = candidate_duplicate_review_template(queue)
        review["trust_status"] = REVIEW_TRUST_STATUS
        review["decisions"] = []
        with self.assertRaisesRegex(CandidateDuplicateReconciliationError, "every pending group"):
            candidate_duplicate_reconciliation_from_review(queue, review)
        review = candidate_duplicate_review_template(queue)
        review["trust_status"] = REVIEW_TRUST_STATUS
        review["decisions"][0].update(decision="same_work", canonical_document_id="foreign_doc", reason_code="human_bibliographic_confirmation")
        with self.assertRaisesRegex(CandidateDuplicateReconciliationError, "outside its group"):
            candidate_duplicate_reconciliation_from_review(queue, review)

    def test_queue_and_reconciliation_are_bound_and_revisioned(self) -> None:
        payload = {"candidates": [candidate("doc_1", "Same title"), candidate("doc_2", "Same title")]}
        queue = build_candidate_duplicate_queue("mission_1", payload)
        review = candidate_duplicate_review_template(queue)
        review["trust_status"] = REVIEW_TRUST_STATUS
        review["decisions"][0].update(decision="unresolved", reason_code="insufficient_metadata")
        reconciliation = candidate_duplicate_reconciliation_from_review(queue, review)
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            queue_path = write_candidate_duplicate_queue(run, queue)
            self.assertEqual(load_candidate_duplicate_queue(queue_path, "mission_1", payload), queue)
            template_path = write_candidate_duplicate_review_template(run / "review.json", candidate_duplicate_review_template(queue))
            self.assertTrue(template_path.is_file())
            path = write_candidate_duplicate_reconciliation(run, reconciliation)
            write_candidate_duplicate_reconciliation(run, reconciliation)
            stored = load_candidate_duplicate_reconciliation(path, "mission_1")
            self.assertEqual(len(stored["revision_history"]), 2)
            self.assertEqual(load_candidate_duplicate_reconciliation(path, "mission_1", queue), stored)
            other_queue = build_candidate_duplicate_queue("mission_1", {
                "candidates": [candidate("doc_1", "Same title", doi="10.1000/shared"), candidate("doc_2", "Same title", doi="10.1000/shared")],
            })
            with self.assertRaisesRegex(CandidateDuplicateReconciliationError, "stale for the current queue"):
                load_candidate_duplicate_reconciliation(path, "mission_1", other_queue)
            changed = {"candidates": [candidate("doc_1", "Changed title"), candidate("doc_2", "Same title")]}
            with self.assertRaisesRegex(CandidateDuplicateReconciliationError, "stale"):
                load_candidate_duplicate_queue(queue_path, "mission_1", changed)


if __name__ == "__main__":
    unittest.main()
