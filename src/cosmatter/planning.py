"""LLM-assisted planning drafts that remain outside evidence and release gates."""

from __future__ import annotations

import json
from pathlib import Path

from .deepseek import DraftCompletion
from .models import FlightPlan, MissionBrief


def research_planning_prompts(mission: MissionBrief) -> tuple[str, str]:
    """Build a metadata-only prompt that requests bounded search suggestions."""
    system_prompt = (
        "You are the CosMatter research-planning station. Produce an untrusted JSON draft with "
        "subquestions, bounded search queries, and counterevidence queries. Do not claim any "
        "scientific fact, invent citations, request full text, or write a final conclusion."
    )
    user_prompt = json.dumps(
        {
            "question": mission.question,
            "material": mission.material,
            "property_name": mission.property_name,
            "scope": mission.scope,
            "source_policy": mission.source_policy.value,
            "limits": {"max_subquestions": 5, "max_queries": 8, "max_counterevidence_queries": 4},
        },
        ensure_ascii=False,
    )
    return system_prompt, user_prompt


def write_untrusted_plan_draft(run_dir: Path, completion: DraftCompletion) -> Path:
    """Persist the LLM result as a draft that must be reviewed before execution."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "research_plan_draft.json"
    payload = {
        "schema_version": "1.0",
        "trust_status": "untrusted_draft",
        "model": completion.model,
        "content": completion.content,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

class PlanApprovalError(ValueError):
    """Raised when a reviewed plan is not a bounded FlightPlan."""


_PLAN_FIELDS = {"subquestions", "queries", "counter_queries", "max_rounds", "max_papers"}


def approved_flight_plan_from_payload(mission: MissionBrief, payload: object) -> FlightPlan:
    """Validate a separately reviewed planning JSON; never parse LLM drafts implicitly."""
    if not isinstance(payload, dict) or set(payload) - _PLAN_FIELDS:
        raise PlanApprovalError("reviewed plan must be a JSON object with supported fields only")
    try:
        subquestions = _bounded_strings(payload["subquestions"], "subquestions", 5)
        queries = _bounded_strings(payload["queries"], "queries", 8)
        counter_queries = _bounded_strings(payload["counter_queries"], "counter_queries", 4)
        max_rounds = int(payload.get("max_rounds", 3))
        max_papers = int(payload.get("max_papers", 20))
        if not 1 <= max_rounds <= 3 or not 1 <= max_papers <= 20:
            raise PlanApprovalError("reviewed plan limits exceed the configured baseline")
        return FlightPlan(
            mission_id=mission.mission_id,
            subquestions=subquestions,
            queries=queries,
            counter_queries=counter_queries,
            max_rounds=max_rounds,
            max_papers=max_papers,
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, PlanApprovalError):
            raise
        raise PlanApprovalError("reviewed plan does not satisfy FlightPlan") from error


def _bounded_strings(value: object, name: str, maximum: int) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise PlanApprovalError(f"{name} must be a nonempty array with at most {maximum} items")
    items = tuple(str(item).strip() for item in value)
    if any(not item for item in items) or len(set(items)) != len(items):
        raise PlanApprovalError(f"{name} must contain unique nonempty strings")
    return items


def write_approved_flight_plan(run_dir: Path, plan: FlightPlan) -> Path:
    """Persist the reviewed executable plan separately from untrusted LLM drafts."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "flight_plan.json"
    path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path