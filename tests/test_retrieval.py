import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.retrieval import RetrievalArtifactError, candidates_from_sciverse, write_candidate_artifact


class RetrievalArtifactTests(unittest.TestCase):
    def test_candidate_projection_excludes_fulltext_and_deduplicates(self) -> None:
        payload = {
            "hits": [
                {
                    "doc_id": "doc_1",
                    "title": "First material paper",
                    "publication_published_year": 2020,
                    "page_no": 3,
                    "offset": 18,
                    "score": 0.9,
                    "is_content_accessible": True,
                    "abstract": "must not be persisted",
                    "content": "must not be persisted",
                },
                {"doc_id": "doc_1", "title": "Duplicate"},
                {"doc_id": "doc_2", "title": "Second material paper", "score": 0.8},
            ]
        }
        candidates = candidates_from_sciverse(payload, "BiFeO3 phase", 5)

        self.assertEqual([candidate.document_id for candidate in candidates], ["doc_1", "doc_2"])
        self.assertEqual(candidates[0].locator_hint, "page:3;offset:18")
        self.assertTrue(candidates[0].is_content_accessible)
        self.assertNotIn("content", candidates[0].to_dict())
        self.assertNotIn("abstract", candidates[0].to_dict())

    def test_candidate_artifact_rejects_query_mismatch(self) -> None:
        candidates = candidates_from_sciverse({"hits": [{"doc_id": "doc_1", "title": "Paper"}]}, "query_a", 1)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RetrievalArtifactError):
                write_candidate_artifact(Path(directory), "query_b", candidates)

    def test_candidate_artifact_is_metadata_only(self) -> None:
        candidates = candidates_from_sciverse({"hits": [{"doc_id": "doc_1", "title": "Paper"}]}, "query_a", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = write_candidate_artifact(Path(directory), "query_a", candidates)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["candidates"][0]["title"], "Paper")
        self.assertNotIn("quote", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
