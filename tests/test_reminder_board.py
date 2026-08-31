import tempfile
import unittest
from datetime import date
from pathlib import Path

from cosmatter.decision_memory import write_decision_memory_entry
from cosmatter.reminder_board import ReminderBoardError, project_reminder_board, validate_reminder_board


def _summary(*, terminal: bool = False, runtime_safety: str = "verified", incomplete: int = 0, unknown: int = 0, plan_status: str = "waiting_human_review") -> dict[str, object]:
    stages = ["intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"]
    return {"run_id": "run_001", "terminal": terminal, "runtime_safety": runtime_safety, "incomplete_dispatch_count": incomplete, "unknown_dispatch_count": unknown, "stages": [{"stage": stage, "status": "completed" if stage == "intake" else plan_status if stage == "plan" else "blocked"} for stage in stages]}


class ReminderBoardTests(unittest.TestCase):
    def test_projects_local_human_and_overdue_operational_reminders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_decision_memory_entry(root / "memory", {"id": "todo_review", "category": "todo", "status": "active", "source": "human", "created_at": "2026-08-01T00:00:00Z", "expires_on": "2026-08-28", "title": "Review local setup", "body": "Check local configuration."})
            board = project_reminder_board([_summary(runtime_safety="attention_required", unknown=1)], root / "memory", today=date(2026, 8, 29))
        self.assertEqual(board["scheduler_status"], "not_scheduled_local_observation_only")
        self.assertEqual(board["reminder_count"], 4)
        self.assertIn({"scope": "project_memory", "identifier": "todo_review", "kind": "expired_todo", "status": "overdue", "priority": "review", "stage": None, "action_label": "review_operational_todo"}, board["reminders"])
        self.assertNotIn("Review local setup", str(board))

    def test_terminal_runs_do_not_create_reminders_and_schema_rejects_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            board = project_reminder_board([_summary(terminal=True)], Path(directory), today=date(2026, 8, 29))
        self.assertEqual(board["reminders"], [])
        board["command"] = "run"
        with self.assertRaises(ReminderBoardError):
            validate_reminder_board(board)

    def test_incomplete_dispatch_is_visible_before_a_new_recovery_call(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            board = project_reminder_board([_summary(incomplete=1)], Path(directory), today=date(2026, 8, 29))
        self.assertIn({"scope": "run", "identifier": "run_001", "kind": "external_dispatch_incomplete", "status": "open", "priority": "attention", "stage": None, "action_label": "verify_dispatch_before_recovery"}, board["reminders"])

    def test_schema_rejects_an_action_or_scope_that_does_not_match_the_reminder_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            board = project_reminder_board([_summary(incomplete=1)], Path(directory), today=date(2026, 8, 29))
        board["reminders"][0]["action_label"] = "verify_provider_outcome_before_recovery"
        with self.assertRaises(ReminderBoardError):
            validate_reminder_board(board)
        board["reminders"][0]["action_label"] = "verify_dispatch_before_recovery"
        board["reminders"][0]["scope"] = "project_memory"
        with self.assertRaises(ReminderBoardError):
            validate_reminder_board(board)


if __name__ == "__main__":
    unittest.main()
