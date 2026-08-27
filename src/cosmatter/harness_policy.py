"""Deny-by-default mission authorization for static CosMatter plugins.

The policy layer decides whether an already registered plugin *may be invoked*.
It never reads secrets, invokes providers, persists a grant, or treats an LLM
output as accepted evidence.  A caller records approved grants in the mission
audit ledger before dispatching an external adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .harness_catalog import CosMatterHarnessCatalogue, HarnessCatalogueError


class HarnessPolicyError(ValueError):
    """Raised when an authorization receipt is structurally unsafe."""


@dataclass(frozen=True)
class MissionAuthorization:
    mission_id: str
    plugin_id: str
    authorizations: tuple[str, ...]
    actor: str = "human_researcher"

    def as_audit_payload(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "plugin_id": self.plugin_id,
            "authorizations": list(self.authorizations),
            "actor": self.actor,
            "trust_status": "authorization_receipt_not_execution_receipt",
        }


def evaluate_mission_authorization(
    catalogue: CosMatterHarnessCatalogue,
    authorization: MissionAuthorization,
) -> dict[str, Any]:
    """Return a non-executing allow/block decision for one mission plugin call."""
    if not isinstance(authorization.mission_id, str) or not authorization.mission_id.strip():
        raise HarnessPolicyError("mission_id is required")
    if not isinstance(authorization.actor, str) or not authorization.actor.strip():
        raise HarnessPolicyError("actor is required")
    if not all(isinstance(item, str) and item.strip() for item in authorization.authorizations):
        raise HarnessPolicyError("authorizations must be non-empty strings")
    try:
        plugin = catalogue.describe(authorization.plugin_id)
    except HarnessCatalogueError as error:
        raise HarnessPolicyError("plugin is not registered") from error

    missing = sorted(set(plugin["required_authorizations"]) - set(authorization.authorizations))
    if plugin["automation_class"] == "human_gate":
        return _decision(plugin, authorization, False, "human_review_required", missing)
    if plugin["automation_class"] == "external_authorized" and missing:
        return _decision(plugin, authorization, False, "missing_explicit_authorization", missing)
    return _decision(plugin, authorization, True, "permitted_to_dispatch_not_yet_executed", missing)


def _decision(
    plugin: dict[str, Any], authorization: MissionAuthorization, permitted: bool, reason: str, missing: list[str]) -> dict[str, Any]:
    return {
        "mission_id": authorization.mission_id,
        "plugin_id": plugin["plugin_id"],
        "permitted": permitted,
        "reason": reason,
        "missing_authorizations": missing,
        "requires_human_review": plugin["requires_human_review"],
        "next_boundary": (
            "A permitted decision authorizes only the named adapter dispatch. It does not accept EvidenceCards, "
            "produce a scientific conclusion, or authorize any calculation, scheduler, training or inference job."
        ),
    }
