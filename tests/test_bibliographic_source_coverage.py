import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.bibliographic_source_coverage import (
    BibliographicSourceCoverageError,
    bibliographic_source_coverage_audit,
    bibliographic_source_template_from_manifest,
    load_bibliographic_source_coverage,
    write_bibliographic_source_template,
)
from cosmatter.corpus_preparation import corpus_manifest_from_review, write_corpus_manifest


def manifest() -> dict:
    return corpus_manifest_from_review(
        mission_id="mission_1", material="BiFeO3", selection={
            "corpus_id": "bfo_90_v1", "material": "BiFeO3", "documents": [
                {"document_id": "doc_1", "title": "Private record one", "doi": None, "access_policy": "institutional_access_internal_review_only"},
                {"document_id": "doc_2", "title": "Private record two", "doi": None, "access_policy": "institutional_access_internal_review_only"},
            ],
        },
    )


class BibliographicSourceCoverageTests(unittest.TestCase):
    def test_blank_template_and_completed_coverage_keep_labels_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            frozen = manifest()
            write_corpus_manifest(run, frozen)
            registry = bibliographic_source_template_from_manifest(frozen)
            template_path = write_bibliographic_source_template(run, registry)
            self.assertTrue(template_path.is_file())
            blank = bibliographic_source_coverage_audit(run_dir=run, mission_id="mission_1", registry_path=template_path)
            self.assertEqual(blank["bibliographic_source_coverage_gate"], "blocked_until_every_frozen_document_has_human_reviewed_bibliographic_source")
            registry["trust_status"] = "human_reviewed_bibliographic_source_registry"
            for item in registry["documents"]:
                item["bibliographic_source"] = "OpenAlex" if item["document_id"] == "doc_1" else "School-authorized library metadata"
            reviewed_path = run / "private_registry.json"
            reviewed_path.write_text(json.dumps(registry), encoding="utf-8")
            audit = bibliographic_source_coverage_audit(run_dir=run, mission_id="mission_1", registry_path=reviewed_path)
            (run / "bibliographic_source_coverage.json").write_text(json.dumps(audit), encoding="utf-8")
            loaded = load_bibliographic_source_coverage(run / "bibliographic_source_coverage.json", mission_id="mission_1", corpus_id="bfo_90_v1", document_count=2)
        self.assertEqual(loaded["documents_with_reviewed_bibliographic_source"], 2)
        self.assertEqual(loaded["distinct_bibliographic_source_count"], 2)
        self.assertNotIn("OpenAlex", json.dumps(audit))
        self.assertNotIn("doc_1", json.dumps(audit))

    def test_rejects_private_paths_and_partial_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            frozen = manifest()
            write_corpus_manifest(run, frozen)
            registry = bibliographic_source_template_from_manifest(frozen)
            registry["trust_status"] = "human_reviewed_bibliographic_source_registry"
            registry["documents"][0]["bibliographic_source"] = "C:\\Users\\private\\library"
            registry["documents"][1]["bibliographic_source"] = "OpenAlex"
            path = run / "unsafe_registry.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            with self.assertRaises(BibliographicSourceCoverageError):
                bibliographic_source_coverage_audit(run_dir=run, mission_id="mission_1", registry_path=path)


if __name__ == "__main__":
    unittest.main()
