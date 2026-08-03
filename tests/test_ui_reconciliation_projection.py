import unittest

from cosmatter.ui_export import _relation_reconciliation_projection


class UiReconciliationProjectionTests(unittest.TestCase):
    def test_projects_only_explicit_reviewed_mapping_fields(self) -> None:
        projected = _relation_reconciliation_projection({
            "trust_status": "human_reviewed_cross_source_identity_not_scientific_evidence",
            "source": {"evidence_id": "e1", "document_id": "d1"},
            "mappings": [{"openalex_work_id": "https://openalex.org/W2", "crossref_doi": "10.1000/x", "status": "matched", "basis": "reviewed DOI"}],
        })
        self.assertEqual(projected["mappings"][0]["status"], "matched")
