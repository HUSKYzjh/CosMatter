"""Durable, secret-safe idempotency records for external DSH tool calls.

The record deliberately stores only hashes of the DSH call identity and request
shape.  It never stores a provider request, token, URL, paper text, or a
provider response.  A repeated DSH call therefore cannot silently submit a
second remote request after the first call may already have crossed the
provider boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .models import utc_now


DISPATCH_LEDGER_FILENAME = "external_dispatch_ledger.json"
DISPATCH_LEDGER_SCHEMA_VERSION = "1.0"
_CALL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{5,255}$")
_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_.-]{2,119}$")
# This ordered public vocabulary is also consumed by count-only telemetry.  It
# must be the single backend source of truth for ledger operation names.
EXTERNAL_DISPATCH_OPERATIONS = (
    "deepseek_plan_draft", "deepseek_graph_plan_draft", "metadata_query",
    "citation_expansion", "mineru_submit", "mineru_poll",
)
_OPERATIONS = frozenset(EXTERNAL_DISPATCH_OPERATIONS)
_STATES = frozenset({"dispatched", "completed", "unknown"})
_ENTRY_FIELDS = {"call_id_sha256", "plugin_id", "operation", "request_sha256", "state", "provider_receipt_ids", "recorded_at", "updated_at"}


class ExternalDispatchError(ValueError):
    """Raised when a dispatch would duplicate, overstate, or corrupt an external action."""


def begin_external_dispatch(
    run_dir: Path,
    *,
    mission_id: str,
    dsh_call_id: str,
    plugin_id: str,
    operation: str,
    request_shape: object,
) -> dict[str, Any]:
    """Persist ``dispatched`` before provider I/O, or return the same completed call.

    Unknown outcomes intentionally raise instead of retrying.  A caller must
    inspect provider status where possible, or issue a new explicitly
    authorised DSH call after review.
    """
    _validate_identity(mission_id, dsh_call_id, plugin_id, operation)
    ledger = _load_ledger(run_dir, mission_id)
    call_digest = _sha256(dsh_call_id)
    request_digest = _canonical_digest(request_shape)
    existing = next((entry for entry in ledger["entries"] if entry["call_id_sha256"] == call_digest), None)
    if existing is not None:
        if (existing["plugin_id"], existing["operation"], existing["request_sha256"]) != (plugin_id, operation, request_digest):
            raise ExternalDispatchError("DSH call identity was reused with a different external request")
        if existing["state"] == "completed":
            return {**existing, "duplicate": True}
        if existing["state"] == "unknown":
            raise ExternalDispatchError("external dispatch outcome is unknown; inspect provider status or create a new explicit call")
        raise ExternalDispatchError("external dispatch is already recorded without a terminal outcome")
    entry = {
        "call_id_sha256": call_digest,
        "plugin_id": plugin_id,
        "operation": operation,
        "request_sha256": request_digest,
        "state": "dispatched",
        "provider_receipt_ids": [],
        "recorded_at": utc_now(),
        "updated_at": utc_now(),
    }
    ledger["entries"].append(entry)
    _write_ledger(run_dir, ledger)
    return {**entry, "duplicate": False}


def complete_external_dispatch(
    run_dir: Path,
    *,
    mission_id: str,
    dsh_call_id: str,
    provider_receipt_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Mark exactly the previously persisted dispatch complete after durable output."""
    ledger, entry = _entry_for_call(run_dir, mission_id, dsh_call_id)
    if entry["state"] != "dispatched":
        raise ExternalDispatchError("external dispatch cannot be completed from its current state")
    if len(set(provider_receipt_ids)) != len(provider_receipt_ids) or any(not isinstance(value, str) or not value.startswith("receipt_") for value in provider_receipt_ids):
        raise ExternalDispatchError("provider receipt identifiers are invalid")
    entry["state"] = "completed"
    entry["provider_receipt_ids"] = list(provider_receipt_ids)
    entry["updated_at"] = utc_now()
    _write_ledger(run_dir, ledger)
    return dict(entry)


def mark_external_dispatch_unknown(run_dir: Path, *, mission_id: str, dsh_call_id: str) -> dict[str, Any]:
    """Record a provider-boundary failure without guessing whether it took effect."""
    ledger, entry = _entry_for_call(run_dir, mission_id, dsh_call_id)
    if entry["state"] == "completed":
        raise ExternalDispatchError("completed external dispatch cannot become unknown")
    entry["state"] = "unknown"
    entry["updated_at"] = utc_now()
    _write_ledger(run_dir, ledger)
    return dict(entry)


def external_dispatch_record(run_dir: Path, *, mission_id: str, dsh_call_id: str) -> dict[str, Any] | None:
    """Return the hash-only record for an exact call, without exposing its ID."""
    ledger = _load_ledger(run_dir, mission_id)
    call_digest = _call_digest(dsh_call_id)
    for entry in ledger["entries"]:
        if entry["call_id_sha256"] == call_digest:
            return dict(entry)
    return None


def load_external_dispatch_ledger(run_dir: Path, mission_id: str) -> dict[str, Any]:
    """Load the validated hash-only ledger for a read-only audit companion."""
    return _load_ledger(run_dir, mission_id)


def _entry_for_call(run_dir: Path, mission_id: str, dsh_call_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger = _load_ledger(run_dir, mission_id)
    call_digest = _call_digest(dsh_call_id)
    for entry in ledger["entries"]:
        if entry["call_id_sha256"] == call_digest:
            return ledger, entry
    raise ExternalDispatchError("external dispatch record does not exist")


def _call_digest(dsh_call_id: str) -> str:
    if not isinstance(dsh_call_id, str) or not _CALL_ID.fullmatch(dsh_call_id):
        raise ExternalDispatchError("DSH call identity is invalid")
    return _sha256(dsh_call_id)


def _validate_identity(mission_id: str, dsh_call_id: str, plugin_id: str, operation: str) -> None:
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise ExternalDispatchError("mission identity is invalid")
    _call_digest(dsh_call_id)
    if not isinstance(plugin_id, str) or not _PLUGIN_ID.fullmatch(plugin_id) or operation not in _OPERATIONS:
        raise ExternalDispatchError("external dispatch identity is invalid")


def _load_ledger(run_dir: Path, mission_id: str) -> dict[str, Any]:
    path = run_dir / DISPATCH_LEDGER_FILENAME
    if not path.exists():
        return {"schema_version": DISPATCH_LEDGER_SCHEMA_VERSION, "mission_id": mission_id, "entries": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExternalDispatchError("external dispatch ledger is invalid") from error
    _validate_ledger(payload, mission_id)
    return payload


def _write_ledger(run_dir: Path, payload: dict[str, Any]) -> Path:
    _validate_ledger(payload, payload["mission_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / DISPATCH_LEDGER_FILENAME
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _validate_ledger(payload: object, mission_id: str) -> None:
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "mission_id", "entries"}:
        raise ExternalDispatchError("external dispatch ledger fields are invalid")
    if payload.get("schema_version") != DISPATCH_LEDGER_SCHEMA_VERSION or payload.get("mission_id") != mission_id or not isinstance(payload.get("entries"), list):
        raise ExternalDispatchError("external dispatch ledger identity is invalid")
    seen: set[str] = set()
    for entry in payload["entries"]:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS:
            raise ExternalDispatchError("external dispatch ledger entry fields are invalid")
        call_digest = entry.get("call_id_sha256")
        if not _is_sha256(call_digest) or call_digest in seen:
            raise ExternalDispatchError("external dispatch call identity is invalid")
        seen.add(call_digest)
        if not isinstance(entry.get("plugin_id"), str) or not _PLUGIN_ID.fullmatch(entry["plugin_id"]) or entry.get("operation") not in _OPERATIONS or not _is_sha256(entry.get("request_sha256")) or entry.get("state") not in _STATES:
            raise ExternalDispatchError("external dispatch ledger entry is invalid")
        receipt_ids = entry.get("provider_receipt_ids")
        if not isinstance(receipt_ids, list) or len(set(receipt_ids)) != len(receipt_ids) or any(not isinstance(value, str) or not value.startswith("receipt_") for value in receipt_ids):
            raise ExternalDispatchError("external dispatch receipt links are invalid")
        if entry["state"] == "completed" and entry["operation"] in {"metadata_query", "mineru_submit", "mineru_poll"} and not receipt_ids:
            raise ExternalDispatchError("completed provider dispatch requires receipt links")
        if not all(isinstance(entry.get(field), str) and entry[field].strip() for field in ("recorded_at", "updated_at")):
            raise ExternalDispatchError("external dispatch timestamps are invalid")


def _canonical_digest(value: object) -> str:
    try:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ExternalDispatchError("external dispatch request shape is invalid") from error
    if len(rendered) > 16_000:
        raise ExternalDispatchError("external dispatch request shape is too large")
    return _sha256(rendered)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-f0-9]{64}", value))
