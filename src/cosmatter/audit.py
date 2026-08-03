"""Append-only, secret-safe JSONL flight recorder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AuditEvent, MissionState


SENSITIVE_TOKENS = ("token", "secret", "api_key", "authorization", "password")


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if any(token in str(key).lower() for token in SENSITIVE_TOKENS) else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    return value


class FlightRecorder:
    def __init__(self, runs_dir: Path, run_id: str) -> None:
        self.run_id = run_id
        self.run_dir = runs_dir / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / "events.jsonl"

    def record(self, *, event_type: str, actor: str, state: MissionState, payload: dict[str, Any]) -> AuditEvent:
        event = AuditEvent(
            run_id=self.run_id,
            event_type=event_type,
            actor=actor,
            state=state,
            payload=sanitize(payload),
        )
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        return event
