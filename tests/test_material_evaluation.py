import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest
from cosmatter.material_evaluation import (
    MaterialFactEvaluationError,
    load_reviewed_material_fact_gold,
    material_fact_evaluation_from_gold,
)
from cosmatter.material_extraction import material_facts_from_review, write_material_facts_for_document
from cosmatter.models import MissionBrief


def selection() -> dict[str, object]:
    return {
        "corpus_id": "bfo_test",
        "material": "BiFeO3",
        "documents": [
            {"document_id": "doc_1", "title": "One", "doi": None, "access_policy": "institutional_access_internal_review_only"},
            {"document_id": "doc_2", "title": "Two", "doi": None, "access_policy": "institutional_access_internal_review_only"},
        ],
    }


def gold_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "mission_id": "mission_1",
        "corpus_id": "bfo_test",
        "trust_status": "human_reviewed_material_fact_gold_for_evaluation",
        "documents": [
            {"document_id": "doc_1", "expected_facts": [{"category": "property", "name": "polarization", "normalized_value": 90, "normalized_unit": "uC/cm2", "locator": "page:1"}]},
            {"document_id": "doc_2", "expected_facts": [{"category": "experimental_condition", "name": "temperature", "normalized_value": 300, "normalized_unit": "K", "locator": "page:2"}]},
        ],
    }


def reviewed_artifacts() -> tuple[dict[str, object], ...]:
    return (
        {"mission_id": "mission_1", "document_id": "doc_1", "facts": [
            {"category": "property", "name": "polarization", "normalized_value": 90, "normalized_unit": "mC/cm2", "locator": "page:1"},
            {"category": "structure", "name": "phase", "normalized_value": "R", "normalized_unit": None, "locator": "page:1"},
        ]},
        {"mission_id": "mission_1", "document_id": "doc_2", "facts": [
            {"category": "experimental_condition", "name": "temperature", "normalized_value": 300, "normalized_unit": "K", "locator": "page:2"},
        ]},
    )


class MaterialFactEvaluationTests(unittest.TestCase):
    def test_scores_exact_facts_and_unit_match_independently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gold.json"
            path.write_text(json.dumps(gold_payload()), encoding="utf-8")
            gold = load_reviewed_material_fact_gold(path, mission_id="mission_1", corpus_id="bfo_test", corpus_document_ids={"doc_1", "doc_2"})
        result = material_fact_evaluation_from_gold(mission_id="mission_1", corpus_id="bfo_test", gold=gold, reviewed_artifacts=reviewed_artifacts())
        self.assertEqual(result["gold_fact_count"], 2)
        self.assertEqual(result["exact_match_count"], 1)
        self.assertEqual(result["precision"], 0.333333)
        self.assertEqual(result["recall"], 0.5)
        self.assertEqual(result["unit_match_accuracy"], 0.5)

    def test_rejects_nonreviewed_or_incomplete_gold(self) -> None:
        bad = gold_payload() | {"trust_status": "blank_human_annotation_template_not_evaluation_result"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gold.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(MaterialFactEvaluationError):
                load_reviewed_material_fact_gold(path, mission_id="mission_1", corpus_id="bfo_test", corpus_document_ids={"doc_1", "doc_2"})

    def test_cli_emits_aggregate_material_fact_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "material_eval"
            run.mkdir(parents=True)
            mission = MissionBrief("q", "BiFeO3", "phase", "scope", mission_id="mission_1")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            manifest = corpus_manifest_from_review(mission_id="mission_1", material="BiFeO3", selection=selection())
            write_corpus_manifest(run, manifest)
            quote = "Measured at 300 K."
            source_map = {
                "schema_version": "1.0", "mission_id": "mission_1", "trust_status": "human_reviewed_parser_selection",
                "document_id": "doc_1", "provider": "mineru", "task_id_sha256": "a" * 64,
                "segments": [{"segment_id": "s1", "locator": "page:1", "kind": "paragraph", "quote": quote, "quote_sha256": hashlib.sha256(quote.encode()).hexdigest()}],
            }
            reviewed = material_facts_from_review(
                mission_id="mission_1",
                source_map=source_map,
                selection={"document_id": "doc_1", "facts": [{"fact_id": "f1", "segment_id": "s1", "category": "property", "name": "polarization", "value": 90, "unit": "uC/cm2", "normalized_value": 90, "normalized_unit": "uC/cm2", "qualifiers": {}}]},
            )
            write_material_facts_for_document(run, reviewed)
            gold_path = root / "gold.json"
            gold_path.write_text(json.dumps(gold_payload()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["evaluate-human-material-facts", "--run-id", "material_eval", "--input", str(gold_path)])
            artifact = (run / "human_material_fact_evaluation.json").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue())
        self.assertIn("unit_match_accuracy", artifact)
        self.assertNotIn("polarization", artifact)


if __name__ == "__main__":
    unittest.main()
