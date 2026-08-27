import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest
from cosmatter.human_evaluation import (
    HumanEvaluationError,
    load_reviewed_retrieval_gold,
    retrieval_evaluation_from_gold,
)
from cosmatter.models import MissionBrief


def selection() -> dict[str, object]:
    return {
        "corpus_id": "bfo_test",
        "material": "BiFeO3",
        "documents": [
            {"document_id": "doc_1", "title": "One", "doi": None, "access_policy": "institutional_access_internal_review_only"},
            {"document_id": "doc_2", "title": "Two", "doi": None, "access_policy": "institutional_access_internal_review_only"},
            {"document_id": "doc_3", "title": "Three", "doi": None, "access_policy": "institutional_access_internal_review_only"},
        ],
    }


def gold_payload() -> dict[str, object]:
    rows = [
        ("doc_1", "relevant"),
        ("doc_2", "partially_relevant"),
        ("doc_3", "not_relevant"),
    ]
    return {
        "schema_version": "1.0",
        "mission_id": "mission_1",
        "corpus_id": "bfo_test",
        "trust_status": "human_reviewed_gold_standard_for_evaluation",
        "documents": [
            {
                "document_id": document_id,
                "retrieval_relevance": relevance,
                "evidence_annotations": [],
                "material_fact_annotations": [],
                "comparison_annotations": [],
                "gap_annotations": [],
            }
            for document_id, relevance in rows
        ],
    }


def candidate_artifact() -> dict[str, object]:
    cards = [
        {"document_id": "doc_2", "title": "Two"},
        {"document_id": "doc_1", "title": "One"},
        {"document_id": "doc_3", "title": "Three"},
    ]
    return {"searches": [{"query": "BiFeO3", "candidate_count": 3, "candidates": cards}]}


class HumanEvaluationTests(unittest.TestCase):
    def test_calculates_strict_precision_recall_and_graded_ndcg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            gold_path = Path(directory) / "gold.json"
            gold_path.write_text(json.dumps(gold_payload()), encoding="utf-8")
            labels = load_reviewed_retrieval_gold(
                gold_path,
                mission_id="mission_1",
                corpus_id="bfo_test",
                corpus_document_ids={"doc_1", "doc_2", "doc_3"},
            )
        result = retrieval_evaluation_from_gold(
            mission_id="mission_1",
            corpus_id="bfo_test",
            gold=labels,
            candidate_artifact=candidate_artifact(),
            search_index=0,
            k=2,
        )
        self.assertEqual(result["precision_at_k"], 0.5)
        self.assertEqual(result["recall_at_k"], 1.0)
        self.assertGreater(result["ndcg_at_k"], 0)
        self.assertEqual(result["trust_status"], "metrics_from_human_reviewed_gold_standard")

    def test_exact_normalized_doi_maps_provider_record_to_frozen_document(self) -> None:
        candidate_history = {
            "searches": [{"query": "BiFeO3", "candidate_count": 3, "candidates": [
                {"document_id": "sciverse:opaque_1", "title": "One", "doi": "https://doi.org/10.1000/ONE"},
                {"document_id": "openalex:alias_1", "title": "One alias", "doi": "10.1000/one"},
                {"document_id": "doc_2", "title": "Two"},
            ]}],
        }
        labels = {"doc_1": "relevant", "doc_2": "partially_relevant", "doc_3": "not_relevant"}
        result = retrieval_evaluation_from_gold(
            mission_id="mission_1", corpus_id="bfo_test", gold=labels,
            candidate_artifact=candidate_history, search_index=0, k=2,
            corpus_document_dois={"doc_1": "10.1000/one", "doc_2": None, "doc_3": None},
        )
        self.assertEqual(result["schema_version"], "1.1")
        self.assertEqual(result["raw_retrieved_count"], 3)
        self.assertEqual(result["retrieved_count"], 2)
        self.assertEqual(result["doi_resolved_candidate_count"], 2)
        self.assertEqual(result["duplicate_alias_count"], 1)
        self.assertEqual(result["recall_at_k"], 1.0)

    def test_non_exact_provider_candidate_is_rejected_from_frozen_evaluation(self) -> None:
        with self.assertRaises(HumanEvaluationError):
            retrieval_evaluation_from_gold(
                mission_id="mission_1", corpus_id="bfo_test",
                gold={"doc_1": "relevant"},
                candidate_artifact={"searches": [{"candidates": [{"document_id": "unmapped", "title": "Unknown"}]}]},
                search_index=0, k=1, corpus_document_dois={"doc_1": "10.1000/one"},
            )

    def test_blank_template_is_rejected(self) -> None:
        bad = gold_payload() | {"trust_status": "blank_human_annotation_template_not_evaluation_result"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gold.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(HumanEvaluationError):
                load_reviewed_retrieval_gold(path, mission_id="mission_1", corpus_id="bfo_test", corpus_document_ids={"doc_1", "doc_2", "doc_3"})

    def test_cli_writes_real_gold_metrics_without_gold_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "human_eval"
            run.mkdir(parents=True)
            mission = MissionBrief("q", "BiFeO3", "phase", "scope", mission_id="mission_1")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            manifest = corpus_manifest_from_review(mission_id="mission_1", material="BiFeO3", selection=selection())
            write_corpus_manifest(run, manifest)
            (run / "retrieval_candidates.json").write_text(json.dumps(candidate_artifact()), encoding="utf-8")
            gold_path = root / "reviewed-gold.json"
            gold_path.write_text(json.dumps(gold_payload()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["evaluate-human-retrieval", "--run-id", "human_eval", "--input", str(gold_path), "--search-index", "0", "--k", "2"])
            artifact = (run / "human_retrieval_evaluation.json").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue())
        self.assertIn("precision_at_k", artifact)
        self.assertNotIn("\"retrieval_relevance\"", artifact)


if __name__ == "__main__":
    unittest.main()
