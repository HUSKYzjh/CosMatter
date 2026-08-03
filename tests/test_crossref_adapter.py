import json
import unittest
from unittest.mock import patch

from cosmatter.config import Settings
from cosmatter.crossref import CrossrefAdapter, _work_from_payload


class FakeResponse:
    headers = {"x-request-id": "crossref-test"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps(
            {
                "message": {
                    "DOI": "10.1000/ROOT",
                    "reference": [{"DOI": "10.1000/A"}, {"DOI": "not-a-doi"}, {"unstructured": "metadata only"}],
                }
            }
        ).encode("utf-8")


class CrossrefAdapterTests(unittest.TestCase):
    def test_lookup_uses_encoded_doi_and_polite_contact_when_configured(self) -> None:
        settings = Settings.load({"CROSSREF_MAILTO": "team@example.org", "CROSSREF_BASE_URL": "https://crossref.example", "API_MAX_RETRIES": "1"})
        with patch("cosmatter.crossref.urlopen", return_value=FakeResponse()) as mocked:
            work = CrossrefAdapter(settings, sleep=lambda _: None).work_references_by_doi("https://doi.org/10.1000/ROOT")
        request = mocked.call_args.args[0]
        self.assertIn("/works/10.1000%2Froot?mailto=team%40example.org", request.full_url)
        self.assertIn("mailto:team@example.org", request.get_header("User-agent"))
        self.assertEqual(work.doi, "10.1000/root")
        self.assertEqual(work.referenced_dois, ("10.1000/a",))
        self.assertTrue(work.reference_field_present)
        self.assertEqual(work.request_id, "crossref-test")

    def test_missing_reference_field_is_not_interpreted_as_zero_references(self) -> None:
        work = _work_from_payload({"message": {"DOI": "10.1000/root"}}, None)
        self.assertFalse(work.reference_field_present)
        self.assertEqual(work.referenced_dois, ())
