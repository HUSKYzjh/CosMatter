"""Loopback-only application service for the interactive CosMatter workbench.

Provider tokens are loaded only inside this backend.  Browser clients receive
allowlisted task data and never receive a token, provider request object, raw
retrieval payload, audit event payload, or arbitrary file path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .audit import AuditPathError, FlightRecorder, safe_run_id
from .config import AGENT_ROOT, Settings
from .deepseek import DeepSeekAdapter, DeepSeekConfigurationError, DeepSeekRequestError
from .dispatch import DispatchError, MissionDispatcher
from .metadata_search import MetadataSearchAdapter, MetadataSearchConfigurationError, MetadataSearchRequestError
from .models import MissionBrief, MissionState
from .planning import (
    PlanApprovalError,
    approved_flight_plan_from_payload,
    load_approved_flight_plan,
    research_planning_prompts,
    write_approved_flight_plan,
    write_untrusted_plan_draft,
)
from .retrieval import RetrievalArtifactError, candidates_from_sciverse, write_candidate_artifact
from .run_control import RunControlError, require_active_run
from .sciverse import SciverseAdapter, SciverseConfigurationError, SciverseRequestError
from .ui_export import UiExportError, _load_object, _mission_from_payload, export_run_to_ui


class LocalApiError(ValueError):
    """A safe API error that is appropriate to return to a local user."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _runs_dir() -> Path:
    return AGENT_ROOT / "runs"


_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _api_safe_run_id(value: str) -> str:
    candidate = safe_run_id(value)
    if not _RUN_ID_PATTERN.fullmatch(candidate):
        raise LocalApiError("run_id must use letters, numbers, underscores, or hyphens")
    return candidate


def _bounded_text(payload: dict[str, Any], field: str, maximum: int = 3_000) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise LocalApiError(f"{field} must be a nonempty string of at most {maximum} characters")
    return value.strip()


@dataclass
class LocalMissionApi:
    """Application operations shared by a local-only HTTP handler and tests."""

    runs_dir: Path
    settings_loader: Callable[[], Settings] = Settings.load

    @classmethod
    def from_project(cls) -> "LocalMissionApi":
        return cls(_runs_dir())

    def status(self) -> dict[str, object]:
        """Return configuration presence flags only, never secret values."""
        status = self.settings_loader().status()
        return {
            "api_mode": "loopback_only",
            "providers": {
                "deepseek": bool(status["deepseek_configured"]),
                "sciverse": bool(status["sciverse_configured"]),
                "mineru": bool(status["mineru_configured"]),
                "openalex": bool(status["openalex_configured"]),
                "crossref": True,
                "crossref_polite_contact": bool(status["crossref_polite_contact_configured"]),
            },
        }

    def create_mission(self, payload: object) -> dict[str, object]:
        body = _object_payload(payload)
        try:
            brief = MissionBrief(
                question=_bounded_text(body, "question"),
                material=_bounded_text(body, "material", 300),
                property_name=_bounded_text(body, "property", 300),
                scope=_bounded_text(body, "scope", 1_000),
            )
            requested_run_id = body.get("run_id")
            if requested_run_id is not None and not isinstance(requested_run_id, str):
                raise LocalApiError("run_id must be a string")
            run_id = _api_safe_run_id(requested_run_id or brief.mission_id.replace("mission_", "run_"))
            run_dir = self.runs_dir / run_id
            if run_dir.exists():
                raise LocalApiError("run_id already exists; choose another identifier", 409)
            recorder = FlightRecorder(self.runs_dir, run_id)
            (recorder.run_dir / "mission.json").write_text(
                json.dumps(brief.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            recorder.record(event_type="mission_created", actor="mission_control", state=MissionState.INTAKE, payload=brief.to_dict())
            assignment = MissionDispatcher.from_project().assign(brief, body.get("mission_type") if isinstance(body.get("mission_type"), str) else None)
            (recorder.run_dir / "fleet_assignment.json").write_text(
                json.dumps(assignment.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            recorder.record(
                event_type="fleet_assigned", actor="mission_dispatch", state=MissionState.INTAKE, payload=assignment.to_dict()
            )
        except (ValueError, AuditPathError, DispatchError) as error:
            if isinstance(error, LocalApiError):
                raise
            raise LocalApiError(str(error)) from error
        return {
            "run_id": run_id,
            "mission_id": brief.mission_id,
            "fleet_type": assignment.fleet_type.value,
            "mission_type": assignment.mission_type,
            "state": MissionState.INTAKE.value,
        }

    def draft_plan(self, run_id: str) -> dict[str, object]:
        run_dir, mission = self._active_mission(run_id)
        try:
            system_prompt, user_prompt = research_planning_prompts(mission)
            completion = DeepSeekAdapter(self.settings_loader()).draft(system_prompt=system_prompt, user_prompt=user_prompt)
            write_untrusted_plan_draft(run_dir, completion)
        except (DeepSeekConfigurationError, DeepSeekRequestError, ValueError) as error:
            raise LocalApiError(str(error), 503) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="research_plan_drafted",
            actor="research_planning",
            state=MissionState.PLAN,
            payload={"model": completion.model, "request_id": completion.request_id, "trust_status": "untrusted_draft"},
        )
        return {"run_id": run_id, "trust_status": "untrusted_draft", "content": completion.content}

    def approve_plan(self, run_id: str, payload: object) -> dict[str, object]:
        run_dir, mission = self._active_mission(run_id)
        try:
            plan = approved_flight_plan_from_payload(mission, _object_payload(payload))
            write_approved_flight_plan(run_dir, plan)
        except PlanApprovalError as error:
            raise LocalApiError(str(error)) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="flight_plan_approved",
            actor="human_plan_review",
            state=MissionState.PLAN,
            payload={"plan_id": plan.artifact_id, "query_count": len(plan.queries), "counter_query_count": len(plan.counter_queries)},
        )
        return {"run_id": run_id, "plan_id": plan.artifact_id, "queries": list(plan.queries), "counter_queries": list(plan.counter_queries)}

    def execute_plan_query(self, run_id: str, payload: object) -> dict[str, object]:
        """Run an approved query against explicitly selected metadata sources.

        External activity is possible only after plan approval and this endpoint
        is invoked. Every provider result is metadata-only candidate data, not
        evidence or full text.
        """
        run_dir, mission = self._active_mission(run_id)
        body = _object_payload(payload)
        try:
            plan = load_approved_flight_plan(run_dir, mission.mission_id)
            index = body.get("query_index")
            counter = body.get("counter", False)
            sources = _selected_sources(body.get("sources"))
            if not isinstance(index, int) or isinstance(index, bool):
                raise LocalApiError("query_index must be an integer")
            if not isinstance(counter, bool):
                raise LocalApiError("counter must be a boolean")
            approved_queries = plan.counter_queries if counter else plan.queries
            if not 0 <= index < len(approved_queries):
                raise LocalApiError("query_index is outside the approved query list")
            query = approved_queries[index]
            settings = self.settings_loader()
            source_counts: dict[str, int] = {}
            candidates = []
            if "sciverse" in sources:
                response = SciverseAdapter(settings).agentic_search(query, top_k=plan.max_papers)
                current = candidates_from_sciverse(response.payload, query, plan.max_papers)
                source_counts["Sciverse"] = len(current)
                candidates.extend(current)
            metadata = MetadataSearchAdapter(settings)
            if "openalex" in sources:
                current = metadata.search_openalex(query, top_k=min(plan.max_papers, 20))
                source_counts["OpenAlex"] = len(current)
                candidates.extend(current)
            if "crossref" in sources:
                current = metadata.search_crossref(query, top_k=min(plan.max_papers, 20))
                source_counts["Crossref"] = len(current)
                candidates.extend(current)
            write_candidate_artifact(run_dir, query, tuple(candidates))
        except (PlanApprovalError, RetrievalArtifactError, SciverseConfigurationError, SciverseRequestError, MetadataSearchConfigurationError, MetadataSearchRequestError, ValueError) as error:
            if isinstance(error, LocalApiError):
                raise
            raise LocalApiError(str(error), 503) from error
        FlightRecorder(self.runs_dir, run_id).record(
            event_type="approved_plan_query_executed",
            actor="search_selection",
            state=MissionState.RETRIEVE,
            payload={"plan_id": plan.artifact_id, "query_kind": "counter" if counter else "primary", "query_index": index, "sources": list(sources), "candidate_count": len(candidates), "source_counts": source_counts},
        )
        return {"run_id": run_id, "query_kind": "counter" if counter else "primary", "query_index": index, "sources": list(sources), "source_counts": source_counts, "candidate_count": len(candidates), "candidates": [candidate.to_dict() for candidate in candidates]}
    def ui_bundle(self, run_id: str) -> bytes:
        try:
            destination = export_run_to_ui(self.runs_dir, _api_safe_run_id(run_id))
            return destination.read_bytes()
        except (AuditPathError, UiExportError, OSError) as error:
            raise LocalApiError(str(error), 404) from error

    def _active_mission(self, run_id: str) -> tuple[Path, MissionBrief]:
        try:
            run_id = _api_safe_run_id(run_id)
            run_dir = self.runs_dir / run_id
            mission = _mission_from_payload(_load_object(run_dir / "mission.json", "mission artifact"))
            require_active_run(run_dir, mission.mission_id)
            return run_dir, mission
        except (AuditPathError, UiExportError, RunControlError) as error:
            raise LocalApiError(str(error), 404) from error


def _selected_sources(value: object) -> tuple[str, ...]:
    allowed = {"sciverse", "openalex", "crossref"}
    if value is None:
        return ("sciverse",)
    if not isinstance(value, list) or not value or len(value) > len(allowed):
        raise LocalApiError("sources must be a nonempty list of approved providers")
    selected: list[str] = []
    for item in value:
        if not isinstance(item, str) or item not in allowed or item in selected:
            raise LocalApiError("sources contains an unsupported provider")
        selected.append(item)
    return tuple(selected)

def _object_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LocalApiError("request body must be a JSON object")
    return payload
