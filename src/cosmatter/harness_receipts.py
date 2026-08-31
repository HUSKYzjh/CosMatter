"""Secret-safe execution receipts for the CosMatter-to-DSH adapter boundary."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import new_id, utc_now


_HASH = re.compile(r"^[a-f0-9]{64}$")
_OUTCOMES = frozenset({"dispatched", "completed", "blocked"})


class PluginReceiptError(ValueError):
    """Raised when a receipt would overstate an adapter action."""


@dataclass(frozen=True)
class PluginExecutionReceipt:
    """A bounded fact about one adapter call, never an evidence acceptance."""

    mission_id: str
    plugin_id: str
    authorization_receipt_id: str
    outcome: str
    output_artifact_hashes: tuple[str, ...] = ()
    receipt_id: str = field(default_factory=lambda: new_id("plugin_receipt"))
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not all(isinstance(item, str) and item.strip() for item in (self.mission_id, self.plugin_id, self.authorization_receipt_id, self.receipt_id)):
            raise PluginReceiptError("receipt identifiers are required")
        if self.outcome not in _OUTCOMES:
            raise PluginReceiptError("receipt outcome is invalid")
        if len(set(self.output_artifact_hashes)) != len(self.output_artifact_hashes) or any(not _HASH.fullmatch(item) for item in self.output_artifact_hashes):
            raise PluginReceiptError("output artifact hashes are invalid")
        if self.outcome == "completed" and not self.output_artifact_hashes:
            raise PluginReceiptError("completed receipts require output artifact hashes")

    def as_audit_payload(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "mission_id": self.mission_id,
            "plugin_id": self.plugin_id,
            "authorization_receipt_id": self.authorization_receipt_id,
            "outcome": self.outcome,
            "output_artifact_hashes": list(self.output_artifact_hashes),
            "created_at": self.created_at,
            "trust_status": "adapter_execution_receipt_not_evidence_acceptance",
        }
