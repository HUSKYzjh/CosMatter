"""Narrow, auditable Sciverse HTTP adapter.

This adapter deliberately returns upstream JSON as a retrieval *candidate*.
Only a later extraction-and-verification stage may turn it into an EvidenceCard.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings


class SciverseConfigurationError(RuntimeError):
    pass


class SciverseRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class SciverseResponse:
    payload: dict[str, Any]
    status_code: int
    request_id: str | None


class SciverseAdapter:
    """One narrowly scoped client, designed for logs and deterministic tests."""

    def __init__(self, settings: Settings, *, sleep=time.sleep) -> None:
        self.settings = settings
        self._sleep = sleep

    def agentic_search(self, query: str, *, top_k: int = 10) -> SciverseResponse:
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= top_k <= 50:
            raise ValueError("top_k must be between 1 and 50")
        return self._post_json("/agentic-search", {"query": query.strip(), "top_k": top_k})

    def can_read_content(self, paper: dict[str, Any]) -> bool:
        """Enforce upstream full-text access policy before content expansion."""
        return paper.get("is_content_accessible") is True

    def _post_json(self, path: str, payload: dict[str, Any]) -> SciverseResponse:
        token = self.settings.sciverse_api_token
        if not token:
            raise SciverseConfigurationError("SCIVERSE_API_TOKEN is not configured")
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=f"{self.settings.sciverse_base_url}{path}",
            data=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.settings.api_max_retries):
            try:
                with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                    if not isinstance(parsed, dict):
                        raise SciverseRequestError("Sciverse response was not a JSON object")
                    return SciverseResponse(
                        payload=parsed,
                        status_code=getattr(response, "status", 200),
                        request_id=response.headers.get("x-request-id"),
                    )
            except HTTPError as error:
                last_error = error
                if error.code not in {429, 502, 503}:
                    raise SciverseRequestError(f"Sciverse request failed with HTTP {error.code}") from error
            except (URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
            if attempt + 1 < self.settings.api_max_retries:
                self._sleep(2**attempt)
        raise SciverseRequestError("Sciverse request failed after configured retries") from last_error
