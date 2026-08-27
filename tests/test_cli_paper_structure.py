import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.models import MissionBrief
from cosmatter.paper_structure import paper_structure_document_path
from cosmatter.source_map import write_source_map_for_document


class CliPaperStructureTests(unittest.TestCase):
    def test_records_only_structure_tied_to_reviewed_source_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs = Path(directory); run = runs / "structure_cli"; run.mkdir()
            mission = MissionBrief(question="q", material="BiFeO3", property_name="phase", scope="scope", mission_id="mission_1")
            (run / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            import hashlib
            source = {"schema_version":"1.0","mission_id":"mission_1","trust_status":"human_reviewed_parser_selection","document_id":"doc_1","provider":"mineru","task_id_sha256":"a"*64,"segments":[{"segment_id":"p1","locator":"p.1","kind":"paragraph","quote":"quoted","quote_sha256":hashlib.sha256(b"quoted").hexdigest()}]}
            write_source_map_for_document(run, source)
            selection = {"document_id":"doc_1","entities":[{"entity_id":"e1","label":"BiFeO3","kind":"material","segment_id":"p1"}],"relations":[]}; selection_path = run / "selection.json"; selection_path.write_text(json.dumps(selection), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs), contextlib.redirect_stdout(output): status = main(["record-paper-structure","--run-id","structure_cli","--input",str(selection_path)])
            artifact = paper_structure_document_path(run, "doc_1").read_text(encoding="utf-8")
        self.assertEqual(status, 0, output.getvalue()); self.assertIn("e1", artifact); self.assertNotIn("quoted", artifact)
