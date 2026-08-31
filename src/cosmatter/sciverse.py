"""Narrow, auditable adapter over the official Sciverse Python SDK.

The SDK is the compatibility boundary for Sciverse authentication, pagination
and request semantics. This synchronous facade deliberately exposes only the
two bounded calls CosMatter needs; it never turns search snippets into
accepted evidence or guesses that a document can be read in full.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from .config import Settings

try:
    # Load the optional SDK during service startup.  Deferring this import to
    # the first approved query can consume an otherwise valid local request's
    # response window; an unavailable SDK remains a configuration error only
    # when a Sciverse operation is actually requested.
    from sciverse import AgentToolsClient as _OfficialAgentToolsClient
except ImportError:
    _OfficialAgentToolsClient = None


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
    """Bounded synchronous facade for ``sciverse.AgentToolsClient``."""

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory or _official_client_factory

    def agentic_search(self, query: str, *, top_k: int = 10) -> SciverseResponse:
        """Run the SDK's documented ``semantic_search`` operation."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= top_k <= 50:
            raise ValueError("top_k must be between 1 and 50")
        payload = self._run("semantic_search", query=query.strip(), top_k=top_k, mode="balanced")
        hits = payload.get("hits")
        if not isinstance(hits, list):
            raise SciverseRequestError("Sciverse semantic_search response did not contain hits")
        return SciverseResponse(payload=payload, status_code=200, request_id=_request_id(payload))

    def read_content(self, document_id: str, *, offset: int = 0, limit: int = 2_000) -> SciverseContentResponse:
        """Read one explicitly requested, bounded SDK content window."""
        if not isinstance(document_id, str) or not document_id.strip() or len(document_id.strip()) > 255:
            raise ValueError("document_id must be a bounded nonempty string")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 200 <= limit <= 4_000:
            raise ValueError("limit must be between 200 and 4000")
        payload = self._run("read_content", doc_id=document_id.strip(), offset=offset, limit=limit)
        text, more, next_offset = payload.get("text"), payload.get("more"), payload.get("next_offset")
        if not isinstance(text, str) or not text or len(text) > limit:
            raise SciverseRequestError("Sciverse read_content response did not contain a bounded text window")
        if not isinstance(more, bool) or (next_offset is not None and (not isinstance(next_offset, int) or next_offset < 0)):
            raise SciverseRequestError("Sciverse read_content response had invalid continuation metadata")
        return SciverseContentResponse(text=text, next_offset=next_offset, more=more, status_code=200, request_id=_request_id(payload))

    def can_read_content(self, paper: dict[str, Any]) -> bool:
        """Decide whether a Sciverse result names a documented content route.

        The SDK does not promise ``is_content_accessible`` on semantic hits.
        Its ``doc_id`` is documented as present only for a full-text artifact,
        while an explicit boolean remains authoritative when supplied.
        """
        explicit = paper.get("is_content_accessible")
        if isinstance(explicit, bool):
            return explicit
        document_id = paper.get("doc_id")
        return isinstance(document_id, str) and bool(document_id.strip())

    def _run(self, operation: str, /, **kwargs: Any) -> dict[str, Any]:
        token = self.settings.sciverse_api_token
        if not token:
            raise SciverseConfigurationError("SCIVERSE_API_TOKEN is not configured")

        async def invoke() -> dict[str, Any]:
            try:
                async with self._client_factory(
                    base_url=self.settings.sciverse_base_url,
                    token=token,
                    timeout=float(self.settings.http_timeout_seconds),
                ) as client:
                    result = await getattr(client, operation)(**kwargs)
            except Exception as error:
                response = getattr(error, "response", None)
                status = getattr(response, "status_code", None)
                headers = getattr(response, "headers", {})
                request_id = headers.get("x-request-id") if hasattr(headers, "get") else None
                suffix = f" with HTTP {status}" if isinstance(status, int) else ""
                request_suffix = f" (request_id={request_id})" if isinstance(request_id, str) and request_id.strip() else ""
                raise SciverseRequestError(f"Sciverse {operation} request failed{suffix}{request_suffix}") from error
            if not isinstance(result, dict):
                raise SciverseRequestError(f"Sciverse {operation} response was not a JSON object")
            return result

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(invoke())
        raise SciverseRequestError("synchronous SciverseAdapter cannot run inside an active event loop")


def _official_client_factory(**kwargs: Any) -> Any:
    if _OfficialAgentToolsClient is None:
        raise SciverseConfigurationError("official sciverse SDK is not installed")
    return _OfficialAgentToolsClient(**kwargs)


def _request_id(payload: dict[str, Any]) -> str | None:
    for key in ("request_id", "x_request_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
