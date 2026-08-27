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


if __name__ == "__main__":
    unittest.main()