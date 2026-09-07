"""Single source of truth for bounded cross-surface operation parameters."""

from __future__ import annotations

from typing import Any


OPERATION_PARAMETER_CONTRACTS_SCHEMA_VERSION = "cosmatter.operation-parameter-contracts/v1"
OPERATION_PARAMETER_CONTRACTS_TRUST_STATUS = "static_parameter_contracts_not_execution_authorization"
SCIVERSE_CONTENT_OFFSET_MIN = 0
SCIVERSE_CONTENT_LIMIT_MIN = 200
SCIVERSE_CONTENT_LIMIT_MAX = 4_000
SCIVERSE_CONTENT_LIMIT_DEFAULT = 2_000


def sciverse_content_parameter_schema() -> dict[str, Any]:
    """Return a fresh closed JSON Schema fragment for one bounded read window."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["offset", "limit"],
        "properties": {
            "offset": {
                "type": "integer",
                "minimum": SCIVERSE_CONTENT_OFFSET_MIN,
                "default": SCIVERSE_CONTENT_OFFSET_MIN,
            },
            "limit": {
                "type": "integer",
                "minimum": SCIVERSE_CONTENT_LIMIT_MIN,
                "maximum": SCIVERSE_CONTENT_LIMIT_MAX,
                "default": SCIVERSE_CONTENT_LIMIT_DEFAULT,
            },
        },
    }


def operation_parameter_contracts() -> dict[str, Any]:
    """Expose static discovery data without a provider call or execution grant."""
    return {
        "schema_version": OPERATION_PARAMETER_CONTRACTS_SCHEMA_VERSION,
        "trust_status": OPERATION_PARAMETER_CONTRACTS_TRUST_STATUS,
        "operations": {
            "sciverse_read_content": sciverse_content_parameter_schema(),
        },
    }


def validate_sciverse_content_parameters(offset: object, limit: object) -> tuple[int, int]:
    """Validate the same range at CLI, SDK, receipt, and artifact boundaries."""
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < SCIVERSE_CONTENT_OFFSET_MIN:
        raise ValueError("offset must be a nonnegative integer")
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not SCIVERSE_CONTENT_LIMIT_MIN <= limit <= SCIVERSE_CONTENT_LIMIT_MAX
    ):
        raise ValueError(
            f"limit must be between {SCIVERSE_CONTENT_LIMIT_MIN} and {SCIVERSE_CONTENT_LIMIT_MAX}"
        )
    return offset, limit


def parse_sciverse_offset(value: str) -> int:
    """Argparse converter generated from the shared offset contract."""
    parsed = int(value)
    return validate_sciverse_content_parameters(parsed, SCIVERSE_CONTENT_LIMIT_DEFAULT)[0]


def parse_sciverse_limit(value: str) -> int:
    """Argparse converter generated from the shared limit contract."""
    parsed = int(value)
    return validate_sciverse_content_parameters(SCIVERSE_CONTENT_OFFSET_MIN, parsed)[1]
