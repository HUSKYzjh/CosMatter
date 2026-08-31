"""Closed, reviewable contracts for every configured fleet facility.

Facility names in fleet YAML are not executable permissions.  This registry
states the only artifact classes a facility may consume or produce, the static
CosMatter descriptors it may be associated with, and its explicit failure and
human-review boundaries.  It intentionally contains no command, URL, prompt,
provider credential, dynamic import, or retry implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .harness_catalog import default_cosmatter_plugin_catalogue
from .models import FacilityType, FleetSpec, FleetType


FACILITY_CONTRACT_SCHEMA_VERSION = "cosmatter.facility-contract/v1"
_ARTIFACT_CLASSES = {
    "mission_brief", "approved_flight_plan", "public_metadata_candidates",
    "screened_candidate_decisions", "authorized_pdf_task", "source_map",
    "material_facts", "accepted_evidence_cards", "condition_matrix",
    "counterevidence_record", "gap_candidates", "validation_plan",
    "report_draft", "workflow_status",
}
_FAILURE_MODES = {
    "invalid_input", "missing_provenance", "missing_human_review",
    "unsafe_access", "provider_unavailable", "incomplete_conditions",
    "insufficient_comparable_evidence", "counterevidence_not_executed",
    "unsupported_validation_scope",
}


class FacilityContractError(ValueError):
    """Raised when a facility contract is incomplete or mismatches a fleet."""


@dataclass(frozen=True)
class FacilityContract:
    """A static schema and boundary declaration, never a facility invocation."""

    facility_type: FacilityType
    fleet_types: tuple[FleetType, ...]
    input_schema: tuple[str, ...]
    output_schema: tuple[str, ...]
    allowed_descriptors: tuple[str, ...]
    failure_modes: tuple[str, ...]
    human_review_required: bool
    execution_boundary: str = "static_contract_only_not_execution_authorization"

    def manifest(self) -> dict[str, object]:
        """Return the safe static surface suitable for a local audit display."""
        return {
            "schema_version": FACILITY_CONTRACT_SCHEMA_VERSION,
            "facility_type": self.facility_type.value,
            "fleet_types": [item.value for item in self.fleet_types],
            "input_schema": list(self.input_schema),
            "output_schema": list(self.output_schema),
            "allowed_descriptors": list(self.allowed_descriptors),
            "failure_modes": list(self.failure_modes),
            "human_review_required": self.human_review_required,
            "execution_boundary": self.execution_boundary,
        }


def _contract(
    facility_type: FacilityType,
    fleet_type: FleetType,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    descriptors: tuple[str, ...],
    failures: tuple[str, ...],
    *,
    human_review: bool,
) -> FacilityContract:
    return FacilityContract(facility_type, (fleet_type,), inputs, outputs, descriptors, failures, human_review)


def facility_contracts() -> tuple[FacilityContract, ...]:
    """Return the sole closed contract catalogue for configured facilities."""
    survey = FleetType.DEEP_SPACE_SURVEY
    patrol = FleetType.EVIDENCE_PATROL
    diagnostics = FleetType.ROUTE_DIAGNOSTICS
    horizon = FleetType.UNCHARTED_SECTOR_EXPLORATION
    validation = FleetType.MISSION_VALIDATION
    contracts = (
        _contract(FacilityType.SECTOR_CARTOGRAPHY, survey, ("mission_brief", "approved_flight_plan"), ("public_metadata_candidates",), ("planning.orchestrate", "literature.metadata_retrieval", "literature.deduplicate_and_rank"), ("invalid_input", "missing_human_review", "provider_unavailable"), human_review=True),
        _contract(FacilityType.TIMELINE_OBSERVATORY, survey, ("workflow_status",), ("workflow_status",), ("workflow.status", "workflow.stage_contract"), ("invalid_input",), human_review=False),
        _contract(FacilityType.CITATION_ARRAY, survey, ("public_metadata_candidates",), ("public_metadata_candidates",), ("bibliography.two_hop_expand",), ("invalid_input", "provider_unavailable"), human_review=True),
        _contract(FacilityType.SOURCE_LOCATOR, patrol, ("authorized_pdf_task",), ("source_map",), ("evidence.source_map",), ("invalid_input", "unsafe_access", "missing_human_review", "missing_provenance"), human_review=True),
        _contract(FacilityType.EVIDENCE_COMPARATOR, patrol, ("source_map", "material_facts"), ("accepted_evidence_cards",), ("evidence.verify",), ("invalid_input", "missing_provenance", "incomplete_conditions", "missing_human_review"), human_review=True),
        _contract(FacilityType.CONDITION_RECORDER, patrol, ("source_map",), ("material_facts",), ("evidence.material_extract",), ("invalid_input", "missing_provenance", "missing_human_review"), human_review=True),
        _contract(FacilityType.TRAJECTORY_OVERLAY, diagnostics, ("accepted_evidence_cards",), ("condition_matrix",), ("knowledge.fuse",), ("invalid_input", "insufficient_comparable_evidence", "incomplete_conditions"), human_review=True),
        _contract(FacilityType.CONDITION_DIFFERENTIAL, diagnostics, ("accepted_evidence_cards", "counterevidence_record"), ("condition_matrix",), ("knowledge.fuse",), ("invalid_input", "insufficient_comparable_evidence", "incomplete_conditions", "counterevidence_not_executed"), human_review=True),
        _contract(FacilityType.COUNTEREVIDENCE_DETECTOR, diagnostics, ("approved_flight_plan", "public_metadata_candidates"), ("counterevidence_record",), ("literature.metadata_retrieval",), ("invalid_input", "missing_human_review", "provider_unavailable"), human_review=True),
        _contract(FacilityType.BLIND_SPOT_SCAN, horizon, ("condition_matrix",), ("gap_candidates",), ("research.gap_candidates",), ("invalid_input", "insufficient_comparable_evidence", "counterevidence_not_executed"), human_review=True),
        _contract(FacilityType.VARIABLE_COMBINATION_SCAN, horizon, ("condition_matrix", "counterevidence_record"), ("gap_candidates",), ("research.gap_candidates",), ("invalid_input", "insufficient_comparable_evidence", "counterevidence_not_executed"), human_review=True),
        _contract(FacilityType.HYPOTHESIS_TRIAGE, horizon, ("gap_candidates",), ("gap_candidates",), ("research.gap_candidates",), ("invalid_input", "missing_human_review"), human_review=True),
        _contract(FacilityType.EXPERIMENT_MISSION_DESIGN, validation, ("gap_candidates",), ("validation_plan",), ("research.gap_candidates",), ("invalid_input", "unsupported_validation_scope", "missing_human_review"), human_review=True),
        _contract(FacilityType.COMPUTATION_MISSION_DESIGN, validation, ("gap_candidates",), ("validation_plan",), ("research.gap_candidates",), ("invalid_input", "unsupported_validation_scope", "missing_human_review"), human_review=True),
        _contract(FacilityType.FALSIFICATION_MONITOR, validation, ("validation_plan", "gap_candidates"), ("validation_plan",), ("research.gap_candidates",), ("invalid_input", "unsupported_validation_scope", "missing_human_review"), human_review=True),
    )
    validate_facility_contracts(contracts)
    return contracts


def validate_facility_contracts(contracts: Iterable[FacilityContract]) -> None:
    """Validate catalogue closure against enums and static plugin descriptors."""
    values = tuple(contracts)
    if {item.facility_type for item in values} != set(FacilityType) or len(values) != len(FacilityType):
        raise FacilityContractError("facility contracts must cover every facility exactly once")
    descriptor_ids = {item.plugin_id for item in default_cosmatter_plugin_catalogue()}
    for contract in values:
        if not contract.fleet_types or len(set(contract.fleet_types)) != len(contract.fleet_types):
            raise FacilityContractError("facility contract fleet coverage is invalid")
        if not contract.input_schema or not contract.output_schema or any(value not in _ARTIFACT_CLASSES for value in (*contract.input_schema, *contract.output_schema)):
            raise FacilityContractError("facility contract artifact schema is invalid")
        if not contract.allowed_descriptors or len(set(contract.allowed_descriptors)) != len(contract.allowed_descriptors) or any(value not in descriptor_ids for value in contract.allowed_descriptors):
            raise FacilityContractError("facility contract descriptor allowlist is invalid")
        if not contract.failure_modes or len(set(contract.failure_modes)) != len(contract.failure_modes) or any(value not in _FAILURE_MODES for value in contract.failure_modes):
            raise FacilityContractError("facility contract failure modes are invalid")
        if contract.execution_boundary != "static_contract_only_not_execution_authorization":
            raise FacilityContractError("facility contract execution boundary is invalid")


def facility_contract(facility_type: FacilityType) -> FacilityContract:
    """Look up one validated contract without creating an execution capability."""
    for item in facility_contracts():
        if item.facility_type is facility_type:
            return item
    raise FacilityContractError("facility contract is unavailable")


def validate_fleet_facility_contracts(specs: Iterable[FleetSpec]) -> None:
    """Ensure every configured facility belongs to, and is covered by, its fleet."""
    by_type = {item.facility_type: item for item in facility_contracts()}
    for spec in specs:
        for facility_type in spec.required_facilities:
            contract = by_type.get(facility_type)
            if contract is None or spec.fleet_type not in contract.fleet_types:
                raise FacilityContractError(f"{spec.fleet_type.value} has no matching contract for {facility_type.value}")
