import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.config import Settings
from cosmatter.deepseek import DraftCompletion
from cosmatter.local_api import LocalMissionApi
from cosmatter.sciverse import SciverseResponse


class _FakeDeepSeek:
    def __init__(self, settings):
        self.settings = settings

    def draft(self, **_):
        return DraftCompletion(content='{"queries":["test"]}', model="deepseek-test", request_id="request-1")


class _FakeSciverse:
    def __init__(self, settings):
        self.settings = settings

    def agentic_search(self, query, *, top_k):
        return SciverseResponse(
            payload={
                "hits": [
                    {"doc_id": "doc-1", "title": "A bounded paper", "is_content_accessible": True, "score": 0.9}
                ]
            },
            status_code=200,
            request_id="search-1",
        )


class LocalMissionApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.runs = Path(self.directory.name) / "runs"
        self.api = LocalMissionApi(
            self.runs,
            settings_loader=lambda: Settings.load(
                {"LLM_PROVIDER": "deepseek", "LLM_MODEL": "deepseek-v4-flash", "DEEPSEEK_API_KEY": "test", "SCIVERSE_API_TOKEN": "test"}
            ),
        )

    def tearDown(self):
        self.directory.cleanup()

    def _mission(self):
        return self.api.create_mission(
            {
                "run_id": "live_001",
                "question": "How do conditions affect phase stability?",
                "material": "BiFeO3",
                "property": "phase stability",
                "scope": "epitaxial films",
            }
        )

    def test_status_and_mission_creation_do_not_return_a_secret(self):
        status = self.api.status()
        created = self._mission()
        self.assertEqual(status["api_mode"], "loopback_only")
        self.assertTrue(status["providers"]["deepseek"])
        self.assertEqual(created["run_id"], "live_001")
        self.assertTrue((self.runs / "live_001" / "mission.json").is_file())
        self.assertNotIn("test", json.dumps({"status": status, "created": created}))

    def test_live_draft_requires_review_before_sciverse_query(self):
        self._mission()
        with patch("cosmatter.local_api.DeepSeekAdapter", _FakeDeepSeek):
            draft = self.api.draft_plan("live_001")
        self.assertEqual(draft["trust_status"], "untrusted_draft")
        self.assertTrue((self.runs / "live_001" / "research_plan_draft.json").is_file())
        approved = self.api.approve_plan(
            "live_001",
            {
                "subquestions": ["Which conditions differ?"],
                "queries": ["BiFeO3 phase stability epitaxial"],
                "counter_queries": ["BiFeO3 contradictory phase reports"],
            },
        )
        self.assertEqual(approved["queries"], ["BiFeO3 phase stability epitaxial"])
        with patch("cosmatter.local_api.SciverseAdapter", _FakeSciverse):
            result = self.api.execute_plan_query("live_001", {"query_index": 0, "counter": False})
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["document_id"], "doc-1")
        self.assertNotIn("request-1", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
