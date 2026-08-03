import unittest

from cosmatter.relation_reconciliation import RelationReconciliationError, reconciliation_from_review


OPENALEX = {"mission_id":"m1","trust_status":"public_relation_metadata_not_scientific_evidence","source":{"evidence_id":"e1","document_id":"d1"},"edges":[{"target_openalex_id":"https://openalex.org/W2"}]}
CROSSREF = {"mission_id":"m1","trust_status":"public_bibliographic_reference_metadata_not_scientific_evidence","source":{"evidence_id":"e1","document_id":"d1"},"edges":[{"target_doi":"10.1000/x"}]}
SELECTION = {"evidence_id":"e1","document_id":"d1","mappings":[{"openalex_work_id":"https://openalex.org/W2","crossref_doi":"10.1000/x","status":"matched","basis":"reviewed DOI resolution"}]}


class RelationReconciliationTests(unittest.TestCase):
    def test_records_only_explicit_existing_targets(self) -> None:
        artifact = reconciliation_from_review(mission_id="m1", openalex=OPENALEX, crossref=CROSSREF, selection=SELECTION)
        self.assertEqual(artifact["mappings"][0]["status"], "matched")

    def test_rejects_invented_target_identity(self) -> None:
        invalid = dict(SELECTION); invalid["mappings"] = [dict(SELECTION["mappings"][0], crossref_doi="10.1000/not-in-source")]
        with self.assertRaises(RelationReconciliationError): reconciliation_from_review(mission_id="m1", openalex=OPENALEX, crossref=CROSSREF, selection=invalid)
