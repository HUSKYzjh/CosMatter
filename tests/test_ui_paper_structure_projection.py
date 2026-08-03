import unittest

from cosmatter.ui_export import _paper_structure_projection


class UiPaperStructureProjectionTests(unittest.TestCase):
    def test_projects_only_paper_scoped_structure_fields(self) -> None:
        structure = {
            "document_id": "doc_1", "trust_status": "human_reviewed_paper_structure_not_scientific_evidence",
            "entities": [{"entity_id": "e1", "label": "BiFeO3", "kind": "material", "segment_id": "p1"}],
            "relations": [],
        }
        projected = _paper_structure_projection(structure)
        self.assertEqual(projected["entities"][0]["entity_id"], "e1")
        self.assertNotIn("quote", str(projected))
