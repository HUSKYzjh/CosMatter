import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.deepseek import DraftCompletion
from cosmatter.models import MissionBrief
from cosmatter.source_map import source_map_from_review, write_source_map


class CliMaterialDraftPreviewTests(unittest.TestCase):
    def test_valid_model_json_creates_untrusted_structured_candidate_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory)
            run = runs / "material_preview_cli"
            run.mkdir()
            mission = MissionBrief("what is reported", "BiFeO3", "phase stability", "films", mission_id="mission_preview_cli")
            source_map = source_map_from_review(
                mission_id=mission.mission_id, document_id="doc_1",
                source_task={"document_id": "doc_1", "provider": "mineru", "state": "done", "task_id": "task_1"},
                selection={"document_id": "doc_1", "segments": [{"segment_id": "seg_1", "locator": "page:2", "kind": "paragraph", "quote": "BiFeO3 measured at 300 K."}]},
            )
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            write_source_map(run, source_map)
            content = json.dumps({"document_id": "doc_1", "facts": [{"fact_id": "fact_1", "segment_id": "seg_1", "category": "experimental_condition", "name": "temperature", "value": 300, "unit": "K", "normalized_value": 300, "normalized_unit": "K", "qualifiers": {}}]})
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs),
                patch("cosmatter.cli.DeepSeekAdapter") as adapter,
                contextlib.redirect_stdout(output),
            ):
                adapter.return_value.draft.return_value = DraftCompletion(content, "fixture-model", "request_fixture")
                status = main(["draft-material-extraction", "--run-id", "material_preview_cli"])
            result = json.loads(output.getvalue())
            previews = list((run / "material_extraction_candidates").glob("*.json"))
            event = (run / "events.jsonl").read_text(encoding="utf-8")
            reviewed_facts_exists = (run / "material_facts.json").exists()

        self.assertEqual(status, 0)
        self.assertEqual(result["structured_candidate_fact_count"], 1)
        self.assertEqual(len(previews), 1)
        self.assertFalse(reviewed_facts_exists)
        self.assertNotIn(content, output.getvalue())
        self.assertNotIn(content, event)


if __name__ == "__main__":
    unittest.main()
