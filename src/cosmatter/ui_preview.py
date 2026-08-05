"""Loopback-only preview server for credential-free CosMatter interfaces."""

from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Type
from urllib.parse import urlsplit

from .config import AGENT_ROOT


class UiPreviewError(ValueError):
    pass


def _preview_directory(web_dir: Path | None, solid: bool) -> Path:
    default_directory = (AGENT_ROOT / "frontend" / "dist") if solid else (AGENT_ROOT / "web")
    directory = (web_dir or default_directory).resolve()
    if not directory.is_dir() or not (directory / "index.html").is_file():
        suffix = "; run npm run build in frontend first" if solid else ""
        raise UiPreviewError(f"preview web directory is invalid{suffix}")
    return directory

def build_ui_preview_server(
    port: int = 8765,
    web_dir: Path | None = None,
    *,
    solid: bool = False,
    ui_bundle: Path | None = None,
) -> ThreadingHTTPServer:
    """Create, but do not start, a loopback-only static UI server.

    When ``ui_bundle`` is supplied, only that already-redacted local JSON file
    is available at ``/ui.json``. This intentionally does not expose runs,
    audit logs, credentials, or arbitrary filesystem paths.
    """
    if not isinstance(port, int) or not (port == 0 or 1024 <= port <= 65535):
        raise UiPreviewError("preview port must be 0 or between 1024 and 65535")
    directory = _preview_directory(web_dir, solid)
    bundle_path: Path | None = None
    if ui_bundle is not None:
        bundle_path = ui_bundle.resolve()
        if not bundle_path.is_file() or bundle_path.name != "ui.json":
            raise UiPreviewError("preview UI bundle must be an existing ui.json file")

    class PreviewHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

        def do_GET(self) -> None:
            if urlsplit(self.path).path == "/ui.json":
                if bundle_path is None:
                    self.send_error(404, "No UI bundle was selected for this preview")
                    return
                payload = bundle_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            super().do_GET()

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            connect_source = "'self'" if bundle_path is not None else "'none'"
            self.send_header("Content-Security-Policy", f"default-src 'self'; connect-src {connect_source}; form-action 'self'; base-uri 'none'")
            super().end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer(("127.0.0.1", port), PreviewHandler)


def serve_ui_preview(port: int = 8765, *, solid: bool = False, ui_bundle: Path | None = None) -> None:
    server = build_ui_preview_server(port, solid=solid, ui_bundle=ui_bundle)
    suffix = " with selected UI bundle" if ui_bundle is not None else ""
    print(f"CosMatter UI preview: http://127.0.0.1:{port}/{suffix}")
    try:
        server.serve_forever()
    finally:
        server.server_close()