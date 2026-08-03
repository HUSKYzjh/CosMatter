import json
import unittest
from unittest.mock import patch

from cosmatter.config import Settings
from cosmatter.openalex import OpenAlexAdapter, normalize_doi


class FakeResponse:
    headers = {"x-request-id": "openalex-test"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps(
            {
                "id": "https://openalex.org/W1",
                "referenced_works": ["https://openalex.org/W2", "invalid"],
                "related_works": ["https://openalex.org/W3"],
            }
        ).encode("utf-8")


class OpenAlexAdapterTests(unittest.TestCase):
    def test_lookup_uses_doi_and_preserves_distinct_relation_lists(self) -> None:
        settings = Settings.load({"OPENALEX_API_KEY": "test-key", "OPENALEX_BASE_URL": "https://openalex.example", "API_MAX_RETRIES": "1"})
        with patch("cosmatter.openalex.urlopen", return_value=FakeResponse()) as mocked:
            work = OpenAlexAdapter(settings, sleep=lambda _: None).work_relations_by_doi("https://doi.org/10.1000/test")
        request = mocked.call_args.args[0]
        self.assertIn("/works/https://doi.org/10.1000/test?select=", request.full_url)
        self.assertEqual(work.referenced_work_ids, ("https://openalex.org/W2",))
        self.assertEqual(work.related_work_ids, ("https://openalex.org/W3",))
        self.assertEqual(work.request_id, "openalex-test")

    def test_doi_normalization_rejects_invalid_values(self) -> None:
        self.assertEqual(normalize_doi(" DOI:10.1000/ABC "), "10.1000/abc")
        with self.assertRaises(ValueError):
            normalize_doi("not-a-doi")
