"""Bounded OpenAlex work lookup for DOI-rooted relation expansion."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import Settings


class OpenAlexConfigurationError(RuntimeError):
    pass


class OpenAlexRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAlexWork:
    work_id: str
    referenced_work_ids: tuple[str, ...]
    related_work_ids: tuple[str, ...]
    request_id: str | None


class OpenAlexAdapter:
    """Fetch one DOI-rooted work and retain only public relation identifiers."""

    def __init__(self, settings: Settings, *, sleep=time.sleep) -> None:
        self.settings = settings
        self._sleep = sleep

    def work_relations_by_doi(self, doi: str) -> OpenAlexWork:
        normalized = normalize_doi(doi)
        if not self.settings.openalex_api_key:
            raise OpenAlexConfigurationError("OPENALEX_API_KEY is not configured")
        path = f"/works/https://doi.org/{quote(normalized, safe='/')}?select=id,referenced_works,related_works"
        return self._get(path)


    def citing_dois_by_doi(self, doi: str, *, limit: int = 25) -> tuple[str, ...]:
        """Return DOI-bearing citing works as public bibliographic metadata."""
        normalized = normalize_doi(doi)
        if not self.settings.openalex_api_key:
            raise OpenAlexConfigurationError("OPENALEX_API_KEY is not configured")
        if not isinstance(limit, int) or not 1 <= limit <= 25:
            raise ValueError("limit must be between 1 and 25")
        path = f"/works?filter=cites:https://doi.org/{quote(normalized, safe='/')}&per-page={limit}&select=doi"
        request = Request(url=f"{self.settings.openalex_base_url}{path}", headers={"Authorization": f"Bearer {self.settings.openalex_api_key}"}, method="GET")
        try:
            with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise OpenAlexRequestError("OpenAlex cited-by request failed") from error
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            raise OpenAlexRequestError("OpenAlex cited-by response is invalid")
        values: list[str] = []
        for item in results:
            raw = item.get("doi") if isinstance(item, dict) else None
            if not isinstance(raw, str):
                continue
            try:
                value = normalize_doi(raw)
            except ValueError:
                continue
            if value not in values:
                values.append(value)
        return tuple(values)

    def _get(self, path: str) -> OpenAlexWork:
        request = Request(
            url=f"{self.settings.openalex_base_url}{path}",
            headers={"Authorization": f"Bearer {self.settings.openalex_api_key}"},
            method="GET",
        )
        last_error: Exception | None = None
        for attempt in range(self.settings.api_max_retries):
            try:
                with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    return _work_from_payload(payload, response.headers.get("x-request-id"))
            except HTTPError as error:
                last_error = error
                if error.code not in {429, 502, 503}:
                    raise OpenAlexRequestError(f"OpenAlex request failed with HTTP {error.code}") from error
            except (URLError, TimeoutError, json.JSONDecodeError, OpenAlexRequestError) as error:
                last_error = error
            if attempt + 1 < self.settings.api_max_retries:
                self._sleep(2**attempt)
        raise OpenAlexRequestError("OpenAlex request failed after configured retries") from last_error


def normalize_doi(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("doi must be a string")
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    if not normalized.startswith("10.") or "/" not in normalized or len(normalized) > 255 or any(character.isspace() for character in normalized):
        raise ValueError("doi must be a bounded DOI")
    return normalized


def _work_from_payload(payload: Any, request_id: str | None) -> OpenAlexWork:
    if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
        raise OpenAlexRequestError("OpenAlex response did not contain a work ID")
    return OpenAlexWork(
        work_id=payload["id"],
        referenced_work_ids=_work_ids(payload.get("referenced_works")),
        related_work_ids=_work_ids(payload.get("related_works")),
        request_id=request_id,
    )


def _work_ids(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    result: list[str] = []
    for value in raw:
        if isinstance(value, str) and value.startswith("https://openalex.org/W") and len(value) <= 80 and value not in result:
            result.append(value)
        if len(result) == 12:
            break
    return tuple(result)
