"""Narrow, auditable Sciverse HTTP adapter.

This adapter deliberately returns upstream JSON as a retrieval *candidate*.
Only a later extraction-and-verification stage may turn it into an EvidenceCard.
"""

from __future__ import annotations

import json
import time
from urllib.parse import urlencode
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


@dataclass(frozen=True)
class SciverseContentResponse:
    text: str
    next_offset: int | None
    more: bool
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

    def read_content(self, document_id: str, *, offset: int = 0, limit: int = 2_000) -> SciverseContentResponse:
        """Read one bounded full-text context window after a human screening gate."""
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id.strip()) > 255:
            raise ValueError("document_id must be a bounded nonempty string")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 200 <= limit <= 4_000:
            raise ValueError("limit must be between 200 and 4000")
        response = self._get_json("/content", {"doc_id": document_id.strip(), "offset": offset, "limit": limit})
        text, more, next_offset = response.payload.get("text"), response.payload.get("more"), response.payload.get("next_offset")
        if not isinstance(text, str) or not text or len(text) > limit:
            raise SciverseRequestError("Sciverse content response did not contain a bounded text window")
        if not isinstance(more, bool) or (next_offset is not None and (not isinstance(next_offset, int) or next_offset < 0)):
            raise SciverseRequestError("Sciverse content response had invalid continuation metadata")
        return SciverseContentResponse(text=text, next_offset=next_offset, more=more, status_code=response.status_code, request_id=response.request_id)

    def can_read_content(self, paper: dict[str, Any]) -> bool:
        """Enforce upstream full-text access policy before content expansion."""
        return paper.get("is_content_accessible") is True

    def _get_json(self, path: str, params: dict[str, Any]) -> SciverseResponse:
        token = self.settings.sciverse_api_token
        if not token:
            raise SciverseConfigurationError("SCIVERSE_API_TOKEN is not configured")
        request = Request(
            url=f"{self.settings.sciverse_base_url}{path}?{urlencode(params)}",
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        last_error: Exception | None = None
        for attempt in range(self.settings.api_max_retries):
            try:
                with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                    if not isinstance(parsed, dict):
                        raise SciverseRequestError("Sciverse response was not a JSON object")
                    return SciverseResponse(parsed, getattr(response, "status", 200), response.headers.get("x-request-id"))
            except HTTPError as error:
                last_error = error
                if error.code not in {429, 502, 503}:
                    raise SciverseRequestError(f"Sciverse request failed with HTTP {error.code}") from error
            except (URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
            if attempt + 1 < self.settings.api_max_retries:
                self._sleep(2**attempt)
        raise SciverseRequestError("Sciverse request failed after configured retries") from last_error

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
