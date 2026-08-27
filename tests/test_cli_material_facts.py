import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.dispatch import MissionDispatcher
from cosmatter.models import MissionBrief
from cosmatter.material_extraction import material_facts_from_review, write_material_facts
from cosmatter.source_map import source_map_from_review, write_source_map


class CliMaterialFactsTests(unittest.TestCase):
    def test_reviewed_facts_are_recorded_and_safely_projected_to_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "material_facts_cli"
            run_dir.mkdir()
            mission = MissionBrief("what is reported", "BiFeO3", "phase stability", "films", mission_id="mission_material_cli")
            assignment = MissionDispatcher.from_project().assign(mission)
            source_map = source_map_from_review(
                mission_id=mission.mission_id, document_id="doc_1",
                source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"},
                selection={"document_id": "doc_1", "segments": [{"segment_id": "seg_1", "locator": "page:2", "kind": "paragraph", "quote": "BiFeO3 was measured at 300 K."}]},
            )
            reviewed = {"document_id": "doc_1", "facts": [{"fact_id": "fact_1", "segment_id": "seg_1", "category": "experimental_condition", "name": "temperature", "value": 300, "unit": "K", "normalized_value": 300, "normalized_unit": "K", "qualifiers": {"sample_form": "film"}}]}
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "fleet_assignment.json").write_text(json.dumps(assignment.to_dict()), encoding="utf-8")
            write_source_map(run_dir, source_map)
            input_path = run_dir / "reviewed_facts.json"
            input_path.write_text(json.dumps(reviewed), encoding="utf-8")
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["record-material-facts", "--run-id", "material_facts_cli", "--input", str(input_path)]), 0)
                self.assertEqual(main(["export-ui", "--run-id", "material_facts_cli"]), 0)
            artifact = json.loads((run_dir / "material_facts.json").read_text(encoding="utf-8"))
            bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))
            events = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(artifact["facts"][0]["locator"], "page:2")
        self.assertEqual(bundle["material_facts"]["facts"][0]["normalized_unit"], "K")
        self.assertNotIn("source_quote_sha256", json.dumps(bundle["material_facts"]))
        self.assertIn("material_facts_reviewed", events)

    def test_fusion_and_ui_export_reject_orphaned_reviewed_material_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "orphaned_facts"
            run_dir.mkdir()
            mission = MissionBrief("what is reported", "BiFeO3", "phase stability", "films", mission_id="mission_orphaned_facts")
            assignment = MissionDispatcher.from_project().assign(mission)
            source_map = source_map_from_review(
                mission_id=mission.mission_id, document_id="doc_1",
                source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"},
                selection={"document_id": "doc_1", "segments": [{"segment_id": "seg_1", "locator": "page:2", "kind": "paragraph", "quote": "BiFeO3 was measured at 300 K."}]},
            )
            reviewed = {"document_id": "doc_1", "facts": [{"fact_id": "fact_1", "segment_id": "seg_1", "category": "experimental_condition", "name": "temperature", "value": 300, "unit": "K", "normalized_value": 300, "normalized_unit": "K", "qualifiers": {"sample_form": "film"}}]}
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "fleet_assignment.json").write_text(json.dumps(assignment.to_dict()), encoding="utf-8")
            write_source_map(run_dir, source_map)
            write_material_facts(run_dir, material_facts_from_review(mission_id=mission.mission_id, source_map=source_map, selection=reviewed))
            (run_dir / "source_map.json").unlink()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["fuse-material-facts", "--run-id", "orphaned_facts"]), 2)
                self.assertEqual(main(["export-ui", "--run-id", "orphaned_facts"]), 2)



if __name__ == "__main__":
    unittest.main()
