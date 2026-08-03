"""Cooperative cancellation and safe run-status summaries.

CosMatter's current provider calls are synchronous and short-lived, so a
cancel request cannot kill an HTTP request already in flight.  Instead it is a
durable local control gate: all later provider submissions must stop before
they leave the process.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import MissionState, utc_now


CONTROL_SCHEMA_VERSION = "1.0"
_CONTROL_FIELDS = {"schema_version", "mission_id", "status", "cancelled_at"}


class RunControlError(ValueError):
    """Raised for invalid or incompatible local cancellation controls."""


def cancel_run(run_dir: Path, mission_id: str) -> Path:
    """Persist an idempotent cancellation marker without retaining a reason."""
    if not mission_id.strip():
        raise RunControlError("mission_id must be nonempty")
    existing = load_run_control(run_dir / "run_control.json", mission_id)
    if existing is not None:
        return run_dir / "run_control.json"
    payload = {
        "schema_version": CONTROL_SCHEMA_VERSION,
        "mission_id": mission_id,
        "status": "cancelled",
        "cancelled_at": utc_now(),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run_control.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_run_control(path: Path, mission_id: str) -> dict[str, str] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RunControlError("run_control.json is invalid JSON") from error
    if not isinstance(payload, dict) or set(payload) != _CONTROL_FIELDS:
        raise RunControlError("run control has unsupported or missing fields")
    if payload.get("schema_version") != CONTROL_SCHEMA_VERSION or payload.get("mission_id") != mission_id or payload.get("status") != "cancelled":
        raise RunControlError("run control identity or status is invalid")
    if not isinstance(payload.get("cancelled_at"), str) or not payload["cancelled_at"].strip():
        raise RunControlError("run control cancellation time is invalid")
    return payload


def require_active_run(run_dir: Path, mission_id: str) -> None:
    """Refuse a later external action if a cancellation marker exists."""
    if load_run_control(run_dir / "run_control.json", mission_id) is not None:
        raise RunControlError("mission is cancelled; create a new run to continue")


def build_run_status(run_id: str, mission_id: str, state: MissionState, control: dict[str, str] | None) -> dict[str, Any]:
    """Return the public-safe state summary used by CLI and future local UI."""
    cancelled = control is not None
    displayed_state = MissionState.CANCELLED if cancelled else state
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "mission_id": mission_id,
        "state": displayed_state.value,
        "terminal": displayed_state in {MissionState.COMPLETE, MissionState.FAILED, MissionState.CANCELLED},
        "cancellation": "requested" if cancelled else "available",
    }
