import unittest

from cosmatter.config import Settings
from cosmatter.sciverse import SciverseAdapter, SciverseConfigurationError


class FakeClient:
    calls: list[tuple[str, dict[str, object]]] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def semantic_search(self, **kwargs):
        self.calls.append(("semantic_search", kwargs))
        return {"hits": [{"doc_id": "paper-1", "title": "SDK paper", "is_content_accessible": True}], "request_id": "sdk-search"}

    async def read_content(self, **kwargs):
        self.calls.append(("read_content", kwargs))
        return {"text": "bounded context", "next_offset": 21, "more": True, "request_id": "sdk-content"}


class FakeHttpResponse:
    status_code = 403
    headers = {"x-request-id": "sdk-denied"}


class FakeSdkError(RuntimeError):
    response = FakeHttpResponse()


class FailingClient(FakeClient):
    async def semantic_search(self, **kwargs):
        raise FakeSdkError("denied")


class SciverseAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeClient.calls = []
        self.settings = Settings.load({"SCIVERSE_API_TOKEN": "test-token", "HTTP_TIMEOUT_SECONDS": "12"})

    def test_agentic_search_uses_official_sdk_semantic_search_with_bounded_parameters(self) -> None:
        response = SciverseAdapter(self.settings, client_factory=FakeClient).agentic_search("BiFeO3 phase", top_k=5)
        self.assertEqual(FakeClient.calls, [("semantic_search", {"query": "BiFeO3 phase", "top_k": 5, "mode": "balanced"})])
        self.assertEqual(response.request_id, "sdk-search")
        self.assertTrue(SciverseAdapter(self.settings).can_read_content(response.payload["hits"][0]))

    def test_doc_id_allows_content_route_when_optional_flag_is_absent(self) -> None:
        self.assertTrue(SciverseAdapter(self.settings).can_read_content({"doc_id": "fulltext-artifact"}))
        self.assertFalse(SciverseAdapter(self.settings).can_read_content({"doc_id": "fulltext-artifact", "is_content_accessible": False}))

    def test_read_content_uses_sdk_and_keeps_existing_bounds(self) -> None:
        result = SciverseAdapter(self.settings, client_factory=FakeClient).read_content("paper-1", offset=5, limit=200)
        self.assertEqual(FakeClient.calls, [("read_content", {"doc_id": "paper-1", "offset": 5, "limit": 200})])
        self.assertEqual(result.text, "bounded context")
        self.assertEqual(result.request_id, "sdk-content")
        with self.assertRaises(ValueError):
            SciverseAdapter(self.settings).read_content("paper-1", limit=199)

    def test_agentic_search_rejects_unbounded_top_k(self) -> None:
        with self.assertRaises(ValueError):
            SciverseAdapter(self.settings, client_factory=FakeClient).agentic_search("x", top_k=51)

    def test_missing_token_fails_before_sdk_initialization(self) -> None:
        with self.assertRaises(SciverseConfigurationError):
            SciverseAdapter(Settings.load({}), client_factory=FakeClient).agentic_search("x")

    def test_sdk_error_retains_only_safe_status_and_request_id(self) -> None:
        with self.assertRaisesRegex(Exception, r"HTTP 403.*request_id=sdk-denied") as error:
            SciverseAdapter(self.settings, client_factory=FailingClient).agentic_search("x")
        self.assertNotIn("test-token", str(error.exception))
