import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.models import PaperCandidate
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
        self.assertTrue(candidates[1].is_content_accessible)
        self.assertNotIn("content", candidates[0].to_dict())
        self.assertNotIn("abstract", candidates[0].to_dict())

    def test_malformed_provider_doi_does_not_drop_an_otherwise_valid_candidate(self) -> None:
        candidates = candidates_from_sciverse(
            {"hits": [{"doc_id": "doc_1", "title": "Paper", "doi": "not-a-doi"}]},
            "BiFeO3 phase",
            1,
        )
        self.assertEqual(len(candidates), 1)
        self.assertIsNone(candidates[0].doi)

    def test_doc_id_is_a_documented_content_route_when_access_flag_is_absent(self) -> None:
        candidates = candidates_from_sciverse(
            {"hits": [{"doc_id": "fulltext-artifact", "title": "Paper"}]},
            "BiFeO3 phase",
            1,
        )
        self.assertTrue(candidates[0].is_content_accessible)

    def test_mathml_title_is_normalized_without_namespace_url(self) -> None:
        candidates = candidates_from_sciverse(
            {
                "hits": [
                    {
                        "doc_id": "doc_mathml",
                        "title": '<mml:math xmlns:mml="http://www.w3.org/1998/Math/MathML"><mml:mi>BiFeO</mml:mi><mml:mn>3</mml:mn></mml:math> films',
                    }
                ]
            },
            "BiFeO3 phase",
            1,
        )

        title = candidates[0].title
        self.assertNotIn("http://", title)
        self.assertNotIn("<mml:", title)
        self.assertIn("BiFeO", title)
        with tempfile.TemporaryDirectory() as directory:
            artifact = write_candidate_artifact(Path(directory), "BiFeO3 phase", candidates)
            persisted = artifact.read_text(encoding="utf-8")
        self.assertNotIn("http://", persisted)
        self.assertNotIn("<mml:", persisted)

    def test_candidate_rejects_title_that_remains_a_url_after_normalization(self) -> None:
        with self.assertRaises(ValueError):
            PaperCandidate(
                document_id="doc_url_title",
                title="https://example.invalid/not-a-title",
                query="query",
                source="Sciverse",
            )

    def test_candidate_artifact_rejects_query_mismatch(self) -> None:
        candidates = candidates_from_sciverse({"hits": [{"doc_id": "doc_1", "title": "Paper"}]}, "query_a", 1)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RetrievalArtifactError):
                write_candidate_artifact(Path(directory), "query_b", candidates)

    def test_candidate_artifact_accumulates_search_history_without_duplicate_documents(self) -> None:
        first = candidates_from_sciverse(
            {"hits": [{"doc_id": "doc_1", "title": "First", "is_content_accessible": False}]},
            "query_one",
            1,
        )
        second = candidates_from_sciverse(
            {
                "hits": [
                    {"doc_id": "doc_1", "title": "First from another query", "is_content_accessible": True},
                    {"doc_id": "doc_2", "title": "Second", "is_content_accessible": False},
                ]
            },
            "query_two",
            2,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_candidate_artifact(Path(directory), "query_one", first)
            path = write_candidate_artifact(Path(directory), "query_two", second)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["search_count"], 2)
        self.assertEqual(len(payload["candidates"]), 2)
        selected_doc_1 = next(item for item in payload["candidates"] if item["document_id"] == "doc_1")
        self.assertTrue(selected_doc_1["is_content_accessible"])
        self.assertEqual(payload["searches"][0]["query"], "query_one")
        self.assertEqual(payload["searches"][1]["query"], "query_two")
        self.assertEqual(len(selected_doc_1["retrieval_origins"]), 2)
        self.assertEqual(selected_doc_1["retrieval_origins"][0]["source"], "Sciverse")

    def test_candidate_artifact_deduplicates_exact_doi_across_distinct_document_ids(self) -> None:
        first = PaperCandidate(
            document_id="sciverse:record_1", title="First provider record", query="query_one",
            source="Sciverse", is_content_accessible=False, doi="https://doi.org/10.1000/Shared.DOI",
        )
        second = PaperCandidate(
            document_id="openalex:W2", title="Second provider record", query="query_two",
            source="OpenAlex", is_content_accessible=True, doi="10.1000/shared.doi",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_candidate_artifact(Path(directory), "query_one", (first,))
            path = write_candidate_artifact(Path(directory), "query_two", (second,))
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["candidate_count"], 1)
        candidate = payload["candidates"][0]
        self.assertEqual(candidate["document_id"], "openalex:W2")
        self.assertEqual(candidate["doi"], "10.1000/shared.doi")
        self.assertEqual(candidate["deduplication"], {"identity_method": "doi", "merged_candidate_count": 2, "merged_document_count": 2})
        self.assertEqual({origin["retrieved_document_id"] for origin in candidate["retrieval_origins"]}, {"sciverse:record_1", "openalex:W2"})

    def test_candidate_origin_links_a_matching_provider_receipt_without_payload(self) -> None:
        query = "BiFeO3 phase"
        candidates = candidates_from_sciverse({"hits": [{"doc_id": "doc_1", "title": "Paper"}]}, query, 1)
        provenance = {"Sciverse": {"provider": "sciverse", "operation": "agentic_search", "receipt_id": "receipt_fixture", "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest()}}
        with tempfile.TemporaryDirectory() as directory:
            path = write_candidate_artifact(Path(directory), query, candidates, source_provenance=provenance)
            payload = json.loads(path.read_text(encoding="utf-8"))
        origin = payload["candidates"][0]["retrieval_origins"][0]
        self.assertEqual(origin["receipt_id"], "receipt_fixture")
        self.assertNotIn("abstract", json.dumps(payload))
        with self.assertRaises(RetrievalArtifactError):
            write_candidate_artifact(Path(tempfile.gettempdir()), query, candidates, source_provenance={"Sciverse": {**provenance["Sciverse"], "query_sha256": "0" * 64}})

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
