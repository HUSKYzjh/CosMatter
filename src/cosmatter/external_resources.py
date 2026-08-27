"""Validation for submission-safe external-resource disclosure records.

This artifact describes provenance and terms of services actually used in a
run.  It is deliberately not a provider receipt, a credential store, or a
claim that a resource supplied scientifically validated evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
TRUST_STATUS = "human_completed_external_resource_disclosure_not_execution_evidence"
_CATEGORIES = {"database", "API", "model", "parser", "software"}
_ACCESS_METHODS = {"API", "local authorized corpus", "public download"}
_FIELDS = {"schema_version", "trust_status", "resources", "reviewer", "review_date"}
_RESOURCE_FIELDS = {
    "name", "category", "purpose", "access_method", "version_or_access_date",
    "license_or_terms", "redistribution_boundary", "used_in_final_result",
}
_FORBIDDEN_MARKERS = ("api_key", "authorization", "bearer ", "cookie:", "c:\\users\\", "/home/")


class ExternalResourceDisclosureError(ValueError):
    """Raised when a disclosure is incomplete or appears to contain private data."""


def load_external_resource_disclosure(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExternalResourceDisclosureError(f"cannot read external resource disclosure: {error}") from error
    return validate_external_resource_disclosure(payload)


def validate_external_resource_disclosure(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise ExternalResourceDisclosureError("external resource disclosure has unsupported or missing fields")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("trust_status") != TRUST_STATUS:
        raise ExternalResourceDisclosureError("external resource disclosure schema or trust status is invalid")
    for key in ("reviewer", "review_date"):
        if not isinstance(payload.get(key), str) or not payload[key].strip() or len(payload[key]) > 160:
            raise ExternalResourceDisclosureError(f"external resource disclosure {key} is invalid")
    resources = payload.get("resources")
    if not isinstance(resources, list) or not resources:
        raise ExternalResourceDisclosureError("external resource disclosure requires at least one resource")
    seen: set[str] = set()
    for resource in resources:
        if not isinstance(resource, dict) or set(resource) != _RESOURCE_FIELDS:
            raise ExternalResourceDisclosureError("external resource entry has unsupported or missing fields")
        name = resource.get("name")
        if not isinstance(name, str) or not name.strip() or name.casefold() in seen:
            raise ExternalResourceDisclosureError("external resource names must be non-empty and unique")
        seen.add(name.casefold())
        if resource.get("category") not in _CATEGORIES or resource.get("access_method") not in _ACCESS_METHODS:
            raise ExternalResourceDisclosureError("external resource category or access method is invalid")
        if not isinstance(resource.get("used_in_final_result"), bool):
            raise ExternalResourceDisclosureError("external resource final-result flag must be boolean")
        for key in ("purpose", "version_or_access_date", "license_or_terms", "redistribution_boundary"):
            value = resource.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ExternalResourceDisclosureError(f"external resource {key} is invalid")
        _reject_private_content(resource)
    return payload


def write_external_resource_disclosure(run_dir: Path, payload: object) -> Path:
    reviewed = validate_external_resource_disclosure(payload)
    path = run_dir / "external_resource_disclosure.json"
    path.write_text(json.dumps(reviewed, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _reject_private_content(resource: dict[str, Any]) -> None:
    text = "\n".join(str(value) for value in resource.values()).casefold()
    if any(marker in text for marker in _FORBIDDEN_MARKERS):
        raise ExternalResourceDisclosureError("external resource disclosure must not contain credentials or private paths")
