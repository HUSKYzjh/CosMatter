import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.corpus_preparation import corpus_manifest_from_review
from cosmatter.local_corpus import candidates_from_local_source_index


def _manifest() -> dict[str, object]:
    return corpus_manifest_from_review(
        mission_id="m_bm25",
        material="BiFeO3",
        selection={
            "corpus_id": "bm25_fixture",
            "material": "BiFeO3",
            "documents": [
                {"document_id": "relevant", "title": "BiFeO3 phase stability under strain", "doi": None, "access_policy": "institutional_access_internal_review_only"},
                {"document_id": "partial", "title": "BiFeO3 ferroelectric properties", "doi": None, "access_policy": "institutional_access_internal_review_only"},
                {"document_id": "noise", "title": "Unrelated oxide review", "doi": None, "access_policy": "institutional_access_internal_review_only"},
            ],
        },
    )


class LocalCorpusBm25Tests(unittest.TestCase):
    def test_bm25_prioritizes_specific_query_coverage_without_persisting_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "relevant": root / "relevant.md",
                "partial": root / "partial.md",
                "noise": root / "noise.md",
            }
            files["relevant"].write_text("phase stability changes under epitaxial strain", encoding="utf-8")
            files["partial"].write_text("ferroelectric polarization and strain measurements", encoding="utf-8")
            files["noise"].write_text("catalysis and electrochemistry", encoding="utf-8")
            index = root / "private-index.json"
            index.write_text(json.dumps({"documents": [
                {"document_id": document_id, "title": next(item["title"] for item in _manifest()["documents"] if item["document_id"] == document_id), "path": str(path), "parser_provenance": "mineru_reviewed_local_output"}
                for document_id, path in files.items()
            ]}), encoding="utf-8")
            candidates = candidates_from_local_source_index(
                manifest=_manifest(), index_path=index, query="BiFeO3 phase stability strain", top_k=3,
            )
        self.assertEqual([item.document_id for item in candidates], ["relevant", "partial"])
        self.assertEqual(candidates[0].source, "Authorized local parsed corpus (BM25)")
        self.assertGreater(candidates[0].score or 0, candidates[1].score or 0)
        self.assertNotIn("epitaxial strain", json.dumps([item.to_dict() for item in candidates]))
        self.assertNotIn("private-index", json.dumps([item.to_dict() for item in candidates]))


if __name__ == "__main__":
    unittest.main()
