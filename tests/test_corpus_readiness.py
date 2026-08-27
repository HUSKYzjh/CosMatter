import tempfile
import unittest
from pathlib import Path

from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest
from cosmatter.corpus_readiness import frozen_corpus_readiness, write_frozen_corpus_readiness


class CorpusReadinessTests(unittest.TestCase):
    def test_reports_count_and_doi_coverage_without_document_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            manifest = corpus_manifest_from_review(
                mission_id="mission_90", material="BiFeO3",
                selection={"corpus_id": "bfo_90", "material": "BiFeO3", "documents": [
                    {"document_id": "doc_1", "title": "Private title", "doi": "10.1000/example", "access_policy": "institutional_access_internal_review_only"},
                    {"document_id": "doc_2", "title": "Another private title", "doi": None, "access_policy": "institutional_access_internal_review_only"},
                ]},
            )
            write_corpus_manifest(run, manifest)
            audit = frozen_corpus_readiness(run_dir=run, mission_id="mission_90", expected_document_count=2)
            path = write_frozen_corpus_readiness(run, audit)
            rendered = path.read_text(encoding="utf-8")
        self.assertTrue(audit["expected_count_matched"])
        self.assertEqual(audit["doi_missing_count"], 1)
        self.assertNotIn("Private title", rendered)


if __name__ == "__main__":
    unittest.main()
