"""Loopback-only preview server for the static, credential-free web UI."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Type

from .config import AGENT_ROOT


class UiPreviewError(ValueError):
    pass


def build_ui_preview_server(port: int = 8765, web_dir: Path | None = None) -> ThreadingHTTPServer:
    """Create, but do not start, a loopback-only server rooted at ``web/``."""
    if not isinstance(port, int) or not (port == 0 or 1024 <= port <= 65535):
        raise UiPreviewError("preview port must be 0 or between 1024 and 65535")
    directory = (web_dir or AGENT_ROOT / "web").resolve()
    if not directory.is_dir() or not (directory / "index.html").is_file():
        raise UiPreviewError("preview web directory is invalid")

    class PreviewHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'none'; form-action 'self'; base-uri 'none'")
            super().end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer(("127.0.0.1", port), PreviewHandler)


def serve_ui_preview(port: int = 8765) -> None:
    server = build_ui_preview_server(port)
    print(f"CosMatter UI preview: http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()
