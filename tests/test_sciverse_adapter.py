import json
import unittest
from unittest.mock import patch

from cosmatter.config import Settings
from cosmatter.sciverse import SciverseAdapter


class FakeResponse:
    status = 200
    headers = {"x-request-id": "request-test"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return json.dumps({"hits": [{"doc_id": "paper-1", "is_content_accessible": True}]}).encode("utf-8")


class SciverseAdapterTests(unittest.TestCase):
    def test_agentic_search_sends_bounded_request(self) -> None:
        settings = Settings.load({"SCIVERSE_API_TOKEN": "test-token", "API_MAX_RETRIES": "1"})
        with patch("cosmatter.sciverse.urlopen", return_value=FakeResponse()) as mocked:
            response = SciverseAdapter(settings, sleep=lambda _: None).agentic_search("BiFeO3 phase", top_k=5)
        request = mocked.call_args.args[0]
        self.assertTrue(request.full_url.endswith("/agentic-search"))
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"query": "BiFeO3 phase", "top_k": 5})
        self.assertEqual(response.request_id, "request-test")
        self.assertTrue(SciverseAdapter(settings).can_read_content(response.payload["hits"][0]))


    def test_read_content_uses_bounded_query_parameters(self) -> None:
        settings = Settings.load({"SCIVERSE_API_TOKEN": "test-token", "API_MAX_RETRIES": "1"})
        response = FakeResponse()
        response.read = lambda: json.dumps({"text": "bounded context", "next_offset": 21, "more": True}).encode("utf-8")
        with patch("cosmatter.sciverse.urlopen", return_value=response) as mocked:
            result = SciverseAdapter(settings, sleep=lambda _: None).read_content("paper-1", offset=5, limit=200)
        request = mocked.call_args.args[0]
        self.assertIn("/content?doc_id=paper-1&offset=5&limit=200", request.full_url)
        self.assertEqual(result.text, "bounded context")
        with self.assertRaises(ValueError):
            SciverseAdapter(settings).read_content("paper-1", limit=199)

    def test_agentic_search_rejects_unbounded_top_k(self) -> None:
        settings = Settings.load({"SCIVERSE_API_TOKEN": "test-token"})
        with self.assertRaises(ValueError):
            SciverseAdapter(settings).agentic_search("x", top_k=51)
