import unittest

from cosmatter.config import Settings
from cosmatter.metadata_search import MetadataSearchAdapter


class MetadataSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings.load({"OPENALEX_API_KEY": "test-key", "API_MAX_RETRIES": "1"})

    def test_openalex_projects_only_bounded_candidate_metadata(self) -> None:
        adapter = MetadataSearchAdapter(self.settings)
        adapter._request_json = lambda *_: {"results": [{"id": "https://openalex.org/W1", "display_name": "A title", "publication_year": 2024, "open_access": {"is_oa": True}, "doi": "https://doi.org/10.1000/OPENALEX", "cited_by_count": 8, "abstract_inverted_index": {"hidden": [0]}}]}
        candidates = adapter.search_openalex("BiFeO3", top_k=3)
        self.assertEqual(candidates[0].document_id, "openalex:W1")
        self.assertEqual(candidates[0].source, "OpenAlex")
        self.assertEqual(candidates[0].doi, "10.1000/openalex")
        self.assertTrue(candidates[0].is_content_accessible)
        self.assertNotIn("hidden", str(candidates[0].to_dict()))

    def test_crossref_projects_title_doi_and_year_only(self) -> None:
        adapter = MetadataSearchAdapter(self.settings)
        adapter._request_json = lambda *_: {"message": {"items": [{"DOI": "10.1000/test", "title": ["A Crossref title"], "published": {"date-parts": [[2023, 1, 1]]}, "is-referenced-by-count": 3, "abstract": "hidden"}]}}
        candidates = adapter.search_crossref("BiFeO3", top_k=3)
        self.assertEqual(candidates[0].document_id, "doi:10.1000/test")
        self.assertEqual(candidates[0].doi, "10.1000/test")
        self.assertEqual(candidates[0].publication_year, 2023)
        self.assertEqual(candidates[0].source, "Crossref")
        self.assertNotIn("hidden", str(candidates[0].to_dict()))


if __name__ == "__main__":
    unittest.main()
