"""Bounded public metadata search adapters for approved literature queries.

The module projects OpenAlex and Crossref responses into the same metadata-only
``PaperCandidate`` shape used for Sciverse.  It deliberately excludes abstracts,
full text, author lists, raw responses, and credentials.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import Settings
from .models import PaperCandidate, normalized_doi_or_none


class MetadataSearchConfigurationError(RuntimeError):
    pass


class MetadataSearchRequestError(RuntimeError):
    pass


class MetadataSearchAdapter:
    """Search configured scholarly metadata APIs after a human has approved a query."""

    def __init__(self, settings: Settings, *, sleep: Callable[[float], None] = time.sleep) -> None:
        self.settings = settings
        self._sleep = sleep

    def search_openalex(self, query: str, *, top_k: int) -> tuple[PaperCandidate, ...]:
        _validate_query(query, top_k)
        if not self.settings.openalex_api_key:
            raise MetadataSearchConfigurationError("OPENALEX_API_KEY is not configured")
        params = {
            "search": query,
            "per-page": str(top_k),
            "select": "id,display_name,publication_year,open_access,doi,cited_by_count",
            "api_key": self.settings.openalex_api_key,
        }
        payload = self._request_json(self.settings.openalex_base_url, "/works", params, {"Accept": "application/json"}, "OpenAlex")
        records = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            raise MetadataSearchRequestError("OpenAlex response did not contain a results list")
        candidates: list[PaperCandidate] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            work_id = _bounded_string(record.get("id"), 180)
            title = _bounded_string(record.get("display_name"), 500)
            if not work_id or not title:
                continue
            access = record.get("open_access")
            is_oa = isinstance(access, dict) and access.get("is_oa") is True
            candidate = _candidate(
                document_id=f"openalex:{work_id.rsplit('/', maxsplit=1)[-1]}", title=title, query=query,
                source="OpenAlex", year=record.get("publication_year"), score=record.get("cited_by_count"), accessible=is_oa,
                doi=normalized_doi_or_none(record.get("doi")),
            )
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) == top_k:
                break
        return _dedupe(candidates)

    def search_crossref(self, query: str, *, top_k: int) -> tuple[PaperCandidate, ...]:
        _validate_query(query, top_k)
        params = {
            "query.bibliographic": query,
            "rows": str(top_k),
            "select": "DOI,title,published,issued,is-referenced-by-count,URL",
        }
        if self.settings.crossref_mailto:
            params["mailto"] = self.settings.crossref_mailto
        user_agent = f"CosMatter/0.1 (mailto:{self.settings.crossref_mailto})" if self.settings.crossref_mailto else "CosMatter/0.1 (materials-literature-agent)"
        payload = self._request_json(self.settings.crossref_base_url, "/works", params, {"Accept": "application/vnd.crossref-api-message+json", "User-Agent": user_agent}, "Crossref")
        message = payload.get("message") if isinstance(payload, dict) else None
        records = message.get("items") if isinstance(message, dict) else None
        if not isinstance(records, list):
            raise MetadataSearchRequestError("Crossref response did not contain a works list")
        candidates: list[PaperCandidate] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            doi = normalized_doi_or_none(_bounded_string(record.get("DOI"), 255))
            title = _first_title(record.get("title"))
            if not doi or not title:
                continue
            candidate = _candidate(
                document_id=f"doi:{doi}", title=title, query=query, source="Crossref",
                year=_crossref_year(record), score=record.get("is-referenced-by-count"), accessible=False,
                doi=doi,
            )
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) == top_k:
                break
        return _dedupe(candidates)

    def _request_json(self, base_url: str, path: str, params: dict[str, str], headers: dict[str, str], provider: str) -> Any:
        request = Request(url=f"{base_url.rstrip('/')}{path}?{urlencode(params)}", headers=headers, method="GET")
        last_error: Exception | None = None
        for attempt in range(self.settings.api_max_retries):
            try:
                with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                last_error = error
                if error.code not in {429, 502, 503}:
                    raise MetadataSearchRequestError(f"{provider} request failed with HTTP {error.code}") from error
            except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
                last_error = error
            if attempt + 1 < self.settings.api_max_retries:
                self._sleep(2**attempt)
        raise MetadataSearchRequestError(f"{provider} request failed after configured retries") from last_error


def _validate_query(query: str, top_k: int) -> None:
    if not isinstance(query, str) or not query.strip() or len(query.strip()) > 3_000:
        raise ValueError("query must be a nonempty string of at most 3000 characters")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20")


def _bounded_string(value: object, maximum: int) -> str | None:
    return value.strip()[:maximum] if isinstance(value, str) and value.strip() else None


def _first_title(value: object) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    return _bounded_string(value[0], 500)


def _crossref_year(record: dict[str, Any]) -> int | None:
    for key in ("published", "issued"):
        part = record.get(key)
        values = part.get("date-parts") if isinstance(part, dict) else None
        if isinstance(values, list) and values and isinstance(values[0], list) and values[0] and isinstance(values[0][0], int):
            return values[0][0]
    return None


def _candidate(*, document_id: str, title: str, query: str, source: str, year: object, score: object, accessible: bool, doi: str | None = None) -> PaperCandidate | None:
    try:
        return PaperCandidate(document_id=document_id, title=title, query=query, source=source, publication_year=year if isinstance(year, int) else None, score=float(score) if isinstance(score, (int, float)) else None, is_content_accessible=accessible, doi=doi)
    except ValueError:
        return None


def _dedupe(candidates: list[PaperCandidate]) -> tuple[PaperCandidate, ...]:
    """Collapse only exact DOI aliases within one metadata-provider response."""
    retained: dict[str, PaperCandidate] = {}
    for candidate in candidates:
        identity = f"doi:{candidate.doi}" if candidate.doi else f"document:{candidate.document_id.casefold()}"
        retained.setdefault(identity, candidate)
    return tuple(retained.values())
