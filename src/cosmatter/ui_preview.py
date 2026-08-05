"""Loopback-only preview server for credential-free CosMatter interfaces."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from .config import AGENT_ROOT
from .local_api import LocalApiError, LocalMissionApi


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
    api: LocalMissionApi | None = None,
) -> ThreadingHTTPServer:
    """Create, but do not start, a loopback-only static UI server.

    ``ui_bundle`` exposes only one already-redacted UI bundle at ``/ui.json``.
    ``api`` exposes a small allowlisted local application API under ``/api``.
    Neither route exposes runs, audit logs, credentials, raw provider payloads,
    or arbitrary filesystem paths.
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
            path = urlsplit(self.path).path
            if path == "/api/status":
                self._api_json(lambda: api.status() if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/ui")
            if run_id is not None:
                self._api_bytes(lambda: api.ui_bundle(run_id) if api is not None else _api_disabled())
                return
            if path.startswith("/api/"):
                self.send_error(404, "Unknown local API route")
                return
            if path == "/ui.json":
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

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path == "/api/missions":
                self._api_json(lambda: api.create_mission(self._json_body()) if api is not None else _api_disabled(), status=201)
                return
            run_id = _api_run_id(path, "/api/runs/", "/draft-plan")
            if run_id is not None:
                self._api_json(lambda: api.draft_plan(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/approve-plan")
            if run_id is not None:
                self._api_json(lambda: api.approve_plan(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/execute-query")
            if run_id is not None:
                self._api_json(lambda: api.execute_plan_query(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            self.send_error(404, "Unknown local API route")

        def _json_body(self) -> object:
            try:
                size = int(self.headers.get("Content-Length") or "0")
            except ValueError as error:
                raise LocalApiError("Content-Length must be an integer") from error
            if not 0 < size <= 48_000:
                raise LocalApiError("request body must be between 1 and 48000 bytes")
            try:
                return json.loads(self.rfile.read(size).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise LocalApiError("request body must be valid UTF-8 JSON") from error

        def _api_json(self, operation: Callable[[], object], status: int = 200) -> None:
            try:
                body = json.dumps(operation(), ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except LocalApiError as error:
                self._api_error(error.status, str(error))

        def _api_bytes(self, operation: Callable[[], object]) -> None:
            try:
                body = operation()
                if not isinstance(body, bytes):
                    raise LocalApiError("local API did not return a valid response", 500)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except LocalApiError as error:
                self._api_error(error.status, str(error))

        def _api_error(self, status: int, message: str) -> None:
            body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            connect_source = "'self'" if bundle_path is not None or api is not None else "'none'"
            self.send_header("Content-Security-Policy", f"default-src 'self'; connect-src {connect_source}; form-action 'self'; base-uri 'none'")
            super().end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer(("127.0.0.1", port), PreviewHandler)


def _api_disabled() -> object:
    raise LocalApiError("local API mode was not enabled", 404)


def _api_run_id(path: str, prefix: str, suffix: str) -> str | None:
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    candidate = path[len(prefix) : len(path) - len(suffix)]
    if not candidate or "/" in candidate:
        return None
    return candidate


def serve_ui_preview(port: int = 8765, *, solid: bool = False, ui_bundle: Path | None = None, api: bool = False) -> None:
    server = build_ui_preview_server(
        port, solid=solid, ui_bundle=ui_bundle, api=LocalMissionApi.from_project() if api else None
    )
    suffix = " with local API" if api else ""
    suffix += " and selected UI bundle" if ui_bundle is not None else ""
    print(f"CosMatter UI preview: http://127.0.0.1:{port}/{suffix}")
    try:
        server.serve_forever()
    finally:
        server.server_close()