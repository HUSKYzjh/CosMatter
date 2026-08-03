import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.ui_export import _relation_expansion_projection


class UiRelationProjectionTests(unittest.TestCase):
    def test_projects_only_allowed_external_relation_fields(self) -> None:
        payload = {
            "schema_version": "1.0",
            "mission_id": "mission_1",
            "trust_status": "public_relation_metadata_not_scientific_evidence",
            "source": {"evidence_id": "evidence_1", "document_id": "doc_1", "openalex_work_id": "https://openalex.org/W1"},
            "edges": [{"edge_type": "citation_reference", "target_openalex_id": "https://openalex.org/W2"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "relation_expansion.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            projected = _relation_expansion_projection(path, "mission_1")
        self.assertEqual(projected["edges"][0]["edge_type"], "citation_reference")
        self.assertNotIn("doi", json.dumps(projected))

    def test_rejects_wrong_mission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "relation_expansion.json"
            path.write_text(json.dumps({}), encoding="utf-8")
            with self.assertRaises(ValueError):
                _relation_expansion_projection(path, "mission_1")
