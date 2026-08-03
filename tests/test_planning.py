import json
import tempfile
import unittest
from pathlib import Path

from cosmatter.deepseek import DraftCompletion
from cosmatter.models import MissionBrief
from cosmatter.planning import research_planning_prompts, write_untrusted_plan_draft


class PlanningTests(unittest.TestCase):
    def test_prompts_only_contain_mission_metadata_and_explicit_limits(self) -> None:
        mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_1")
        system, user = research_planning_prompts(mission)
        payload = json.loads(user)

        self.assertIn("untrusted JSON draft", system)
        self.assertEqual(payload["limits"]["max_queries"], 8)
        self.assertNotIn("quote", user)

    def test_draft_file_is_explicitly_untrusted(self) -> None:
        completion = DraftCompletion("{\"queries\": []}", "deepseek-v4-flash", "request_1")
        with tempfile.TemporaryDirectory() as directory:
            path = write_untrusted_plan_draft(Path(directory), completion)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["trust_status"], "untrusted_draft")
        self.assertNotIn("request_id", payload)


if __name__ == "__main__":
    unittest.main()
