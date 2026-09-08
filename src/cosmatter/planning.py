"""LLM-assisted planning drafts that remain outside evidence and release gates."""

from __future__ import annotations

import json
from pathlib import Path

from .deepseek import DraftCompletion
from .models import ApprovedQueryTrack, FlightPlan, MissionBrief
from .research_tracks import DEFAULT_TRACK_CANDIDATE_MINIMUMS, RESEARCH_TRACKS


def research_planning_prompts(mission: MissionBrief) -> tuple[str, str]:
    """Build a metadata-only prompt that requests bounded search suggestions."""
    system_prompt = (
        "You are the CosMatter research-planning station. Produce an untrusted JSON draft with "
        "subquestions, bounded search queries, counterevidence queries, and three proposed query-track "
        "assignments (exact_material, mechanism_analogue, algorithm) that a human must review. Do not claim any "
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
            "required_plan_fields": {
                "query_tracks": [
                    {"query_index": 0, "research_track": "exact_material"},
                    {"query_index": 1, "research_track": "mechanism_analogue"},
                    {"query_index": 2, "research_track": "algorithm"},
                ],
                "track_candidate_minimums": DEFAULT_TRACK_CANDIDATE_MINIMUMS,
            },
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


_PLAN_FIELDS = {
    "subquestions", "queries", "counter_queries", "max_rounds", "max_papers",
    "query_tracks", "track_candidate_minimums",
}


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
        query_tracks, track_candidate_minimums = _approved_query_tracks(payload, len(queries))
        return FlightPlan(
            mission_id=mission.mission_id,
            subquestions=subquestions,
            queries=queries,
            counter_queries=counter_queries,
            max_rounds=max_rounds,
            max_papers=max_papers,
            query_tracks=query_tracks,
            track_candidate_minimums=track_candidate_minimums,
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


def _approved_query_tracks(payload: dict[str, object], query_count: int) -> tuple[tuple[ApprovedQueryTrack, ...], dict[str, int]]:
    """Validate an optional vNext three-track block while retaining old plans."""
    has_tracks = "query_tracks" in payload
    has_minimums = "track_candidate_minimums" in payload
    if has_tracks != has_minimums:
        raise PlanApprovalError("query_tracks and track_candidate_minimums must be supplied together")
    if not has_tracks:
        return (), {}
    raw_tracks = payload["query_tracks"]
    raw_minimums = payload["track_candidate_minimums"]
    if not isinstance(raw_tracks, list) or len(raw_tracks) != query_count:
        raise PlanApprovalError("query_tracks must assign every primary query index exactly once")
    assignments: list[ApprovedQueryTrack] = []
    for raw in raw_tracks:
        if not isinstance(raw, dict) or set(raw) != {"query_index", "research_track"}:
            raise PlanApprovalError("query_tracks entries have unsupported or missing fields")
        assignments.append(ApprovedQueryTrack(raw["query_index"], raw["research_track"]))
    if not isinstance(raw_minimums, dict) or set(raw_minimums) != set(RESEARCH_TRACKS):
        raise PlanApprovalError("track_candidate_minimums must cover every research track")
    minimums = {track: raw_minimums[track] for track in RESEARCH_TRACKS}
    return tuple(assignments), minimums


def write_approved_flight_plan(run_dir: Path, plan: FlightPlan) -> Path:
    """Persist the reviewed executable plan separately from untrusted LLM drafts."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "flight_plan.json"
    path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

def load_approved_flight_plan(run_dir: Path, mission_id: str) -> FlightPlan:
    """Load only the explicit approved plan for a matching mission."""
    path = run_dir / "flight_plan.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("plan must be an object")
        plan = FlightPlan(
            mission_id=str(payload["mission_id"]),
            subquestions=tuple(str(item) for item in payload["subquestions"]),
            queries=tuple(str(item) for item in payload["queries"]),
            counter_queries=tuple(str(item) for item in payload["counter_queries"]),
            max_rounds=int(payload.get("max_rounds", 3)),
            max_papers=int(payload.get("max_papers", 20)),
            query_tracks=tuple(
                ApprovedQueryTrack(item["query_index"], item["research_track"])
                for item in payload.get("query_tracks", ())
            ),
            track_candidate_minimums=dict(payload.get("track_candidate_minimums", {})),
            artifact_id=str(payload.get("artifact_id", "plan_loaded")),
            created_at=str(payload.get("created_at", "loaded")),
        )
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise PlanApprovalError("run must contain a valid approved flight_plan.json") from error
    if plan.mission_id != mission_id:
        raise PlanApprovalError("approved flight plan does not belong to this mission")
    return plan
