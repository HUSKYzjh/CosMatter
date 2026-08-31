"""Local, cross-session operational reminder projection.

This is an observation board, not a scheduler.  It never stores a timer,
invokes an action, reads decision-memory bodies, or turns a reminder into an
authorisation.  An overdue item becomes visible the next time a local client
reads the board; closing a session never claims that work ran in its absence.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .decision_memory import DecisionMemoryError, load_decision_memory_index


REMINDER_BOARD_SCHEMA_VERSION = "cosmatter.project-reminder-board/v1"
REMINDER_BOARD_TRUST_STATUS = "loopback_operational_reminders_not_schedule_or_execution_authorization"
_REMINDER_RULES = {
    "human_review_required": ("run", "complete_human_review", True),
    "workflow_blocked": ("run", "review_stage_boundary", True),
    "runtime_attention": ("run", "inspect_runtime_invariants", False),
    "external_dispatch_incomplete": ("run", "verify_dispatch_before_recovery", False),
    "external_outcome_unknown": ("run", "verify_provider_outcome_before_recovery", False),
    "expired_todo": ("project_memory", "review_operational_todo", False),
}
_KINDS = set(_REMINDER_RULES)
_PRIORITIES = {"attention", "review"}
_STATUSES = {"open", "overdue"}
_FIELDS = {"schema_version", "trust_status", "scheduler_status", "reminder_count", "reminders"}
_REMINDER_FIELDS = {"scope", "identifier", "kind", "status", "priority", "stage", "action_label"}


class ReminderBoardError(ValueError):
    """Raised when a reminder projection would be malformed or unsafe."""


def project_reminder_board(run_summaries: object, memory_dir: Path, *, today: date | None = None) -> dict[str, Any]:
    """Build a bounded, deterministic status board from safe local summaries."""
    if not isinstance(run_summaries, list):
        raise ReminderBoardError("run summaries are invalid")
    reminders: list[dict[str, Any]] = []
    for summary in run_summaries:
        _validate_run_summary(summary)
        if summary["terminal"]:
            continue
        identifier = summary["run_id"]
        if summary["runtime_safety"] == "attention_required":
            reminders.append(_reminder("run", identifier, "runtime_attention", "open", "attention", None, "inspect_runtime_invariants"))
        first_unfinished = next((stage for stage in summary["stages"] if stage["status"] != "completed"), None)
        if first_unfinished is not None and first_unfinished["status"] == "blocked":
            reminders.append(_reminder("run", identifier, "workflow_blocked", "open", "attention", first_unfinished["stage"], "review_stage_boundary"))
        elif first_unfinished is not None and first_unfinished["status"] == "waiting_human_review":
            reminders.append(_reminder("run", identifier, "human_review_required", "open", "review", first_unfinished["stage"], "complete_human_review"))
        if summary["incomplete_dispatch_count"]:
            reminders.append(_reminder("run", identifier, "external_dispatch_incomplete", "open", "attention", None, "verify_dispatch_before_recovery"))
        if summary["unknown_dispatch_count"]:
            reminders.append(_reminder("run", identifier, "external_outcome_unknown", "open", "attention", None, "verify_provider_outcome_before_recovery"))
    try:
        index = load_decision_memory_index(memory_dir)
    except DecisionMemoryError as error:
        raise ReminderBoardError(str(error)) from error
    reference_day = today or date.today()
    for entry in index["entries"]:
        if entry["category"] == "todo" and entry["status"] == "active" and entry["expires_on"] is not None and entry["expires_on"] <= reference_day.isoformat():
            reminders.append(_reminder("project_memory", entry["id"], "expired_todo", "overdue", "review", None, "review_operational_todo"))
    priority_order = {"attention": 0, "review": 1}
    reminders.sort(key=lambda item: (priority_order[item["priority"]], item["scope"], item["identifier"], item["kind"], item["stage"] or ""))
    result = {
        "schema_version": REMINDER_BOARD_SCHEMA_VERSION,
        "trust_status": REMINDER_BOARD_TRUST_STATUS,
        "scheduler_status": "not_scheduled_local_observation_only",
        "reminder_count": len(reminders),
        "reminders": reminders,
    }
    validate_reminder_board(result)
    return result


def validate_reminder_board(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise ReminderBoardError("reminder board fields are invalid")
    if payload.get("schema_version") != REMINDER_BOARD_SCHEMA_VERSION or payload.get("trust_status") != REMINDER_BOARD_TRUST_STATUS or payload.get("scheduler_status") != "not_scheduled_local_observation_only" or not isinstance(payload.get("reminder_count"), int) or payload["reminder_count"] < 0 or payload["reminder_count"] > 100 or not isinstance(payload.get("reminders"), list) or len(payload["reminders"]) != payload["reminder_count"]:
        raise ReminderBoardError("reminder board identity is invalid")
    seen: set[tuple[str, str, str, str | None]] = set()
    for item in payload["reminders"]:
        if not isinstance(item, dict) or set(item) != _REMINDER_FIELDS or item.get("scope") not in {"run", "project_memory"} or not isinstance(item.get("identifier"), str) or not item["identifier"] or len(item["identifier"]) > 80 or item.get("kind") not in _KINDS or item.get("status") not in _STATUSES or item.get("priority") not in _PRIORITIES or item.get("stage") is not None and item["stage"] not in {"intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation"} or not isinstance(item.get("action_label"), str):
            raise ReminderBoardError("reminder board item is invalid")
        expected_scope, expected_action, requires_stage = _REMINDER_RULES[item["kind"]]
        if item["scope"] != expected_scope or item["action_label"] != expected_action or (item["stage"] is not None) != requires_stage:
            raise ReminderBoardError("reminder board item semantics are invalid")
        key = (item["scope"], item["identifier"], item["kind"], item["stage"])
        if key in seen:
            raise ReminderBoardError("reminder board items are duplicated")
        seen.add(key)


def _reminder(scope: str, identifier: str, kind: str, status: str, priority: str, stage: str | None, action_label: str) -> dict[str, Any]:
    return {"scope": scope, "identifier": identifier, "kind": kind, "status": status, "priority": priority, "stage": stage, "action_label": action_label}


def _validate_run_summary(value: object) -> None:
    fields = {"run_id", "terminal", "runtime_safety", "incomplete_dispatch_count", "unknown_dispatch_count", "stages"}
    if not isinstance(value, dict) or set(value) != fields or not isinstance(value.get("run_id"), str) or not value["run_id"] or len(value["run_id"]) > 80 or not isinstance(value.get("terminal"), bool) or value.get("runtime_safety") not in {"verified", "attention_required"} or any(not isinstance(value.get(name), int) or value[name] < 0 or value[name] > 1_000_000 for name in ("incomplete_dispatch_count", "unknown_dispatch_count")) or not isinstance(value.get("stages"), list) or len(value["stages"]) != 9:
        raise ReminderBoardError("run summary is invalid")
    expected_stages = ("intake", "plan", "retrieval", "screening", "parse", "extraction", "gap", "report", "evaluation")
    for expected, stage in zip(expected_stages, value["stages"]):
        if not isinstance(stage, dict) or set(stage) != {"stage", "status"} or stage.get("stage") != expected or stage.get("status") not in {"completed", "ready", "waiting_human_review", "blocked"}:
            raise ReminderBoardError("run summary stage is invalid")
