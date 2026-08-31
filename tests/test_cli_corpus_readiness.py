import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest
from cosmatter.models import MissionBrief


class CliCorpusReadinessTests(unittest.TestCase):
    def test_writes_count_only_readiness_audit_for_human_frozen_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "bfo_90"
            run.mkdir(parents=True)
            mission = MissionBrief(
                "why", "BiFeO3", "phase stability", "epitaxial thin films", mission_id="mission_bfo_90"
            )
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            manifest = corpus_manifest_from_review(
                mission_id=mission.mission_id,
                material=mission.material,
                selection={
                    "corpus_id": "bfo_90",
                    "material": "BiFeO3",
                    "documents": [
                        {
                            "document_id": "doc_1",
                            "title": "Private institutional title",
                            "doi": "10.1000/example",
                            "access_policy": "institutional_access_internal_review_only",
                        },
                        {
                            "document_id": "doc_2",
                            "title": "Another private title",
                            "doi": None,
                            "access_policy": "institutional_access_internal_review_only",
                        },
                    ],
                },
            )
            write_corpus_manifest(run, manifest)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["audit-frozen-corpus-readiness", "--run-id", "bfo_90", "--expected-count", "2"])
            result = json.loads(output.getvalue())
            readiness_text = (run / "frozen_corpus_readiness.json").read_text(encoding="utf-8")
            events_text = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue())
        self.assertEqual(result["evaluation_gate"], "ready_for_private_human_annotation")
        self.assertNotIn("Private institutional title", readiness_text)
        self.assertNotIn("Private institutional title", events_text)

    def test_rejects_expected_count_outside_safe_evaluation_range(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["audit-frozen-corpus-readiness", "--run-id", "not-used", "--expected-count", "0"])
        self.assertEqual(status, 2)
        self.assertIn("expected document count", json.loads(output.getvalue())["error"])

    def test_prepares_all_blank_real_evaluation_artifacts_from_one_frozen_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "evaluation_pack"
            run.mkdir(parents=True)
            mission = MissionBrief("why", "BiFeO3", "phase stability", "epitaxial thin films", mission_id="mission_pack")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            manifest = corpus_manifest_from_review(
                mission_id=mission.mission_id,
                material=mission.material,
                selection={
                    "corpus_id": "bfo_pack",
                    "material": "BiFeO3",
                    "documents": [{
                        "document_id": "doc_1", "title": "Private institutional title", "doi": "10.1000/example",
                        "access_policy": "institutional_access_internal_review_only",
                    }],
                },
            )
            write_corpus_manifest(run, manifest)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["prepare-real-evaluation", "--run-id", "evaluation_pack", "--expected-count", "1", "--seed-candidates"])
            result = json.loads(output.getvalue())
            events = (run / "events.jsonl").read_text(encoding="utf-8")
            readiness = json.loads((run / "frozen_corpus_readiness.json").read_text(encoding="utf-8"))
            gold = json.loads((run / "human_gold_standard_template.json").read_text(encoding="utf-8"))
            registry = json.loads((run / "bibliographic_source_registry_template.json").read_text(encoding="utf-8"))
            run_record = json.loads((run / "real_corpus_evaluation_run_record_template.json").read_text(encoding="utf-8"))
            candidates = json.loads((run / "retrieval_candidates.json").read_text(encoding="utf-8"))
        self.assertEqual(status, 0, output.getvalue())
        self.assertEqual(result["evaluation_gate"], "ready_for_private_human_annotation")
        self.assertTrue(result["candidate_seeding_requested"])
        self.assertEqual(readiness["frozen_document_count"], 1)
        self.assertEqual(gold["trust_status"], "blank_human_annotation_template_not_evaluation_result")
        self.assertEqual(registry["trust_status"], "blank_human_bibliographic_source_template_not_evaluation_result")
        self.assertEqual(run_record["trust_status"], "blank_human_real_corpus_evaluation_run_record_not_a_result")
        self.assertEqual(candidates["candidates"][0]["score"], None)
        self.assertIn("real_corpus_evaluation_preparation_created", events)
        self.assertNotIn("Private institutional title", output.getvalue())
        self.assertNotIn("Private institutional title", events)


if __name__ == "__main__":
    unittest.main()
