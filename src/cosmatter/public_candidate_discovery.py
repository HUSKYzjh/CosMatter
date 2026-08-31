"""Credential-free, allowlisted public-candidate discovery boundary.

The optional probe is deliberately smaller than a downloader: it follows only
policy-validated redirects, reads at most a PDF signature, and never writes a
remote body or a plain URL into a mission artifact.
"""
from __future__ import annotations
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
from xml.etree import ElementTree
import certifi
from .config import AGENT_ROOT

class PublicDiscoveryError(ValueError): pass

def load_policy() -> dict[str, Any]:
    try: value=json.loads((AGENT_ROOT/"configs"/"public_candidate_discovery.json").read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as e: raise PublicDiscoveryError("public discovery policy unavailable") from e
    if not isinstance(value,dict) or set(value)!={"schema_version","allowed_hosts","max_redirects","max_response_bytes","timeout_seconds"} or value.get("schema_version")!="cosmatter.public-discovery-policy/v1" or not isinstance(value.get("allowed_hosts"),list) or not value["allowed_hosts"] or not all(isinstance(x,str) and x for x in value["allowed_hosts"]) or value.get("max_redirects")!=3 or value.get("max_response_bytes")!=262144 or value.get("timeout_seconds")!=10: raise PublicDiscoveryError("public discovery policy invalid")
    return value

def validate_public_url(value: object, policy: dict[str, Any] | None=None) -> str:
    policy=policy or load_policy()
    if not isinstance(value,str) or len(value)>2048: raise PublicDiscoveryError("candidate URL invalid")
    parsed=urlsplit(value)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443): raise PublicDiscoveryError("candidate URL must be public HTTPS")
    host=parsed.hostname.rstrip(".").lower()
    try: ipaddress.ip_address(host)
    except ValueError: pass
    else: raise PublicDiscoveryError("candidate URL must not use an IP host")
    if host=="localhost" or host.endswith(".local") or not any(host==allowed or host.endswith("."+allowed) for allowed in policy["allowed_hosts"]): raise PublicDiscoveryError("candidate URL host is not allowlisted")
    return parsed.geturl()

def validate_redirect_chain(urls: object, policy: dict[str, Any] | None=None) -> list[str]:
    policy=policy or load_policy()
    if not isinstance(urls,list) or not urls or len(urls)>policy["max_redirects"]+1: raise PublicDiscoveryError("redirect chain invalid")
    result=[validate_public_url(url,policy) for url in urls]
    if len(set(result))!=len(result): raise PublicDiscoveryError("redirect chain loops")
    return result

def discovery_receipt(*, query: str, redirect_chain: object, status_code: int, candidate_count: int) -> dict[str, Any]:
    if not isinstance(query,str) or not query or len(query)>500 or not isinstance(status_code,int) or not 100<=status_code<=599 or not isinstance(candidate_count,int) or not 0<=candidate_count<=50: raise PublicDiscoveryError("discovery receipt invalid")
    chain=validate_redirect_chain(redirect_chain)
    return {"schema_version":"cosmatter.public-discovery-receipt/v1","trust_status":"untrusted_public_candidate_discovery_not_download_or_evidence","query_length":len(query),"redirect_count":len(chain)-1,"final_host":urlsplit(chain[-1]).hostname,"status_class":f"{status_code//100}xx","candidate_count":candidate_count,"cookies_or_credentials_used":False,"download_or_import_performed":False}


class _NoRedirect(HTTPRedirectHandler):
    """Expose redirects to the policy loop instead of following them implicitly."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _resolve_public_tcp_addresses(host: str, port: int) -> list[tuple[int, int, int, tuple[Any, ...]]]:
    """Resolve a permitted name to public TCP endpoints, fail-closed.

    URL allowlisting alone cannot prevent a permitted hostname from resolving
    to a loopback or private target.  The same resolver result used for the
    eventual connection is therefore checked here; any non-global record
    rejects the whole request rather than relying on address ordering.
    """
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise PublicDiscoveryError("public discovery DNS resolution failed") from error
    result: list[tuple[int, int, int, tuple[Any, ...]]] = []
    seen: set[tuple[int, int, int, tuple[Any, ...]]] = set()
    for family, socktype, protocol, _canonical, sockaddr in records:
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except (ValueError, IndexError, TypeError) as error:
            raise PublicDiscoveryError("public discovery DNS response is invalid") from error
        if not address.is_global:
            raise PublicDiscoveryError("public discovery DNS resolved to a non-public address")
        item = (family, socktype, protocol, sockaddr)
        if item not in seen:
            result.append(item)
            seen.add(item)
    if not result:
        raise PublicDiscoveryError("public discovery DNS returned no public address")
    return result


def _connect_public_tcp(host: str, port: int, timeout: float | None, source_address: tuple[str, int] | None) -> socket.socket:
    """Connect only to a just-validated resolver result (no second DNS lookup)."""
    last_error: OSError | None = None
    for family, socktype, protocol, sockaddr in _resolve_public_tcp_addresses(host, port):
        connection = socket.socket(family, socktype, protocol)
        try:
            if timeout is not None:
                connection.settimeout(timeout)
            if source_address is not None:
                connection.bind(source_address)
            connection.connect(sockaddr)
            return connection
        except OSError as error:
            last_error = error
            connection.close()
    raise OSError("public discovery could not connect to a resolved public address") from last_error


class _PublicHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that pins one checked DNS result for its TCP connect."""

    def connect(self) -> None:
        self.sock = _connect_public_tcp(self.host, self.port, self.timeout, self.source_address)
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        if self._tunnel_host:
            self._tunnel()
        server_hostname = self._tunnel_host if self._tunnel_host else self.host
        self.sock = self._context.wrap_socket(self.sock, server_hostname=server_hostname)


class _PublicHTTPSHandler(HTTPSHandler):
    """Route HTTPS requests through the DNS-checked connection class."""

    def https_open(self, request: Request):  # type: ignore[override]
        return self.do_open(_PublicHTTPSConnection, request, context=self._context)


def _public_opener(context: ssl.SSLContext):
    """Use no ambient HTTP(S) proxy and only checked direct HTTPS connections."""
    return build_opener(ProxyHandler({}), _NoRedirect(), _PublicHTTPSHandler(context=context))


def discover_arxiv_candidates(query: object, *, top_k: int = 10, policy: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Discover bounded arXiv metadata candidates without downloading PDFs.

    The approved query is sent only to the allowlisted Atom endpoint. The
    returned candidate cards retain bibliographic metadata but no source URL,
    abstract, Atom body, cookie or credential; every card remains inaccessible
    until a separate explicit PDF probe confirms a route.
    """
    if not isinstance(query, str) or not query.strip() or len(query.strip()) > 500:
        raise PublicDiscoveryError("public discovery query is invalid")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 50:
        raise PublicDiscoveryError("public discovery top_k is invalid")
    policy = policy or load_policy()
    normalized_query = query.strip()
    endpoint = "https://export.arxiv.org/api/query?" + urlencode({"search_query": f"all:{normalized_query}", "start": 0, "max_results": top_k})
    body, status, chain = _fetch_bounded_public_bytes(endpoint, policy=policy, accept="application/atom+xml, application/xml;q=0.9")
    candidates = _arxiv_atom_candidates(body, normalized_query, top_k)
    return candidates, discovery_receipt(query=normalized_query, redirect_chain=chain, status_code=status, candidate_count=len(candidates))


def _fetch_bounded_public_bytes(value: object, *, policy: dict[str, Any], accept: str) -> tuple[bytes, int, list[str]]:
    """Fetch a small public metadata response with validated redirect hops."""
    current = validate_public_url(value, policy)
    chain = [current]
    context = ssl.create_default_context(cafile=certifi.where())
    opener = _public_opener(context)
    for _ in range(policy["max_redirects"] + 1):
        request = Request(current, headers={"Accept": accept}, method="GET")
        try:
            with opener.open(request, timeout=policy["timeout_seconds"]) as response:
                status = getattr(response, "status", 200)
                body = response.read(policy["max_response_bytes"] + 1)
        except HTTPError as error:
            if error.code not in {301, 302, 303, 307, 308}:
                raise PublicDiscoveryError(f"public discovery request failed with HTTP {error.code}") from error
            location = error.headers.get("Location")
            error.close()
            if not isinstance(location, str) or not location.strip():
                raise PublicDiscoveryError("public discovery redirect lacks a location") from error
            current = validate_public_url(urljoin(current, location), policy)
            chain.append(current)
            if len(chain) > policy["max_redirects"] + 1:
                raise PublicDiscoveryError("public discovery redirect limit exceeded")
            continue
        except (URLError, TimeoutError) as error:
            raise PublicDiscoveryError("public discovery request failed") from error
        if not isinstance(status, int) or not 200 <= status < 300:
            raise PublicDiscoveryError("public discovery returned an unexpected status")
        if len(body) > policy["max_response_bytes"]:
            raise PublicDiscoveryError("public discovery response exceeds the byte safety limit")
        return body, status, chain
    raise PublicDiscoveryError("public discovery redirect limit exceeded")


def _arxiv_atom_candidates(body: bytes, query: str, top_k: int) -> list[dict[str, Any]]:
    lowered = body.lower()
    if not body or b"<!doctype" in lowered or b"<!entity" in lowered:
        raise PublicDiscoveryError("public discovery Atom response is unsafe")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as error:
        raise PublicDiscoveryError("public discovery Atom response is invalid") from error
    namespace = "{http://www.w3.org/2005/Atom}"
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in root.findall(f"{namespace}entry"):
        identifier = _arxiv_identifier(entry.findtext(f"{namespace}id"))
        title = _single_line(entry.findtext(f"{namespace}title"))
        if identifier is None or title is None or identifier in seen:
            continue
        year = _arxiv_year(entry.findtext(f"{namespace}published"))
        result.append({
            "document_id": f"arxiv:{identifier}",
            "title": title,
            "query": query,
            "source": "PublicArXiv",
            "publication_year": year,
            "is_content_accessible": False,
        })
        seen.add(identifier)
        if len(result) == top_k:
            break
    return result


def _arxiv_identifier(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"(?:abs/|arXiv:)?([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)$", value.strip())
    return match.group(1) if match else None


def _single_line(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized[:500] if normalized else None


def _arxiv_year(value: object) -> int | None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T.*", value.strip()):
        return None
    year = int(value[:4])
    return year if 1000 <= year <= 3000 else None


def probe_public_pdf(value: object, *, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Confirm a publicly reachable PDF route without downloading its content.

    Only a five-byte PDF signature may be read. The returned receipt is safe
    to persist: it contains a digest, host, redirect count and status class,
    never a URL, query string, response body or headers.
    """
    policy = policy or load_policy()
    current = validate_public_url(value, policy)
    chain = [current]
    # Python's bundled CA path on Windows can be empty under a virtual
    # environment.  Certifi keeps certificate verification enabled and avoids
    # the unsafe workaround of disabling TLS checks for public discovery.
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    opener = _public_opener(ssl_context)
    for _ in range(policy["max_redirects"] + 1):
        request = Request(current, headers={"Range": "bytes=0-4", "Accept": "application/pdf"}, method="GET")
        try:
            with opener.open(request, timeout=policy["timeout_seconds"]) as response:
                status = getattr(response, "status", 200)
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
                signature = response.read(5)
        except HTTPError as error:
            if error.code not in {301, 302, 303, 307, 308}:
                raise PublicDiscoveryError(f"public PDF probe failed with HTTP {error.code}") from error
            location = error.headers.get("Location")
            error.close()
            if not isinstance(location, str) or not location.strip():
                raise PublicDiscoveryError("public PDF redirect lacks a location") from error
            current = validate_public_url(urljoin(current, location), policy)
            chain.append(current)
            if len(chain) > policy["max_redirects"] + 1:
                raise PublicDiscoveryError("public PDF redirect limit exceeded")
            continue
        except (URLError, TimeoutError) as error:
            raise PublicDiscoveryError("public PDF probe failed") from error
        if not isinstance(status, int) or status not in {200, 206}:
            raise PublicDiscoveryError("public PDF probe returned an unexpected status")
        if content_type != "application/pdf" and signature != b"%PDF-":
            raise PublicDiscoveryError("public source is not a PDF response")
        return {
            "schema_version": "cosmatter.public-pdf-probe-receipt/v1",
            "trust_status": "public_pdf_route_confirmed_not_content_review_or_evidence",
            "source_url_sha256": hashlib.sha256(current.encode("utf-8")).hexdigest(),
            "redirect_count": len(chain) - 1,
            "final_host": urlsplit(current).hostname,
            "status_class": f"{status // 100}xx",
            "pdf_signature_confirmed": signature == b"%PDF-",
            "cookies_or_credentials_used": False,
            "remote_body_persisted": False,
        }
