import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.corpus_preparation import corpus_manifest_from_review, gold_standard_template_from_manifest, write_corpus_manifest
from cosmatter.models import MissionBrief


class AnnotationCoverageCliTests(unittest.TestCase):
    def test_audits_private_annotation_file_without_copying_titles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            run = runs / "coverage_cli"
            run.mkdir(parents=True)
            mission = MissionBrief("q", "BiFeO3", "phase", "scope", mission_id="mission_90")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            manifest = corpus_manifest_from_review(
                mission_id="mission_90", material="BiFeO3", selection={
                    "corpus_id": "bfo_90", "material": "BiFeO3", "documents": [
                        {"document_id": "doc_1", "title": "Private title", "doi": None, "access_policy": "institutional_access_internal_review_only"},
                    ],
                },
            )
            write_corpus_manifest(run, manifest)
            gold = gold_standard_template_from_manifest(manifest)
            source = root / "private_review.json"
            source.write_text(json.dumps(gold), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output):
                status = main(["audit-human-annotation-coverage", "--run-id", "coverage_cli", "--input", str(source)])
            saved = (run / "human_annotation_coverage.json").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue())
        self.assertIn("blocked_until_every_frozen_document", saved)
        self.assertNotIn("Private title", saved)


if __name__ == "__main__":
    unittest.main()
