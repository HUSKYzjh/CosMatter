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
    status_code: int = 200


@dataclass(frozen=True)
class MinerUBatch:
    batch_id: str
    upload_url: str
    state: str
    markdown_url: str | None = None
    error: str | None = None


class MinerUAdapter:
    """Client for MinerU's token-authenticated v4 asynchronous task API."""

    def __init__(self, settings: Settings, *, sleep=time.sleep) -> None:
        self.settings = settings
        self._sleep = sleep

    def submit_local_file(self, file_name: str, content: bytes) -> MinerUBatch:
        """Request one signed upload URL, upload privately, and retain only task metadata."""
        if not file_name.lower().endswith(".pdf") or len(file_name) > 240:
            raise ValueError("file_name must be a bounded PDF name")
        if not content.startswith(b"%PDF-") or not 0 < len(content) <= 200 * 1024 * 1024:
            raise ValueError("content must be a PDF of at most 200 MB")
        data = self._request_json("POST", "/api/v4/file-urls/batch", {"files": [{"name": file_name, "data_id": "cosmatter_pdf"}], "model_version": self.settings.mineru_model_version})
        details = data.get("data") if isinstance(data, dict) else None
        urls = details.get("file_urls") if isinstance(details, dict) else None
        batch_id = details.get("batch_id") if isinstance(details, dict) else None
        if not isinstance(batch_id, str) or not batch_id or not isinstance(urls, list) or len(urls) != 1 or not isinstance(urls[0], str) or not urls[0].startswith("https://"):
            raise MinerURequestError("MinerU did not return one valid signed upload URL")
        request = Request(url=urls[0], data=content, method="PUT")
        try:
            with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                if getattr(response, "status", 200) not in {200, 201, 204}:
                    raise MinerURequestError("MinerU signed upload failed")
        except (HTTPError, URLError, TimeoutError) as error:
            raise MinerURequestError("MinerU signed upload failed") from error
        return MinerUBatch(batch_id=batch_id, upload_url="redacted", state="pending")

    def get_batch(self, batch_id: str) -> MinerUBatch:
        if not isinstance(batch_id, str) or not batch_id.strip() or len(batch_id) > 200:
            raise ValueError("batch_id must be a nonempty bounded string")
        data = self._request_json("GET", f"/api/v4/extract-results/batch/{batch_id.strip()}")
        details = data.get("data") if isinstance(data, dict) else None
        results = details.get("extract_result") if isinstance(details, dict) else None
        item = results[0] if isinstance(results, list) and results and isinstance(results[0], dict) else None
        if not isinstance(item, dict):
            raise MinerURequestError("MinerU batch result is invalid")
        state = item.get("state")
        if not isinstance(state, str) or state not in _TASK_STATES | {"waiting-file", "converting", "uploading"}:
            raise MinerURequestError("MinerU batch state is invalid")
        markdown_url = item.get("markdown_url")
        return MinerUBatch(batch_id=batch_id.strip(), upload_url="redacted", state=state, markdown_url=markdown_url if state == "done" and isinstance(markdown_url, str) and markdown_url.startswith("https://") else None, error=item.get("err_msg") if isinstance(item.get("err_msg"), str) else None)
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

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self.settings.mineru_api_token
        if not token:
            raise MinerUConfigurationError("MINERU_API_TOKEN is not configured")
        request = Request(url=f"{self.settings.mineru_base_url}{path}", data=json.dumps(payload).encode("utf-8") if payload is not None else None, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method=method)
        try:
            with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise MinerURequestError("MinerU request failed") from error
        if not isinstance(data, dict) or data.get("code") != 0:
            raise MinerURequestError("MinerU response was unsuccessful")
        return data
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
                    return _task_from_response(
                        data,
                        response.headers.get("x-request-id"),
                        getattr(response, "status", 200),
                    )
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


def _task_from_response(payload: Any, request_id: str | None, status_code: int) -> MinerUTask:
    if not isinstance(payload, dict) or payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
        raise MinerURequestError("MinerU response did not contain a successful task payload")
    data = payload["data"]
    task_id = data.get("task_id")
    state = data.get("state", "pending")
    if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 200:
        raise MinerURequestError("MinerU response did not contain a valid task_id")
    if not isinstance(state, str) or state not in _TASK_STATES:
        raise MinerURequestError("MinerU response did not contain a supported task state")
    if not isinstance(status_code, int) or isinstance(status_code, bool) or not 100 <= status_code <= 599:
        raise MinerURequestError("MinerU response did not contain a valid HTTP status")
    return MinerUTask(task_id=task_id, state=state, request_id=request_id, status_code=status_code)
