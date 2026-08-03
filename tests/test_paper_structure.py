import unittest

from cosmatter.paper_structure import PaperStructureError, paper_structure_from_review


SOURCE_MAP = {"mission_id": "mission_1", "trust_status": "human_reviewed_parser_selection", "document_id": "doc_1", "segments": [{"segment_id": "p1"}, {"segment_id": "p2"}]}
SELECTION = {"document_id": "doc_1", "entities": [{"entity_id": "e1", "label": "BiFeO3", "kind": "material", "segment_id": "p1"}, {"entity_id": "e2", "label": "polarization", "kind": "property", "segment_id": "p2"}], "relations": [{"source_entity_id": "e1", "target_entity_id": "e2", "relation_type": "reports", "segment_id": "p2"}]}


class PaperStructureTests(unittest.TestCase):
    def test_scopes_entities_to_reviewed_document_segments(self) -> None:
        structure = paper_structure_from_review(mission_id="mission_1", source_map=SOURCE_MAP, selection=SELECTION)
        self.assertEqual(structure["document_id"], "doc_1")
        self.assertEqual(structure["relations"][0]["relation_type"], "reports")

    def test_rejects_relation_without_reviewed_segment(self) -> None:
        invalid = dict(SELECTION); invalid["relations"] = [{"source_entity_id": "e1", "target_entity_id": "e2", "relation_type": "reports", "segment_id": "p99"}]
        with self.assertRaises(PaperStructureError): paper_structure_from_review(mission_id="mission_1", source_map=SOURCE_MAP, selection=invalid)
