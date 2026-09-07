"""Content-free telemetry for rejected local operation parameters."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

from .audit import AuditPathError, safe_run_id
from .models import utc_now
from .operation_parameter_contracts import SCIVERSE_CONTENT_LIMIT_MAX, SCIVERSE_CONTENT_LIMIT_MIN


VALIDATION_REJECTION_SCHEMA_VERSION = "cosmatter.validation-rejection/v1"
VALIDATION_REJECTION_COMMANDS = {"sciverse_read_context"}
VALIDATION_REJECTION_REASON_CODES = {
    "invalid_integer",
    "offset_below_minimum",
    "limit_below_minimum",
    "limit_above_maximum",
}
_FIELDS = {"schema_version", "run_id", "command", "reason_code", "occurred_at"}
_MAX_RECORDS = 10_000


class ValidationRejectionError(ValueError):
    """Raised when rejection telemetry is malformed or exceeds its boundary."""


def detect_cli_validation_rejection(argv: Sequence[str]) -> tuple[str, str] | None:
    """Classify bounded Sciverse CLI failures without retaining their values."""
    if not argv or argv[0] != "sciverse-read-context":
        return None
    for index, token in enumerate(argv[1:], start=1):
        if token == "--":
            break
        flag: str | None = None
        value: str | None = None
        for candidate in ("--offset", "--limit"):
            if token == candidate and index + 1 < len(argv):
                flag, value = candidate, argv[index + 1]
                break
            if token.startswith(f"{candidate}="):
                flag, value = candidate, token.split("=", maxsplit=1)[1]
                break
        if flag is None or value is None:
            continue
        try:
            parsed = int(value)
        except ValueError:
            return "sciverse_read_context", "invalid_integer"
        if flag == "--offset" and parsed < 0:
            return "sciverse_read_context", "offset_below_minimum"
        if flag == "--limit" and parsed < SCIVERSE_CONTENT_LIMIT_MIN:
            return "sciverse_read_context", "limit_below_minimum"
        if flag == "--limit" and parsed > SCIVERSE_CONTENT_LIMIT_MAX:
            return "sciverse_read_context", "limit_above_maximum"
    return None


def record_cli_validation_rejection(argv: Sequence[str], runs_dir: Path) -> bool:
    """Record a detected failure only for an existing, safely named run."""
    classified = detect_cli_validation_rejection(argv)
    raw_run_id = _last_option_value(argv, "--run-id")
    if classified is None or raw_run_id is None:
        return False
    try:
        run_id = safe_run_id(raw_run_id)
    except (AuditPathError, AttributeError):
        return False
    run_dir = runs_dir / run_id
    if not run_dir.is_dir() or not (run_dir / "mission.json").is_file():
        return False
    path = run_dir / "validation_rejections.jsonl"
    try:
        existing = load_validation_rejections(path)
        if len(existing) >= _MAX_RECORDS:
            return False
        command, reason_code = classified
        record = {
            "schema_version": VALIDATION_REJECTION_SCHEMA_VERSION,
            "run_id": run_id,
            "command": command,
            "reason_code": reason_code,
            "occurred_at": utc_now(),
        }
        _validate_record(record, expected_run_id=run_id)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    except (OSError, ValidationRejectionError):
        return False
    return True


def load_validation_rejections(path: Path, *, expected_run_id: str | None = None) -> list[dict[str, str]]:
    """Load a bounded ledger and fail closed on any malformed record."""
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValidationRejectionError("validation rejection ledger cannot be read") from error
    if len(lines) > _MAX_RECORDS or any(not line.strip() for line in lines):
        raise ValidationRejectionError("validation rejection ledger size is invalid")
    records: list[dict[str, str]] = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValidationRejectionError("validation rejection ledger is invalid JSON") from error
        _validate_record(record, expected_run_id=expected_run_id)
        records.append(record)
    return records


def summarize_validation_rejections(records: Sequence[dict[str, str]]) -> list[dict[str, object]]:
    """Project only allowlisted command/reason counts."""
    for record in records:
        _validate_record(record)
    counts = Counter((record["command"], record["reason_code"]) for record in records)
    return [
        {"command": command, "reason_code": reason_code, "rejection_count": count}
        for (command, reason_code), count in sorted(counts.items())
    ]


def _last_option_value(argv: Sequence[str], flag: str) -> str | None:
    result: str | None = None
    for index, token in enumerate(argv):
        if token == "--":
            break
        if token == flag and index + 1 < len(argv):
            result = argv[index + 1]
        elif token.startswith(f"{flag}="):
            result = token.split("=", maxsplit=1)[1]
    return result


def _validate_record(record: object, *, expected_run_id: str | None = None) -> None:
    if not isinstance(record, dict) or set(record) != _FIELDS:
        raise ValidationRejectionError("validation rejection record fields are invalid")
    if record.get("schema_version") != VALIDATION_REJECTION_SCHEMA_VERSION:
        raise ValidationRejectionError("validation rejection schema is invalid")
    try:
        run_id = safe_run_id(record.get("run_id"))
    except (AuditPathError, AttributeError) as error:
        raise ValidationRejectionError("validation rejection run is invalid") from error
    if expected_run_id is not None and run_id != expected_run_id:
        raise ValidationRejectionError("validation rejection belongs to another run")
    if record.get("command") not in VALIDATION_REJECTION_COMMANDS or record.get("reason_code") not in VALIDATION_REJECTION_REASON_CODES:
        raise ValidationRejectionError("validation rejection classification is invalid")
    occurred_at = record.get("occurred_at")
    if not isinstance(occurred_at, str):
        raise ValidationRejectionError("validation rejection time is invalid")
    try:
        parsed = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationRejectionError("validation rejection time is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValidationRejectionError("validation rejection time is invalid")
