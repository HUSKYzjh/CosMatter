"""Narrow MinerU v4 task adapter for explicitly authorized remote sources.

The adapter submits an HTTPS source URL only after the caller has passed the
CosMatter candidate-access gate.  It never downloads parser output, follows
result URLs, or persists source text.  Those operations require a later,
separately reviewed source-map workflow.
"""

from __future__ import annotations

import ipaddress
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import Settings


class MinerUConfigurationError(RuntimeError):
    """Raised when the MinerU integration is not configured."""


class MinerURequestError(RuntimeError):
    """Raised when MinerU cannot complete a bounded task operation."""


_TASK_STATES = {"pending", "running", "done", "failed"}


@dataclass(frozen=True)
class MinerUTask:
    task_id: str
    state: str
    request_id: str | None


class MinerUAdapter:
    """Client for MinerU's token-authenticated v4 asynchronous task API."""

    def __init__(self, settings: Settings, *, sleep=time.sleep) -> None:
        self.settings = settings
        self._sleep = sleep

    def submit_remote_source(self, source_url: str) -> MinerUTask:
        """Submit one validated HTTPS URL and return only its task metadata."""
        normalized_url = validate_remote_source_url(source_url)
        return self._request_task(
            method="POST",
            path="/api/v4/extract/task",
            payload={"url": normalized_url, "model_version": self.settings.mineru_model_version},
        )

    def get_task(self, task_id: str) -> MinerUTask:
        """Poll task metadata; parser output URLs and content are discarded."""
        task_id = task_id.strip()
        if not task_id or len(task_id) > 200:
            raise ValueError("task_id must be a nonempty bounded string")
        return self._request_task(method="GET", path=f"/api/v4/extract/task/{task_id}")

    def _request_task(self, *, method: str, path: str, payload: dict[str, Any] | None = None) -> MinerUTask:
        token = self.settings.mineru_api_token
        if not token:
            raise MinerUConfigurationError("MINERU_API_TOKEN is not configured")
        request = Request(
            url=f"{self.settings.mineru_base_url}{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method=method,
        )
        last_error: Exception | None = None
        for attempt in range(self.settings.api_max_retries):
            try:
                with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    return _task_from_response(data, response.headers.get("x-request-id"))
            except HTTPError as error:
                last_error = error
                if error.code not in {429, 502, 503}:
                    raise MinerURequestError(f"MinerU request failed with HTTP {error.code}") from error
            except (URLError, TimeoutError, json.JSONDecodeError, MinerURequestError) as error:
                last_error = error
            if attempt + 1 < self.settings.api_max_retries:
                self._sleep(2**attempt)
        raise MinerURequestError("MinerU request failed after configured retries") from last_error


def validate_remote_source_url(value: str) -> str:
    """Accept only a public-looking HTTPS source URL without credentials.

    This is a client-side guard, not a replacement for provider-side SSRF
    protections.  DNS is deliberately not resolved here, avoiding outbound
    side effects before explicit task submission.
    """
    if not isinstance(value, str) or not value.strip() or len(value) > 2_000:
        raise ValueError("source_url must be a nonempty URL of at most 2000 characters")
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source_url must be an HTTPS URL without credentials")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".local"):
        raise ValueError("source_url must not target a local host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved):
        raise ValueError("source_url must not target a private or reserved address")
    return parsed.geturl()


def _task_from_response(payload: Any, request_id: str | None) -> MinerUTask:
    if not isinstance(payload, dict) or payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
        raise MinerURequestError("MinerU response did not contain a successful task payload")
    data = payload["data"]
    task_id = data.get("task_id")
    state = data.get("state", "pending")
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 200:
        raise MinerURequestError("MinerU response did not contain a valid task_id")
    if not isinstance(state, str) or state not in _TASK_STATES:
        raise MinerURequestError("MinerU response did not contain a supported task state")
    return MinerUTask(task_id=task_id, state=state, request_id=request_id)
