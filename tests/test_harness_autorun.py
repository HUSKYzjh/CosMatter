from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cosmatter.harness_autorun import HarnessAutoRunError, plan_automatic_mission_authorization, run_authorized_automatic_mission


class _FakeApi:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir
        self.called = False

    def auto_mission(self, _payload: object) -> dict[str, object]:
        self.called = True
        return {"run_id": "run_auto_001", "trust_status": "metadata_only_automatic_run"}


class HarnessAutoRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "question": "How do growth conditions change phase stability in BiFeO3 films?",
            "material": "BiFeO3",
            "property": "phase stability",
            "scope": "epitaxial films",
            "consent": True,
        }

    def test_plan_requires_one_time_consent(self) -> None:
        with self.assertRaises(HarnessAutoRunError):
            plan_automatic_mission_authorization({**self.payload, "consent": False})

    def test_plan_is_scoped_to_the_derived_mission_and_named_plugins(self) -> None:
        plan = plan_automatic_mission_authorization(self.payload)
        self.assertTrue(plan.mission_id.startswith("mission_"))
        self.assertEqual([item["plugin_id"] for item in plan.decisions], ["literature.question_candidates", "literature.metadata_retrieval"])
        self.assertTrue(all(item["permitted"] for item in plan.decisions))

    def test_policy_is_checked_before_legacy_auto_mission_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            api = _FakeApi(Path(directory) / "runs")
            result = run_authorized_automatic_mission(api, self.payload)
            self.assertTrue(api.called)
            self.assertIn("harness_authorization", result)
            events = (api.runs_dir / "run_auto_001" / "events.jsonl").read_text(encoding="utf-8")
            self.assertIn("harness_authorization_checked", events)


if __name__ == "__main__":
    unittest.main()
