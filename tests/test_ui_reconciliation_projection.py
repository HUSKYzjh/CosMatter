import unittest

from cosmatter.ui_export import _relation_reconciliation_projection


class UiReconciliationProjectionTests(unittest.TestCase):
    def test_projects_only_explicit_reviewed_mapping_fields(self) -> None:
        projected = _relation_reconciliation_projection({
            "trust_status": "human_reviewed_cross_source_identity_not_scientific_evidence",
            "source": {"evidence_id": "e1", "document_id": "d1"},
            "mappings": [{"openalex_work_id": "https://openalex.org/W2", "crossref_doi": "10.1000/x", "status": "matched", "basis": "reviewed DOI"}],
            "revision_history": [{"revision": 1, "recorded_at": "2026-08-31T09:30:00Z", "mapping_count": 1, "status_counts": {"matched": 1, "conflict": 0, "unresolved": 0}, "mappings_sha256": "a" * 64}],
        })
        self.assertEqual(projected["mappings"][0]["status"], "matched")
        self.assertEqual(projected["revision_history"][0], {"revision": 1, "recorded_at": "2026-08-31T09:30:00Z", "mapping_count": 1, "status_counts": {"matched": 1, "conflict": 0, "unresolved": 0}})
