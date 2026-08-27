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


class CliBibliographicSourceCoverageTests(unittest.TestCase):
    def test_cli_creates_and_audits_private_source_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, run = Path(directory), Path(directory) / "source_registry"
            run.mkdir()
            mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="films", mission_id="mission_1")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            manifest = corpus_manifest_from_review(mission_id="mission_1", material="BiFeO3", selection={
                "corpus_id": "bfo_90_v1", "material": "BiFeO3", "documents": [
                    {"document_id": "doc_1", "title": "Private title", "doi": None, "access_policy": "institutional_access_internal_review_only"},
                ],
            })
            write_corpus_manifest(run, manifest)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=root), contextlib.redirect_stdout(output):
                self.assertEqual(main(["create-bibliographic-source-template", "--run-id", "source_registry"]), 0, output.getvalue())
            registry = json.loads((run / "bibliographic_source_registry_template.json").read_text(encoding="utf-8"))
            registry["trust_status"] = "human_reviewed_bibliographic_source_registry"
            registry["documents"][0]["bibliographic_source"] = "OpenAlex"
            private_input = root / "reviewed_source_registry.json"
            private_input.write_text(json.dumps(registry), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=root), contextlib.redirect_stdout(output):
                self.assertEqual(main(["audit-bibliographic-source-coverage", "--run-id", "source_registry", "--input", str(private_input)]), 0, output.getvalue())
            audit = json.loads((run / "bibliographic_source_coverage.json").read_text(encoding="utf-8"))
            events = (run / "events.jsonl").read_text(encoding="utf-8")
        self.assertEqual(audit["bibliographic_source_coverage_gate"], "ready_for_source_traceable_evaluation")
        self.assertIn("bibliographic_source_registry_template_created", events)
        self.assertIn("bibliographic_source_coverage_audited", events)
        self.assertNotIn(str(private_input), output.getvalue())


if __name__ == "__main__":
    unittest.main()
