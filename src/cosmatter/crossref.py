"""Bounded Crossref metadata lookup for DOI-rooted reference discovery.

Crossref deposits are bibliographic metadata.  A missing ``reference`` field
is therefore an availability limitation, never evidence that a work cites no
other work.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .config import Settings
from .openalex import normalize_doi


class CrossrefRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class CrossrefWork:
    doi: str
    referenced_dois: tuple[str, ...]
    reference_field_present: bool
    request_id: str | None


class CrossrefAdapter:
    """Fetch one Crossref DOI record and retain bounded reference identifiers."""

    def __init__(self, settings: Settings, *, sleep=time.sleep) -> None:
        self.settings = settings
        self._sleep = sleep

    def work_references_by_doi(self, doi: str) -> CrossrefWork:
        normalized = normalize_doi(doi)
        query = urlencode({"mailto": self.settings.crossref_mailto}) if self.settings.crossref_mailto else ""
        return self._get(f"/works/{quote(normalized, safe='')}" + (f"?{query}" if query else ""))

    def _get(self, path: str) -> CrossrefWork:
        headers = {"Accept": "application/vnd.crossref-api-message+json"}
        if self.settings.crossref_mailto:
            headers["User-Agent"] = f"CosMatter/0.1 (mailto:{self.settings.crossref_mailto})"
        else:
            headers["User-Agent"] = "CosMatter/0.1 (materials-literature-agent)"
        request = Request(url=f"{self.settings.crossref_base_url}{path}", headers=headers, method="GET")
        last_error: Exception | None = None
        for attempt in range(self.settings.api_max_retries):
            try:
                with urlopen(request, timeout=self.settings.http_timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    return _work_from_payload(payload, response.headers.get("x-request-id"))
            except HTTPError as error:
                last_error = error
                if error.code not in {429, 502, 503}:
                    raise CrossrefRequestError(f"Crossref request failed with HTTP {error.code}") from error
            except (URLError, TimeoutError, json.JSONDecodeError, CrossrefRequestError) as error:
                last_error = error
            if attempt + 1 < self.settings.api_max_retries:
                self._sleep(2**attempt)
        raise CrossrefRequestError("Crossref request failed after configured retries") from last_error


def _work_from_payload(payload: Any, request_id: str | None) -> CrossrefWork:
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict) or not isinstance(message.get("DOI"), str):
        raise CrossrefRequestError("Crossref response did not contain a DOI record")
    raw_references = message.get("reference")
    return CrossrefWork(
        doi=normalize_doi(message["DOI"]),
        referenced_dois=_reference_dois(raw_references),
        reference_field_present=isinstance(raw_references, list),
        request_id=request_id,
    )


def _reference_dois(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    result: list[str] = []
    for reference in raw:
        if not isinstance(reference, dict) or not isinstance(reference.get("DOI"), str):
            continue
        try:
            doi = normalize_doi(reference["DOI"])
        except ValueError:
            continue
        if doi not in result:
            result.append(doi)
        if len(result) == 12:
            break
    return tuple(result)
