#!/usr/bin/env python3
"""Archive public Liu Theory Lab PDF links with only the Python standard library.

The crawler is confined to one HTTPS origin, honours a discoverable robots.txt,
uses a delay between requests, and writes a manifest with file hashes.  It is
intended for private research input only; it does not bypass access controls or
make downloaded PDFs part of a submission package.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urldefrag, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser


DEFAULT_ORIGIN = "https://liutheory.westlake.edu.cn"
USER_AGENT = "CosMatterResearchArchive/1.0 (public-document archival; local academic use)"


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() not in {"a", "area"}:
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.hrefs.append(value.strip())


@dataclass
class PdfRecord:
    source_url: str
    local_file: str
    status: str
    retrieved_at: str
    content_type: str = ""
    bytes: int = 0
    sha256: str = ""
    discovered_from: str = ""
    detail: str = ""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def canonical(url: str) -> str:
    raw, _ = urldefrag(url)
    parsed = urlparse(raw)
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", parsed.query, ""))


def in_scope(url: str, origin: str) -> bool:
    candidate, root = urlparse(url), urlparse(origin)
    return candidate.scheme == "https" and candidate.netloc.lower() == root.netloc.lower()


def likely_pdf(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def likely_html(url: str) -> bool:
    path = urlparse(url).path.lower()
    return not path or path.endswith("/") or path.endswith(".html") or path.endswith(".htm")


def sleep_for_delay(delay: float, last_request: list[float]) -> None:
    wait = delay - (time.monotonic() - last_request[0])
    if wait > 0:
        time.sleep(wait)


def fetch(url: str, delay: float, last_request: list[float]):
    sleep_for_delay(delay, last_request)
    response = urlopen(
        Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.1"}),
        timeout=90,
    )
    last_request[0] = time.monotonic()
    return response


def filename_for(url: str, index: int) -> str:
    raw = Path(urlparse(url).path).name or f"pdf-{index:04d}.pdf"
    if not raw.lower().endswith(".pdf"):
        raw += ".pdf"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._") or f"pdf-{index:04d}.pdf"
    return safe


def destination_for(directory: Path, url: str, index: int) -> Path:
    candidate = directory / filename_for(url, index)
    if not candidate.exists():
        return candidate
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return directory / f"{candidate.stem}-{digest}{candidate.suffix}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--origin", default=DEFAULT_ORIGIN)
    parser.add_argument("--max-pages", type=int, default=120)
    parser.add_argument("--delay", type=float, default=1.2)
    parser.add_argument("--max-pdf-mb", type=int, default=100)
    parser.add_argument("--max-total-mb", type=int, default=4096)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    origin = canonical(args.origin)
    if not in_scope(origin, origin) or args.max_pages < 1 or args.delay < 0:
        raise SystemExit("use one HTTPS origin and positive crawl limits")
    max_pdf_bytes = args.max_pdf_mb * 1024 * 1024
    max_total_bytes = args.max_total_mb * 1024 * 1024
    if max_pdf_bytes < 1 or max_total_bytes < 1:
        raise SystemExit("byte limits must be positive")

    output = args.output.resolve()
    pdf_dir = output / "pdf"
    output.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(exist_ok=True)
    manifest_path = output / "manifest.json"
    prior: dict[str, PdfRecord] = {}
    if args.resume and manifest_path.exists():
        for item in json.loads(manifest_path.read_text(encoding="utf-8")):
            prior[item["source_url"]] = PdfRecord(**item)

    robots = RobotFileParser(urljoin(origin + "/", "robots.txt"))
    try:
        robots.read()
        robots_available = True
    except OSError:
        robots_available = False

    queue: deque[str] = deque([origin + "/", origin + "/index.html", origin + "/resource.html"])
    visited: set[str] = set()
    discovered: dict[str, str] = {}
    last_request = [0.0]
    while queue and len(visited) < args.max_pages:
        page = canonical(queue.popleft())
        if page in visited or not in_scope(page, origin) or not likely_html(page):
            continue
        if robots_available and not robots.can_fetch(USER_AGENT, page):
            continue
        visited.add(page)
        try:
            response = fetch(page, args.delay, last_request)
            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                response.close()
                continue
            encoding = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(encoding, errors="replace")
            response.close()
        except (HTTPError, URLError, OSError, ValueError) as error:
            print(f"PAGE_ERROR {page}: {error}", file=sys.stderr)
            continue
        collector = LinkCollector()
        collector.feed(body)
        for href in collector.hrefs:
            target = canonical(urljoin(page, href))
            if not in_scope(target, origin):
                continue
            if likely_pdf(target):
                discovered.setdefault(target, page)
            elif likely_html(target) and target not in visited:
                queue.append(target)

    records: list[PdfRecord] = []
    total_bytes = 0
    for index, (url, parent) in enumerate(sorted(discovered.items()), start=1):
        old = prior.get(url)
        if old and old.status == "downloaded" and (output / old.local_file).is_file():
            records.append(old)
            total_bytes += old.bytes
            continue
        if robots_available and not robots.can_fetch(USER_AGENT, url):
            records.append(PdfRecord(url, "", "skipped_robots", utc_now(), discovered_from=parent))
            continue
        if total_bytes >= max_total_bytes:
            records.append(PdfRecord(url, "", "skipped_total_limit", utc_now(), discovered_from=parent))
            continue
        partial = pdf_dir / f".partial-{index:04d}.pdf"
        try:
            response = fetch(url, args.delay, last_request)
            final_url = canonical(response.geturl())
            if not in_scope(final_url, origin):
                raise ValueError("redirected outside permitted origin")
            content_type = response.headers.get("Content-Type", "")
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > max_pdf_bytes:
                response.close()
                records.append(PdfRecord(url, "", "skipped_file_limit", utc_now(), content_type, int(declared), discovered_from=parent))
                continue
            digest, size = hashlib.sha256(), 0
            with partial.open("wb") as handle:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_pdf_bytes:
                        raise ValueError(f"file exceeds {args.max_pdf_mb} MB limit")
                    if total_bytes + size > max_total_bytes:
                        raise ValueError(f"total exceeds {args.max_total_mb} MB limit")
                    digest.update(chunk)
                    handle.write(chunk)
            response.close()
            if partial.read_bytes()[:5] != b"%PDF-":
                raise ValueError("response lacks PDF signature")
            destination = destination_for(pdf_dir, final_url, index)
            partial.replace(destination)
            records.append(PdfRecord(url, destination.relative_to(output).as_posix(), "downloaded", utc_now(), content_type, size, digest.hexdigest(), parent))
            total_bytes += size
        except (HTTPError, URLError, OSError, ValueError) as error:
            partial.unlink(missing_ok=True)
            records.append(PdfRecord(url, "", "failed", utc_now(), discovered_from=parent, detail=str(error)))

    payload = [asdict(item) for item in records]
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(PdfRecord("", "", "", "")).keys()))
        writer.writeheader()
        writer.writerows(payload)
    summary = {
        "origin": origin,
        "retrieved_at": utc_now(),
        "robots_txt_available": robots_available,
        "pages_visited": len(visited),
        "pdf_links_discovered": len(discovered),
        "downloaded": sum(item.status == "downloaded" for item in records),
        "failed": sum(item.status == "failed" for item in records),
        "skipped": sum(item.status.startswith("skipped_") for item in records),
        "downloaded_bytes": total_bytes,
        "limits": {"max_pdf_bytes": max_pdf_bytes, "max_total_bytes": max_total_bytes, "delay_seconds": args.delay},
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

