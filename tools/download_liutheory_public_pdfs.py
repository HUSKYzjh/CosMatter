#!/usr/bin/env python3
"""Download public PDFs linked by Liu Theory Lab with a reproducible manifest.

This utility is deliberately restricted to one public origin.  It does not
authenticate, bypass access controls, or recurse off-site.  It stores the
source URL, retrieval time, content type, byte count and SHA-256 alongside
each downloaded file so that downstream PDF parsing can be audited.
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
from urllib.parse import urljoin, urldefrag, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests


DEFAULT_ORIGIN = "https://liutheory.westlake.edu.cn"
USER_AGENT = "CosMatterResearchArchive/1.0 (public-document archival; local academic use)"
MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024


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


def canonical(url: str) -> str:
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", parsed.query, ""))


def in_scope(url: str, origin: str) -> bool:
    candidate = urlparse(url)
    root = urlparse(origin)
    return candidate.scheme in {"http", "https"} and candidate.netloc.lower() == root.netloc.lower()


def likely_pdf(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def likely_html(url: str) -> bool:
    path = urlparse(url).path.lower()
    return not path or path.endswith("/") or path.endswith(".html") or path.endswith(".htm")


def safe_filename(url: str, index: int) -> str:
    stem = Path(urlparse(url).path).name or f"pdf-{index:04d}.pdf"
    if not stem.lower().endswith(".pdf"):
        stem = f"{stem}.pdf"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or f"pdf-{index:04d}.pdf"
    return stem


def unique_path(directory: Path, filename: str, url: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    suffix = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return directory / f"{candidate.stem}-{suffix}{candidate.suffix}"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="private output directory")
    parser.add_argument("--origin", default=DEFAULT_ORIGIN, help="single permitted website origin")
    parser.add_argument("--max-pages", type=int, default=120, help="maximum same-site HTML pages to inspect")
    parser.add_argument("--delay", type=float, default=1.0, help="minimum seconds between requests")
    parser.add_argument("--max-pdf-mb", type=int, default=100, help="skip files larger than this limit")
    parser.add_argument("--max-total-mb", type=int, default=4096, help="stop before exceeding this total")
    parser.add_argument("--resume", action="store_true", help="keep prior manifest entries and skip matching files")
    return parser.parse_args()


def request(session: requests.Session, url: str, delay: float, last_request: list[float]) -> requests.Response:
    pause = delay - (time.monotonic() - last_request[0])
    if pause > 0:
        time.sleep(pause)
    response = session.get(url, timeout=(10, 90), stream=True, allow_redirects=True)
    last_request[0] = time.monotonic()
    response.raise_for_status()
    return response


def main() -> int:
    args = parse_args()
    origin = canonical(args.origin)
    root = urlparse(origin)
    if root.scheme != "https" or not root.netloc:
        raise SystemExit("--origin must be one HTTPS origin")
    if args.max_pages <= 0 or args.delay < 0 or args.max_pdf_mb <= 0 or args.max_total_mb <= 0:
        raise SystemExit("limits must be positive")

    output = args.output.resolve()
    pdf_dir = output / "pdf"
    output.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(exist_ok=True)
    manifest_path = output / "manifest.json"
    csv_path = output / "manifest.csv"
    max_pdf_bytes = args.max_pdf_mb * 1024 * 1024
    max_total_bytes = args.max_total_mb * 1024 * 1024

    prior: dict[str, PdfRecord] = {}
    if args.resume and manifest_path.exists():
        for item in json.loads(manifest_path.read_text(encoding="utf-8")):
            prior[item["source_url"]] = PdfRecord(**item)

    robots = RobotFileParser()
    robots.set_url(urljoin(origin + "/", "robots.txt"))
    try:
        robots.read()
        robots_available = True
    except OSError:
        robots_available = False

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.1"})
    queue: deque[str] = deque([origin + "/", origin + "/index.html", origin + "/resource.html"])
    visited_pages: set[str] = set()
    discovered: dict[str, str] = {}
    last_request = [0.0]

    while queue and len(visited_pages) < args.max_pages:
        page = canonical(queue.popleft())
        if page in visited_pages or not in_scope(page, origin) or not likely_html(page):
            continue
        if robots_available and not robots.can_fetch(USER_AGENT, page):
            continue
        visited_pages.add(page)
        try:
            response = request(session, page, args.delay, last_request)
            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                continue
            text = response.text
        except requests.RequestException as error:
            print(f"PAGE_ERROR {page}: {error}", file=sys.stderr)
            continue
        collector = LinkCollector()
        collector.feed(text)
        for href in collector.hrefs:
            target = canonical(urljoin(page, href))
            if not in_scope(target, origin):
                continue
            if likely_pdf(target):
                discovered.setdefault(target, page)
            elif likely_html(target) and target not in visited_pages:
                queue.append(target)

    records: list[PdfRecord] = []
    total_downloaded = 0
    for index, (url, parent) in enumerate(sorted(discovered.items()), start=1):
        existing = prior.get(url)
        if existing and existing.status == "downloaded" and (output / existing.local_file).is_file():
            records.append(existing)
            total_downloaded += existing.bytes
            continue
        if robots_available and not robots.can_fetch(USER_AGENT, url):
            records.append(PdfRecord(url, "", "skipped_robots", utc_now(), discovered_from=parent))
            continue
        if total_downloaded >= max_total_bytes:
            records.append(PdfRecord(url, "", "skipped_total_limit", utc_now(), discovered_from=parent))
            continue
        temp = pdf_dir / f".partial-{index:04d}.pdf"
        try:
            response = request(session, url, args.delay, last_request)
            final_url = canonical(response.url)
            if not in_scope(final_url, origin):
                raise ValueError("redirected outside permitted origin")
            content_type = response.headers.get("Content-Type", "")
            expected = response.headers.get("Content-Length")
            if expected and int(expected) > max_pdf_bytes:
                records.append(PdfRecord(url, "", "skipped_file_limit", utc_now(), content_type, int(expected), discovered_from=parent))
                continue
            digest = hashlib.sha256()
            size = 0
            with temp.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_pdf_bytes:
                        raise ValueError(f"file exceeds {args.max_pdf_mb} MB limit")
                    if total_downloaded + size > max_total_bytes:
                        raise ValueError(f"total exceeds {args.max_total_mb} MB limit")
                    digest.update(chunk)
                    handle.write(chunk)
            header = temp.read_bytes()[:5]
            if header != b"%PDF-":
                raise ValueError("response is not a PDF signature")
            destination = unique_path(pdf_dir, safe_filename(final_url, index), url)
            temp.replace(destination)
            relative = destination.relative_to(output).as_posix()
            records.append(PdfRecord(url, relative, "downloaded", utc_now(), content_type, size, digest.hexdigest(), parent))
            total_downloaded += size
        except (requests.RequestException, OSError, ValueError) as error:
            temp.unlink(missing_ok=True)
            records.append(PdfRecord(url, "", "failed", utc_now(), discovered_from=parent, detail=str(error)))

    manifest_path.write_text(json.dumps([asdict(record) for record in records], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(PdfRecord("", "", "", "")).keys()))
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)
    summary = {
        "origin": origin,
        "retrieved_at": utc_now(),
        "robots_txt_available": robots_available,
        "pages_visited": len(visited_pages),
        "pdf_links_discovered": len(discovered),
        "records": len(records),
        "downloaded": sum(record.status == "downloaded" for record in records),
        "failed": sum(record.status == "failed" for record in records),
        "skipped": sum(record.status.startswith("skipped_") for record in records),
        "downloaded_bytes": total_downloaded,
        "limits": {"max_pdf_bytes": max_pdf_bytes, "max_total_bytes": max_total_bytes, "delay_seconds": args.delay},
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

