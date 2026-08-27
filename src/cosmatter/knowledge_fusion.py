"""Conservative cross-document comparison of reviewed material facts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .material_extraction import MaterialExtractionError

FUSION_SCHEMA_VERSION = "1.0"


class KnowledgeFusionError(ValueError):
    pass


def fuse_reviewed_material_facts(mission_id: str, artifacts: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Group reviewed facts without turning differences into scientific conclusions."""
    if not isinstance(mission_id, str) or not mission_id.strip() or not artifacts:
        raise KnowledgeFusionError("fusion requires a mission and at least one reviewed material-fact artifact")
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for artifact in artifacts:
        if artifact.get("mission_id") != mission_id or artifact.get("trust_status") != "human_reviewed_structured_material_facts_not_scientific_conclusion":
            raise KnowledgeFusionError("material fact artifact does not belong to this reviewed mission")
        document_id = artifact.get("document_id")
        if not isinstance(document_id, str) or not isinstance(artifact.get("facts"), list):
            raise KnowledgeFusionError("material fact artifact is invalid")
        for fact in artifact["facts"]:
            if not isinstance(fact, dict):
                raise KnowledgeFusionError("material fact is invalid")
            category, name = fact.get("category"), fact.get("name")
            unit = fact.get("normalized_unit") if fact.get("normalized_unit") is not None else fact.get("unit")
            value = fact.get("normalized_value") if fact.get("normalized_value") is not None else fact.get("value")
            if not isinstance(category, str) or not isinstance(name, str) or value is None:
                continue
            key = (category, _normalise_name(name), unit if isinstance(unit, str) else "unit_unspecified")
            groups.setdefault(key, []).append({
                "document_id": document_id, "fact_id": fact.get("fact_id"), "segment_id": fact.get("segment_id"), "locator": fact.get("locator"),
                "value": value, "qualifiers": fact.get("qualifiers", {}),
            })
    rows = []
    for index, ((category, name, unit), observations) in enumerate(sorted(groups.items()), 1):
        rows.append({
            "comparison_id": f"comparison_{index:03d}", "category": category, "name": name, "normalized_unit": None if unit == "unit_unspecified" else unit,
            "observations": observations, **_comparison_status(observations),
        })
    if not rows:
        raise KnowledgeFusionError("no comparable material facts with values are available")
    return {"schema_version": FUSION_SCHEMA_VERSION, "mission_id": mission_id, "trust_status": "reviewed_material_fact_comparison_not_scientific_conclusion", "comparisons": rows}


def write_material_fact_fusion(run_dir: Path, artifact: dict[str, Any]) -> Path:
    _validate(artifact, artifact.get("mission_id"))
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "material_fact_fusion.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_material_fact_fusion(path: Path, mission_id: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        artifact = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise KnowledgeFusionError("material_fact_fusion.json is invalid JSON") from error
    _validate(artifact, mission_id)
    return artifact


def _comparison_status(observations: list[dict[str, Any]]) -> dict[str, Any]:
    qualifier_keys = set().union(*(set(item["qualifiers"]) for item in observations))
    differing = sorted(key for key in qualifier_keys if len({json.dumps(item["qualifiers"].get(key), sort_keys=True) for item in observations}) > 1)
    values = {json.dumps(item["value"], sort_keys=True) for item in observations}
    if len(observations) == 1:
        status = "single_observation"
    elif differing:
        status = "not_directly_comparable_differing_qualifiers"
    elif len(values) == 1:
        status = "aligned_under_matching_qualifiers"
    else:
        status = "value_disagreement_under_matching_qualifiers_requires_human_review"
    return {"comparison_status": status, "differing_qualifier_fields": differing}


def _normalise_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _validate(artifact: object, mission_id: object) -> None:
    if not isinstance(mission_id, str) or not isinstance(artifact, dict) or set(artifact) != {"schema_version", "mission_id", "trust_status", "comparisons"} or artifact.get("schema_version") != FUSION_SCHEMA_VERSION or artifact.get("mission_id") != mission_id or artifact.get("trust_status") != "reviewed_material_fact_comparison_not_scientific_conclusion" or not isinstance(artifact.get("comparisons"), list):
        raise KnowledgeFusionError("material fact fusion artifact is invalid")
