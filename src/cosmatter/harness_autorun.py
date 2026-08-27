"""Authorized automatic-mission bridge for the existing local API.

The bridge is deliberately small: it evaluates the static plugin policy before
calling the legacy automatic mission operation, then adds an audit record to
the run created by that operation.  It does not inspect configuration,
providers, private documents or model responses itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .audit import FlightRecorder
from .harness_catalog import CosMatterHarnessCatalogue
from .harness_policy import MissionAuthorization, evaluate_mission_authorization
from .models import MissionBrief, MissionState


class HarnessAutoRunError(ValueError):
    """Raised when the automatic route has not received a safe authorization."""


class AutomaticMissionPort(Protocol):
    """The minimal legacy API surface consumed by this bridge."""

    runs_dir: Any

    def auto_mission(self, payload: object) -> dict[str, object]: ...


@dataclass(frozen=True)
class AutoMissionAuthorizationPlan:
    mission_id: str
    decisions: tuple[dict[str, Any], ...]

    def audit_payload(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "plugin_authorization_decisions": list(self.decisions),
            "trust_status": "authorization_checked_before_automatic_dispatch",
        }


def plan_automatic_mission_authorization(payload: object) -> AutoMissionAuthorizationPlan:
    """Validate one-time consent and produce non-executing dispatch decisions."""
    if not isinstance(payload, dict) or payload.get("consent") is not True:
        raise HarnessAutoRunError("automatic execution requires explicit one-time consent")
    try:
        brief = MissionBrief(
            question=_required_text(payload, "question", 3_000),
            material=_required_text(payload, "material", 300),
            property_name=_required_text(payload, "property", 300),
            scope=_required_text(payload, "scope", 1_000),
        )
    except (TypeError, ValueError) as error:
        raise HarnessAutoRunError("automatic mission boundary is invalid") from error
    catalogue = CosMatterHarnessCatalogue()
    decisions = (
        evaluate_mission_authorization(
            catalogue,
            MissionAuthorization(
                brief.mission_id,
                "literature.question_candidates",
                ("mission_scoped_egress_consent", "deepseek_request_consent"),
            ),
        ),
        evaluate_mission_authorization(
            catalogue,
            MissionAuthorization(
                brief.mission_id,
                "literature.metadata_retrieval",
                ("mission_scoped_egress_consent", "metadata_provider_consent"),
            ),
        ),
    )
    if not all(decision["permitted"] for decision in decisions):
        raise HarnessAutoRunError("automatic mission is blocked by the static plugin policy")
    return AutoMissionAuthorizationPlan(brief.mission_id, decisions)


def run_authorized_automatic_mission(api: AutomaticMissionPort, payload: object) -> dict[str, object]:
    """Policy-check, then dispatch the existing bounded automatic mission.

    This function remains useful while the legacy HTTP routes are gradually
    migrated: callers can opt into the plugin policy without altering the
    current run artifact or UI bundle contracts.
    """
    authorization = plan_automatic_mission_authorization(payload)
    result = api.auto_mission(payload)
    run_id = result.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise HarnessAutoRunError("automatic mission did not return a safe run_id")
    FlightRecorder(api.runs_dir, run_id).record(
        event_type="harness_authorization_checked",
        actor="harness_policy",
        state=MissionState.PLAN,
        payload=authorization.audit_payload(),
    )
    return {**result, "harness_authorization": authorization.audit_payload()}


def _required_text(payload: dict[str, object], field: str, maximum: int) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise HarnessAutoRunError(f"{field} must be a nonempty string within its limit")
    return value.strip()
