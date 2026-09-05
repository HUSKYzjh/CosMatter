"""Strict vocabulary and record validation for condition-bound material observations.

The registry is deliberately separate from reviewed ``material_facts``.  It can
hold literature leads before a Source Map exists, but its trust and maturity
rules prevent those leads from being presented as human-checked data.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .unit_normalization import UnitNormalizationError, validate_reported_normalization


CATALOG_SCHEMA_VERSION = "cosmatter.material-indicator-catalog/v1"
CATALOG_SCHEMA_VERSION_V2 = "cosmatter.material-indicator-catalog/v2"
OBSERVATION_SCHEMA_VERSION = "cosmatter.material-observation-set/v1"
SOURCE_MATRIX_SCHEMA_VERSION = "cosmatter.material-source-candidate-matrix/v1"
P0_BFO_CATALOG_ID = "bfo-p0-experimental-indicators/v1"
BFO_CATALOG_ID_V2 = "bfo-experimental-indicators/v2"

QUALIFIER_FIELDS = (
    "sample_form",
    "composition",
    "orientation",
    "substrate",
    "thickness",
    "strain",
    "temperature",
    "frequency",
    "field_protocol",
    "electrode",
    "preparation",
    "measurement_geometry",
)

_CATALOG_FIELDS = {
    "schema_version", "registry_id", "material_scope", "trust_status",
    "qualifier_fields", "indicators",
}
_QUALIFIER_DEFINITION_FIELDS = {"field_id", "display_name_zh", "description_zh"}
_INDICATOR_FIELDS = {
    "indicator_id", "family", "priority", "category", "display_name_zh",
    "quantity_kind", "canonical_unit", "allowed_reported_units",
    "value_shape", "required_qualifiers",
}
_OBSERVATION_SET_FIELDS = {
    "schema_version", "catalog_id", "material_scope", "trust_status", "observations",
}
_OBSERVATION_FIELDS = {
    "observation_id", "indicator_id", "document_id", "normalized_doi",
    "document_version", "category", "reported_value", "reported_lower",
    "reported_upper", "reported_uncertainty", "reported_unit",
    "normalized_value", "normalized_lower", "normalized_upper", "normalized_unit",
    "value_semantics", "measurement_method", "qualifiers", "segment_id", "locator",
    "source_quote_sha256", "source_map_status", "data_status", "conditions_status",
    "maturity_level", "assessment_authority", "limitation",
}
_SOURCE_MATRIX_FIELDS = {
    "schema_version", "catalog_id", "material_scope", "trust_status",
    "provider_probe_summary", "questions",
}
_PROVIDER_PROBE_FIELDS = {
    "provider", "operation", "search_status", "content_status", "probe_scope",
}
_SOURCE_QUESTION_FIELDS = {
    "question_id", "focus_indicator_ids", "comparison_question_zh", "source_candidates",
}
_SOURCE_CANDIDATE_FIELDS = {
    "source_id", "normalized_doi", "title", "year", "role", "independence_group",
    "independence_note", "sample_scope", "method_scope", "reported_lead",
    "claim_boundary", "fulltext_route", "access_status", "evidence_status",
}
_P0_FAMILIES = {"structure_phase", "ferroelectric", "electrical_transport", "phase_transition"}
_EXPANDED_FAMILIES = _P0_FAMILIES | {
    "dielectric_piezoelectric",
    "magnetic",
    "optical_photovoltaic",
    "defect_chemistry",
    "process_reproducibility",
}
_CATALOG_PROFILES = {
    (CATALOG_SCHEMA_VERSION, P0_BFO_CATALOG_ID): (_P0_FAMILIES, {"P0"}),
    (CATALOG_SCHEMA_VERSION_V2, BFO_CATALOG_ID_V2): (
        _EXPANDED_FAMILIES,
        {"P0", "P1", "P2"},
    ),
}
_CATEGORIES = {"structure", "property", "experimental_condition"}
_VALUE_SHAPES = {"numeric", "categorical"}
_SEMANTICS = {
    "exact", "approximate", "range", "lower_bound", "upper_bound",
    "maximum", "minimum", "plus_minus", "categorical",
}
_DOCUMENT_VERSIONS = {
    "publisher_version", "accepted_manuscript", "preprint", "unknown",
    "publisher_open_access_mirror_version_not_human_verified",
}
_MATURITY_LEVELS = {
    "literature_mentioned", "data_supported", "reproducibility_ready",
    "independently_reproduced",
}
_AUTHORITIES = {
    "unreviewed", "human_source_review", "human_data_review",
    "human_reproducibility_review", "independent_reproduction_review",
}
_SAFE_ID = re.compile(r"[a-z0-9][a-z0-9._/-]{0,159}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DOI = re.compile(r"10\.\d{4,9}/\S+\Z", re.IGNORECASE)


class MaterialIndicatorRegistryError(ValueError):
    """Raised when a catalog or observation could blur a scientific boundary."""


def load_material_indicator_catalog(path: Path) -> dict[str, Any]:
    value = _load_json(path, "material indicator catalog")
    validate_material_indicator_catalog(value)
    assert isinstance(value, dict)
    return value


def load_material_observation_set(path: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    value = _load_json(path, "material observation set")
    validate_material_observation_set(value, catalog)
    assert isinstance(value, dict)
    return value


def load_material_source_candidate_matrix(path: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    value = _load_json(path, "material source candidate matrix")
    validate_material_source_candidate_matrix(value, catalog)
    assert isinstance(value, dict)
    return value


def validate_material_indicator_catalog(value: object) -> None:
    if not isinstance(value, dict) or set(value) != _CATALOG_FIELDS:
        raise MaterialIndicatorRegistryError("material indicator catalog fields are invalid")
    profile = _CATALOG_PROFILES.get((value.get("schema_version"), value.get("registry_id")))
    if (
        profile is None
        or value.get("material_scope") != "BiFeO3"
        or value.get("trust_status") != "curated_indicator_vocabulary_not_scientific_evidence"
    ):
        raise MaterialIndicatorRegistryError("material indicator catalog identity is invalid")
    allowed_families, allowed_priorities = profile

    qualifiers = value.get("qualifier_fields")
    if not isinstance(qualifiers, list) or len(qualifiers) != len(QUALIFIER_FIELDS):
        raise MaterialIndicatorRegistryError("material indicator catalog must define exactly twelve qualifiers")
    qualifier_ids: list[str] = []
    for item in qualifiers:
        if not isinstance(item, dict) or set(item) != _QUALIFIER_DEFINITION_FIELDS:
            raise MaterialIndicatorRegistryError("material indicator qualifier definition is invalid")
        if not all(_bounded_text(item.get(key), 300) for key in _QUALIFIER_DEFINITION_FIELDS):
            raise MaterialIndicatorRegistryError("material indicator qualifier text is invalid")
        qualifier_ids.append(item["field_id"])
    if tuple(qualifier_ids) != QUALIFIER_FIELDS:
        raise MaterialIndicatorRegistryError("material indicator qualifier order or identity is invalid")

    indicators = value.get("indicators")
    if not isinstance(indicators, list) or not indicators or len(indicators) > 100:
        raise MaterialIndicatorRegistryError("material indicator definitions are invalid")
    seen: set[str] = set()
    families: set[str] = set()
    priorities: set[str] = set()
    for indicator in indicators:
        if not isinstance(indicator, dict) or set(indicator) != _INDICATOR_FIELDS:
            raise MaterialIndicatorRegistryError("material indicator definition fields are invalid")
        indicator_id = indicator.get("indicator_id")
        if not _safe_id(indicator_id) or indicator_id in seen:
            raise MaterialIndicatorRegistryError("material indicator IDs must be unique safe identifiers")
        family = indicator.get("family")
        if (
            family not in allowed_families
            or indicator.get("priority") not in allowed_priorities
            or indicator.get("category") not in _CATEGORIES
        ):
            raise MaterialIndicatorRegistryError("material indicator family, priority, or category is invalid")
        if not _bounded_text(indicator.get("display_name_zh"), 120) or not _safe_id(indicator.get("quantity_kind")):
            raise MaterialIndicatorRegistryError("material indicator name or quantity kind is invalid")
        canonical_unit = indicator.get("canonical_unit")
        units = indicator.get("allowed_reported_units")
        if canonical_unit is not None and not _bounded_text(canonical_unit, 40):
            raise MaterialIndicatorRegistryError("material indicator canonical unit is invalid")
        if not isinstance(units, list) or not units or len(units) > 12 or not all(unit is None or _bounded_text(unit, 40) for unit in units):
            raise MaterialIndicatorRegistryError("material indicator units are invalid")
        if canonical_unit not in units or indicator.get("value_shape") not in _VALUE_SHAPES:
            raise MaterialIndicatorRegistryError("material indicator canonical unit or value shape is invalid")
        required = indicator.get("required_qualifiers")
        if not isinstance(required, list) or not required or len(required) != len(set(required)) or any(item not in QUALIFIER_FIELDS for item in required):
            raise MaterialIndicatorRegistryError("material indicator required qualifiers are invalid")
        seen.add(indicator_id)
        families.add(family)
        priorities.add(indicator["priority"])
    if families != allowed_families:
        raise MaterialIndicatorRegistryError("material indicator catalog must cover every profile family")
    if priorities != allowed_priorities:
        raise MaterialIndicatorRegistryError("material indicator catalog must cover every profile priority")
    _require_distinct_indicator_semantics(seen)


def validate_material_observation_set(value: object, catalog: dict[str, Any]) -> None:
    validate_material_indicator_catalog(catalog)
    if not isinstance(value, dict) or set(value) != _OBSERVATION_SET_FIELDS:
        raise MaterialIndicatorRegistryError("material observation set fields are invalid")
    trust = value.get("trust_status")
    if (
        value.get("schema_version") != OBSERVATION_SCHEMA_VERSION
        or value.get("catalog_id") != catalog["registry_id"]
        or value.get("material_scope") != catalog["material_scope"]
        or trust not in {
            "candidate_literature_observations_not_human_data_checked",
            "human_reviewed_material_observations_not_scientific_conclusion",
        }
    ):
        raise MaterialIndicatorRegistryError("material observation set identity is invalid")
    observations = value.get("observations")
    if not isinstance(observations, list) or not observations or len(observations) > 500:
        raise MaterialIndicatorRegistryError("material observations are invalid")
    definitions = {item["indicator_id"]: item for item in catalog["indicators"]}
    seen: set[str] = set()
    for observation in observations:
        _validate_observation(observation, definitions, trust)
        observation_id = observation["observation_id"]
        if observation_id in seen:
            raise MaterialIndicatorRegistryError("material observation IDs must be unique")
        seen.add(observation_id)


def validate_material_source_candidate_matrix(value: object, catalog: dict[str, Any]) -> None:
    """Require an independent A/B source pair plus a boundary counterexample."""
    validate_material_indicator_catalog(catalog)
    if not isinstance(value, dict) or set(value) != _SOURCE_MATRIX_FIELDS:
        raise MaterialIndicatorRegistryError("material source candidate matrix fields are invalid")
    if (
        value.get("schema_version") != SOURCE_MATRIX_SCHEMA_VERSION
        or value.get("catalog_id") != catalog["registry_id"]
        or value.get("material_scope") != catalog["material_scope"]
        or value.get("trust_status") != "source_candidates_not_screened_or_source_mapped"
    ):
        raise MaterialIndicatorRegistryError("material source candidate matrix identity is invalid")
    probe = value.get("provider_probe_summary")
    if not isinstance(probe, dict) or set(probe) != _PROVIDER_PROBE_FIELDS:
        raise MaterialIndicatorRegistryError("material source provider probe summary is invalid")
    if (
        probe.get("provider") != "sciverse"
        or probe.get("operation") != "semantic_search_and_bounded_content"
        or probe.get("search_status") not in {"succeeded", "failed_closed"}
        or probe.get("content_status") not in {"succeeded", "failed_closed", "not_attempted"}
        or not _safe_public_text(probe.get("probe_scope"), 240)
    ):
        raise MaterialIndicatorRegistryError("material source provider probe status is invalid")
    questions = value.get("questions")
    if not isinstance(questions, list) or not 1 <= len(questions) <= 50:
        raise MaterialIndicatorRegistryError("material source candidate questions are invalid")
    indicator_ids = {item["indicator_id"] for item in catalog["indicators"]}
    seen_questions: set[str] = set()
    for question in questions:
        if not isinstance(question, dict) or set(question) != _SOURCE_QUESTION_FIELDS:
            raise MaterialIndicatorRegistryError("material source candidate question fields are invalid")
        question_id = question.get("question_id")
        if not _safe_id(question_id) or question_id in seen_questions:
            raise MaterialIndicatorRegistryError("material source candidate question identity is invalid")
        focus = question.get("focus_indicator_ids")
        if not isinstance(focus, list) or not focus or len(focus) > 12 or len(focus) != len(set(focus)) or any(item not in indicator_ids for item in focus):
            raise MaterialIndicatorRegistryError("material source candidate focus indicators are invalid")
        if not _safe_public_text(question.get("comparison_question_zh"), 500):
            raise MaterialIndicatorRegistryError("material source comparison question is invalid")
        _validate_source_candidates(question.get("source_candidates"))
        seen_questions.add(question_id)


def _validate_source_candidates(value: object) -> None:
    if not isinstance(value, list) or not 3 <= len(value) <= 12:
        raise MaterialIndicatorRegistryError("each material question requires at least three source candidates")
    roles: dict[str, list[dict[str, Any]]] = {
        "primary_support": [], "independent_support": [], "boundary_counterexample": [],
    }
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()
    for source in value:
        if not isinstance(source, dict) or set(source) != _SOURCE_CANDIDATE_FIELDS:
            raise MaterialIndicatorRegistryError("material source candidate fields are invalid")
        source_id, doi, role = source.get("source_id"), source.get("normalized_doi"), source.get("role")
        if not _safe_id(source_id) or source_id in seen_ids or not isinstance(doi, str) or not _DOI.fullmatch(doi) or doi.casefold() in seen_dois:
            raise MaterialIndicatorRegistryError("material source candidate identity or DOI is invalid")
        if role not in roles:
            raise MaterialIndicatorRegistryError("material source candidate role is invalid")
        if not isinstance(source.get("year"), int) or isinstance(source.get("year"), bool) or not 1900 <= source["year"] <= 2100:
            raise MaterialIndicatorRegistryError("material source candidate year is invalid")
        if not _safe_id(source.get("independence_group")):
            raise MaterialIndicatorRegistryError("material source independence group is invalid")
        for field, maximum in (
            ("title", 500), ("independence_note", 400), ("sample_scope", 500),
            ("method_scope", 500), ("reported_lead", 600), ("claim_boundary", 600),
        ):
            if not _safe_public_text(source.get(field), maximum):
                raise MaterialIndicatorRegistryError("material source candidate public text is invalid")
        if source.get("fulltext_route") not in {"publisher_open_access", "author_manuscript", "public_repository", "institutional_access_required", "abstract_only"}:
            raise MaterialIndicatorRegistryError("material source candidate full-text route is invalid")
        if source.get("access_status") not in {
            "publicly_retrievable", "private_mineru_review_pool_ready",
            "candidate_route_not_probed", "institutional_access_required",
        }:
            raise MaterialIndicatorRegistryError("material source candidate access status is invalid")
        if source.get("evidence_status") != "metadata_or_abstract_checked_not_source_mapped":
            raise MaterialIndicatorRegistryError("material source candidate cannot claim reviewed evidence")
        roles[role].append(source)
        seen_ids.add(source_id)
        seen_dois.add(doi.casefold())
    if not all(roles.values()):
        raise MaterialIndicatorRegistryError("material source matrix requires support, independent support, and a counterexample")
    primary_groups = {item["independence_group"] for item in roles["primary_support"]}
    independent_groups = {item["independence_group"] for item in roles["independent_support"]}
    if primary_groups & independent_groups:
        raise MaterialIndicatorRegistryError("primary and independent support sources must use distinct independence groups")


def _validate_observation(value: object, definitions: dict[str, dict[str, Any]], trust: str) -> None:
    if not isinstance(value, dict) or set(value) != _OBSERVATION_FIELDS:
        raise MaterialIndicatorRegistryError("material observation fields are invalid")
    if not _safe_id(value.get("observation_id")) or not _bounded_text(value.get("document_id"), 200):
        raise MaterialIndicatorRegistryError("material observation identity is invalid")
    indicator = definitions.get(value.get("indicator_id"))
    if indicator is None or value.get("category") != indicator["category"]:
        raise MaterialIndicatorRegistryError("material observation indicator or category is invalid")
    doi = value.get("normalized_doi")
    if doi is not None and (not isinstance(doi, str) or not _DOI.fullmatch(doi)):
        raise MaterialIndicatorRegistryError("material observation DOI is invalid")
    if value.get("document_version") not in _DOCUMENT_VERSIONS:
        raise MaterialIndicatorRegistryError("material observation document version is invalid")
    semantics = value.get("value_semantics")
    if semantics not in _SEMANTICS or not _bounded_text(value.get("measurement_method"), 160):
        raise MaterialIndicatorRegistryError("material observation semantics or method is invalid")
    unit = value.get("reported_unit")
    normalized_unit = value.get("normalized_unit")
    if unit not in indicator["allowed_reported_units"] or normalized_unit not in {None, indicator["canonical_unit"]}:
        raise MaterialIndicatorRegistryError("material observation unit is not allowed by its indicator")
    _validate_value_shape(value, indicator["value_shape"], semantics)
    _validate_normalized_values(value)
    qualifiers = value.get("qualifiers")
    if not isinstance(qualifiers, dict) or tuple(qualifiers) != QUALIFIER_FIELDS:
        raise MaterialIndicatorRegistryError("material observation must contain the twelve ordered qualifier fields")
    if any(not _scalar(item) for item in qualifiers.values()):
        raise MaterialIndicatorRegistryError("material observation qualifiers must be bounded scalars or null")
    if not all(qualifiers[item] not in {None, "not_checked"} for item in indicator["required_qualifiers"]) and value.get("conditions_status") == "complete_human_checked":
        raise MaterialIndicatorRegistryError("complete conditions require every indicator-specific qualifier")
    _validate_provenance_and_maturity(value, trust)
    if not _bounded_text(value.get("limitation"), 500):
        raise MaterialIndicatorRegistryError("material observation requires a bounded limitation")


def _validate_value_shape(value: dict[str, Any], shape: str, semantics: str) -> None:
    value_keys = (
        "reported_value", "reported_lower", "reported_upper", "reported_uncertainty",
        "normalized_value", "normalized_lower", "normalized_upper",
    )
    if any(not _scalar(value.get(key)) for key in value_keys):
        raise MaterialIndicatorRegistryError("material observation values must be finite scalars or null")
    if shape == "categorical":
        if semantics != "categorical" or not _bounded_text(value.get("reported_value"), 200):
            raise MaterialIndicatorRegistryError("categorical material observations require a text value")
        if any(value.get(key) is not None for key in value_keys[1:]):
            raise MaterialIndicatorRegistryError("categorical material observations cannot contain numeric bounds")
        return
    numeric_fields = {key: value.get(key) for key in value_keys}
    if any(item is not None and not _number(item) for item in numeric_fields.values()):
        raise MaterialIndicatorRegistryError("numeric material observations require numeric values")
    if semantics == "range":
        lower, upper = value.get("reported_lower"), value.get("reported_upper")
        if not _number(lower) or not _number(upper) or float(lower) > float(upper):
            raise MaterialIndicatorRegistryError("range observations require ordered reported bounds")
    elif semantics == "plus_minus":
        if not _number(value.get("reported_value")) or not _number(value.get("reported_uncertainty")) or float(value["reported_uncertainty"]) < 0:
            raise MaterialIndicatorRegistryError("plus-minus observations require a value and nonnegative uncertainty")
    elif semantics in {"lower_bound", "upper_bound", "exact", "approximate", "maximum", "minimum"} and not _number(value.get("reported_value")):
        raise MaterialIndicatorRegistryError("numeric observation semantics require a reported value")


def _validate_normalized_values(value: dict[str, Any]) -> None:
    pairs = (
        ("reported_value", "normalized_value"),
        ("reported_lower", "normalized_lower"),
        ("reported_upper", "normalized_upper"),
    )
    for reported_key, normalized_key in pairs:
        reported, normalized = value.get(reported_key), value.get(normalized_key)
        if normalized is not None and reported is None:
            raise MaterialIndicatorRegistryError("normalized observation values require matching reported values")
        if _number(reported) and _number(normalized):
            try:
                validate_reported_normalization(
                    reported, value.get("reported_unit"), normalized, value.get("normalized_unit")
                )
            except UnitNormalizationError as error:
                raise MaterialIndicatorRegistryError(str(error)) from error
    normalized_lower, normalized_upper = value.get("normalized_lower"), value.get("normalized_upper")
    if _number(normalized_lower) and _number(normalized_upper) and float(normalized_lower) > float(normalized_upper):
        raise MaterialIndicatorRegistryError("normalized observation bounds must be ordered")


def _validate_provenance_and_maturity(value: dict[str, Any], trust: str) -> None:
    source_status = value.get("source_map_status")
    data_status = value.get("data_status")
    condition_status = value.get("conditions_status")
    maturity = value.get("maturity_level")
    authority = value.get("assessment_authority")
    if source_status not in {"none", "human_reviewed"} or data_status not in {"not_checked", "numeric_or_figure_data_human_checked"} or condition_status not in {"not_checked", "partial", "complete_human_checked"}:
        raise MaterialIndicatorRegistryError("material observation review status is invalid")
    if maturity not in _MATURITY_LEVELS or authority not in _AUTHORITIES:
        raise MaterialIndicatorRegistryError("material observation maturity or authority is invalid")
    bindings = (value.get("segment_id"), value.get("locator"), value.get("source_quote_sha256"))
    if source_status == "none":
        if any(item is not None for item in bindings):
            raise MaterialIndicatorRegistryError("unmapped observations cannot claim Source Map bindings")
    elif not (_bounded_text(bindings[0], 120) and _bounded_text(bindings[1], 240) and isinstance(bindings[2], str) and _SHA256.fullmatch(bindings[2])):
        raise MaterialIndicatorRegistryError("human-reviewed observations require an exact Source Map binding")

    if trust == "candidate_literature_observations_not_human_data_checked":
        if maturity != "literature_mentioned" or authority != "unreviewed" or source_status != "none" or data_status != "not_checked" or condition_status == "complete_human_checked":
            raise MaterialIndicatorRegistryError("candidate observations cannot claim human review or promoted maturity")
    elif authority == "unreviewed":
        raise MaterialIndicatorRegistryError("human-reviewed observation sets cannot contain unreviewed observations")

    if maturity != "literature_mentioned" and (
        authority not in {"human_data_review", "human_reproducibility_review", "independent_reproduction_review"}
        or source_status != "human_reviewed"
        or data_status != "numeric_or_figure_data_human_checked"
        or condition_status != "complete_human_checked"
    ):
        raise MaterialIndicatorRegistryError("promoted observations require human-checked data, conditions, and Source Map")


def _require_distinct_indicator_semantics(indicator_ids: set[str]) -> None:
    required = {
        "spontaneous_polarization_ps", "remanent_polarization_pr",
        "switched_polarization_2pr", "coercive_field_ec", "coercive_field_2ec",
    }
    if not required.issubset(indicator_ids):
        raise MaterialIndicatorRegistryError("P0 catalog must keep Ps/Pr/2Pr and Ec/2Ec as distinct indicators")


def _load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise MaterialIndicatorRegistryError(f"{label} is unavailable") from error
    except json.JSONDecodeError as error:
        raise MaterialIndicatorRegistryError(f"{label} is not valid JSON") from error


def _safe_id(value: object) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID.fullmatch(value))


def _bounded_text(value: object, maximum: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _safe_public_text(value: object, maximum: int) -> bool:
    if not _bounded_text(value, maximum):
        return False
    assert isinstance(value, str)
    lowered = value.casefold()
    return not any(marker in lowered for marker in (
        "https://", "http://", "file://", "api_key", "authorization", "bearer ",
        "c:\\users\\", "/home/",
    ))


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _scalar(value: object) -> bool:
    return value is None or isinstance(value, str) and bool(value.strip()) and len(value) <= 500 or _number(value)
