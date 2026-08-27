#!/usr/bin/env python3
"""Run the private MinerU v4 batch tool with an exact signed PUT request.

The companion batch tool is intentionally reused for discovery, manifests, and
safe polling.  This wrapper replaces only the signed-upload transport so a
default ``urllib`` Content-Type cannot alter the provider's signed request.
"""

from __future__ import annotations

import http.client
import importlib.util
import sys
from pathlib import Path
from urllib.parse import urlsplit


SOURCE = Path(__file__).with_name("mineru_v4_private_batch.py")
SPEC = importlib.util.spec_from_file_location("cosmatter_mineru_v4_batch", SOURCE)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("Cannot load private MinerU batch implementation")
batch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = batch
SPEC.loader.exec_module(batch)


def raw_signed_put(settings: object, url: str, content: bytes) -> int:
    """PUT to the opaque HTTPS URL with Content-Length and no Content-Type."""
    target = urlsplit(url)
    if target.scheme != "https" or not target.hostname:
        return 0
    path = target.path + (f"?{target.query}" if target.query else "")
    timeout = getattr(settings, "http_timeout_seconds")
    connection = http.client.HTTPSConnection(target.hostname, target.port or 443, timeout=timeout)
    try:
        connection.putrequest("PUT", path, skip_accept_encoding=True)
        connection.putheader("Content-Length", str(len(content)))
        connection.endheaders(content)
        response = connection.getresponse()
        response.read()
        return int(response.status)
    except (http.client.HTTPException, TimeoutError, OSError):
        return 0
    finally:
        connection.close()


batch.signed_put = raw_signed_put

if __name__ == "__main__":
    raise SystemExit(batch.main())
