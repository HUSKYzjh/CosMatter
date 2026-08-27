import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.annotation_coverage import AnnotationCoverageError, annotation_coverage_audit
from cosmatter.corpus_preparation import corpus_manifest_from_review, gold_standard_template_from_manifest, write_corpus_manifest


def manifest() -> dict:
    return corpus_manifest_from_review(
        mission_id="mission_90", material="BiFeO3", selection={
            "corpus_id": "bfo_90", "material": "BiFeO3", "documents": [
                {"document_id": "doc_1", "title": "Private one", "doi": None, "access_policy": "institutional_access_internal_review_only"},
                {"document_id": "doc_2", "title": "Private two", "doi": None, "access_policy": "institutional_access_internal_review_only"},
            ],
        },
    )


class AnnotationCoverageTests(unittest.TestCase):
    def test_blank_template_reports_unreviewed_without_document_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            frozen = manifest()
            write_corpus_manifest(run, frozen)
            annotation = gold_standard_template_from_manifest(frozen)
            path = run / "gold.json"
            path.write_text(json.dumps(annotation), encoding="utf-8")
            audit = annotation_coverage_audit(run_dir=run, mission_id="mission_90", annotation_path=path)
        self.assertEqual(audit["relevance_counts"]["unreviewed"], 2)
        self.assertEqual(audit["relevance_evaluation_gate"], "blocked_until_every_frozen_document_has_reviewed_relevance")
        self.assertNotIn("Private one", json.dumps(audit))

    def test_reviewed_relevance_opens_only_retrieval_evaluation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            frozen = manifest()
            write_corpus_manifest(run, frozen)
            annotation = gold_standard_template_from_manifest(frozen)
            annotation["trust_status"] = "human_reviewed_gold_standard_for_evaluation"
            annotation["documents"][0]["retrieval_relevance"] = "relevant"
            annotation["documents"][1]["retrieval_relevance"] = "not_relevant"
            path = run / "reviewed.json"
            path.write_text(json.dumps(annotation), encoding="utf-8")
            audit = annotation_coverage_audit(run_dir=run, mission_id="mission_90", annotation_path=path)
        self.assertEqual(audit["relevance_evaluation_gate"], "ready_for_human_retrieval_evaluation")

    def test_rejects_mismatched_annotation_document_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            frozen = manifest()
            write_corpus_manifest(run, frozen)
            annotation = gold_standard_template_from_manifest(frozen)
            annotation["documents"].pop()
            path = run / "bad.json"
            path.write_text(json.dumps(annotation), encoding="utf-8")
            with self.assertRaises(AnnotationCoverageError):
                annotation_coverage_audit(run_dir=run, mission_id="mission_90", annotation_path=path)


if __name__ == "__main__":
    unittest.main()
