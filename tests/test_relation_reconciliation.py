import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.relation_reconciliation import RelationReconciliationError, load_relation_reconciliation, reconciliation_from_review, write_relation_reconciliation


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

    def test_write_appends_summary_only_revision_history_and_reads_legacy_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            legacy = reconciliation_from_review(mission_id="m1", openalex=OPENALEX, crossref=CROSSREF, selection=SELECTION)
            legacy = {key: value for key, value in legacy.items() if key != "revision_history"}
            legacy["schema_version"] = "1.0"
            (run_dir / "relation_reconciliation.json").write_text(json.dumps(legacy), encoding="utf-8")
            current = reconciliation_from_review(mission_id="m1", openalex=OPENALEX, crossref=CROSSREF, selection=SELECTION)
            write_relation_reconciliation(run_dir, current)
            stored = load_relation_reconciliation(run_dir / "relation_reconciliation.json", "m1")
            self.assertEqual(stored["schema_version"], "1.1")
            self.assertEqual(len(stored["revision_history"]), 2)
            self.assertEqual(stored["revision_history"][-1]["revision"], 2)
            self.assertEqual(set(stored["revision_history"][-1]), {"revision", "recorded_at", "mapping_count", "status_counts", "mappings_sha256"})
            self.assertNotIn("basis", stored["revision_history"][-1])
