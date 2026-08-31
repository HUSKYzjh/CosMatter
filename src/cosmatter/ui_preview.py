"""Loopback-only preview server for credential-free CosMatter interfaces."""

from __future__ import annotations

import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from .config import AGENT_ROOT
from .harness_autorun import HarnessAutoRunError, run_authorized_automatic_mission
from .local_api import LocalApiError, LocalMissionApi
from .artifact_contract import ArtifactDownload


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
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/api/status":
                self._api_json(lambda: api.status() if api is not None else _api_disabled())
                return
            if path == "/api/plugins":
                self._api_json(lambda: api.plugin_catalogue() if api is not None else _api_disabled())
                return
            if path == "/api/facility-contracts":
                self._api_json(lambda: api.facility_contract_catalogue() if api is not None else _api_disabled())
                return
            if path == "/api/reminder-board":
                self._api_json(lambda: api.reminder_board() if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/status")
            if run_id is not None:
                self._api_json(lambda: api.run_status(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/workflow-status")
            if run_id is not None:
                self._api_json(lambda: api.workflow_status(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/stage-contract")
            if run_id is not None:
                self._api_json(lambda: api.stage_contract(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/operational-telemetry")
            if run_id is not None:
                self._api_json(lambda: api.operational_telemetry(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/workflow-dag")
            if run_id is not None:
                self._api_json(lambda: api.workflow_dag(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/artifacts")
            if run_id is not None:
                self._api_json(lambda: api.approved_artifacts(run_id) if api is not None else _api_disabled())
                return
            match = re.fullmatch(r"/api/runs/([A-Za-z0-9][A-Za-z0-9_-]*)/artifacts/(ui_bundle|graph_snapshot|workflow_readiness|runtime_invariants|mission_report|research_report)", path)
            if match:
                self._api_artifact(lambda: api.approved_artifact_download(match.group(1), match.group(2)) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/ui")
            if run_id is not None:
                self._api_bytes(lambda: api.ui_bundle(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/graph")
            if run_id is not None:
                self._api_json(lambda: api.graph_projection(run_id, **_graph_query(parsed.query)) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/candidate-screening")
            if run_id is not None:
                self._api_json(lambda: api.candidate_screening_template(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/pdf/tasks")
            if run_id is not None:
                self._api_json(lambda: api.pdf_tasks(run_id) if api is not None else _api_disabled())
                return
            match = re.fullmatch(r"/api/runs/([A-Za-z0-9][A-Za-z0-9_-]*)/pdf/(pdf_[a-f0-9]{24})/(status|source-map)", path)
            if match:
                operation = match.group(3)
                self._api_json(lambda: api.pdf_status(match.group(1), match.group(2)) if operation == "status" and api is not None else api.pdf_source_map_context(match.group(1), match.group(2)) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/pdf/source-map")
            if run_id is not None:
                self._api_json(lambda: api.pdf_source_map_context(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/pdf/status")
            if run_id is not None:
                self._api_json(lambda: api.pdf_status(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/package")
            if run_id is not None:
                self._api_bytes(lambda: api.export_run_package(run_id) if api is not None else _api_disabled())
                return
            match = re.fullmatch(r"/api/runs/([A-Za-z0-9][A-Za-z0-9_-]*)/pdf/(pdf_[a-f0-9]{24})/markdown", path)
            if match:
                self._api_bytes(lambda: api.private_markdown(match.group(1), match.group(2)) if api is not None else _api_disabled())
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
            if path == "/api/question-candidates":
                self._api_json(lambda: api.question_candidates(self._json_body()) if api is not None else _api_disabled())
                return
            if path == "/api/missions/auto":
                self._api_json(
                    lambda: self._authorized_auto_mission(self._json_body()) if api is not None else _api_disabled(),
                    status=201,
                )
                return
            if path == "/api/pdf-runs":
                payload, file_name, content = self._pdf_upload_body()
                self._api_json(lambda: api.create_pdf_run(payload, file_name, content) if api is not None else _api_disabled(), status=201)
                return
            if path == "/api/runs/import":
                self._api_json(lambda: api.import_run_package(self._json_body()) if api is not None else _api_disabled(), status=201)
                return
            if path == "/api/missions":
                self._api_json(lambda: api.create_mission(self._json_body()) if api is not None else _api_disabled(), status=201)
                return
            run_id = _api_run_id(path, "/api/runs/", "/plugin-authorization-plan")
            if run_id is not None:
                self._api_json(lambda: api.plan_plugin_authorization(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/candidate-screening")
            if run_id is not None:
                self._api_json(lambda: api.record_candidate_screening(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            match = re.fullmatch(r"/api/runs/([A-Za-z0-9][A-Za-z0-9_-]*)/pdf/(pdf_[a-f0-9]{24})/citations", path)
            if match:
                self._api_json(_legacy_external_dispatch_disabled)
                return
            run_id = _api_run_id(path, "/api/runs/", "/pdf/source-map")
            if run_id is not None:
                self._api_json(lambda: api.record_pdf_source_map(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/pdf/material-facts")
            if run_id is not None:
                self._api_json(lambda: api.record_pdf_material_facts(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/pdf/evidence-card")
            if run_id is not None:
                self._api_json(lambda: api.record_pdf_evidence_card(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/pdf/doi")
            if run_id is not None:
                self._api_json(lambda: api.confirm_pdf_doi(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/condition-diagnostics")
            if run_id is not None:
                self._api_json(lambda: api.diagnose_conditions(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/gap-candidates")
            if run_id is not None:
                self._api_json(lambda: api.generate_gap_candidates(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/citations")
            if run_id is not None:
                self._api_json(_legacy_external_dispatch_disabled)
                return
            run_id = _api_run_id(path, "/api/runs/", "/authorized-citation-expansion")
            if run_id is not None:
                self._api_json(lambda: api.expand_authorized_pdf_citations(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/cancel")
            if run_id is not None:
                self._api_json(lambda: api.cancel(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/draft-plan")
            if run_id is not None:
                self._api_json(_legacy_external_dispatch_disabled)
                return
            run_id = _api_run_id(path, "/api/runs/", "/authorized-draft-plan")
            if run_id is not None:
                self._api_json(lambda: api.draft_authorized_plan(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/approve-plan")
            if run_id is not None:
                self._api_json(lambda: api.approve_plan(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/execute-query")
            if run_id is not None:
                self._api_json(_legacy_external_dispatch_disabled)
                return
            run_id = _api_run_id(path, "/api/runs/", "/authorized-execute-query")
            if run_id is not None:
                self._api_json(lambda: api.execute_authorized_plan_query(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/authorized-mineru-submit")
            if run_id is not None:
                self._api_json(lambda: api.submit_authorized_mineru_source(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/authorized-mineru-poll")
            if run_id is not None:
                self._api_json(lambda: api.poll_authorized_mineru_source(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/accepted-evidence/search")
            if run_id is not None:
                self._api_json(lambda: api.search_accepted_evidence(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/graph/project")
            if run_id is not None:
                self._api_json(lambda: api.project_accepted_evidence_graph(run_id) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/graph/review-request")
            if run_id is not None:
                self._api_json(lambda: api.request_graph_review(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/graph/plan-draft")
            if run_id is not None:
                self._api_json(lambda: api.draft_graph_plan(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/graph/model-plan-draft")
            if run_id is not None:
                self._api_json(_legacy_external_dispatch_disabled)
                return
            run_id = _api_run_id(path, "/api/runs/", "/graph/authorized-model-plan-draft")
            if run_id is not None:
                self._api_json(lambda: api.assist_authorized_graph_plan(run_id, self._json_body()) if api is not None else _api_disabled())
                return
            run_id = _api_run_id(path, "/api/runs/", "/graph/plan-approval")
            if run_id is not None:
                self._api_json(lambda: api.approve_graph_plan(run_id, self._json_body()) if api is not None else _api_disabled())
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

        def _pdf_upload_body(self) -> tuple[object, str, bytes]:
            """Accept one bounded multipart PDF without forwarding a signed URL."""
            content_type = self.headers.get("Content-Type") or ""
            match = re.search(r"boundary=([^;]+)", content_type)
            if not match:
                raise LocalApiError("PDF upload must use multipart/form-data")
            try:
                size = int(self.headers.get("Content-Length") or "0")
            except ValueError as error:
                raise LocalApiError("Content-Length must be an integer") from error
            if not 0 < size <= 200 * 1024 * 1024 + 64_000:
                raise LocalApiError("PDF upload exceeds 200 MB")
            boundary = b"--" + match.group(1).strip().strip('"').encode("ascii")
            body: object | None = None; file_name: str | None = None; content: bytes | None = None
            for part in self.rfile.read(size).split(boundary):
                if b"\r\n\r\n" not in part:
                    continue
                headers, value = part.split(b"\r\n\r\n", 1)
                if value.endswith(b"\r\n"):
                    value = value[:-2]
                disposition = headers.decode("utf-8", errors="ignore")
                if 'name="payload"' in disposition:
                    try:
                        body = json.loads(value.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise LocalApiError("PDF upload payload is invalid JSON") from error
                elif 'name="file"' in disposition:
                    name = re.search(r'filename="([^"\\]+)"', disposition)
                    if name:
                        file_name, content = name.group(1), value
            if body is None or file_name is None or content is None:
                raise LocalApiError("PDF upload must include payload and file")
            return body, file_name, content
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

        def _api_artifact(self, operation: Callable[[], object]) -> None:
            try:
                artifact = operation()
                if not isinstance(artifact, ArtifactDownload):
                    raise LocalApiError("local API did not return an approved artifact", 500)
                self.send_response(200)
                self.send_header("Content-Type", artifact.media_type)
                self.send_header("Content-Disposition", f'attachment; filename="{artifact.filename}"')
                self.send_header("Content-Length", str(len(artifact.data)))
                self.end_headers()
                self.wfile.write(artifact.data)
            except LocalApiError as error:
                self._api_error(error.status, str(error))

        def _authorized_auto_mission(self, payload: object) -> dict[str, object]:
            """Run the automatic route through its one-time Harness policy gate."""
            if api is None:
                return _api_disabled()  # pragma: no cover - guarded by the route
            try:
                return run_authorized_automatic_mission(api, payload)
            except HarnessAutoRunError as error:
                raise LocalApiError(str(error), 400) from error
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

    class PreviewServer(ThreadingHTTPServer):
        """Wait for an in-flight local request before its temporary root closes.

        ``ThreadingHTTPServer`` defaults to daemon request threads.  On Windows
        that can leave an ``index.html`` handle open after ``server_close()``,
        which makes a short-lived preview root impossible to clean up during
        tests or controlled preview shutdown.  These settings preserve
        loopback-only behaviour while making shutdown deterministic.
        """

        daemon_threads = False
        block_on_close = True
        allow_reuse_address = True

    return PreviewServer(("127.0.0.1", port), PreviewHandler)


def _api_disabled() -> object:
    raise LocalApiError("local API mode was not enabled", 404)


def _legacy_external_dispatch_disabled() -> object:
    raise LocalApiError("legacy external dispatch is disabled; use the explicit authorization endpoint", 410)


def _api_run_id(path: str, prefix: str, suffix: str) -> str | None:
    if not path.startswith(prefix) or not path.endswith(suffix):
        return None
    candidate = path[len(prefix) : len(path) - len(suffix)]
    if not candidate or "/" in candidate:
        return None
    return candidate


def _graph_query(query: str) -> dict[str, object]:
    """Parse a tiny allowlist of bounded graph-page arguments."""
    values = parse_qs(query, keep_blank_values=True, strict_parsing=True)
    if set(values) - {"node_type", "offset", "limit"}:
        raise LocalApiError("unsupported graph query parameter")
    types = values.get("node_type", [])
    if any(not item or len(item) > 32 for item in types):
        raise LocalApiError("graph node_type is invalid")
    parsed: dict[str, object] = {"node_types": tuple(types)}
    for key in ("offset", "limit"):
        raw = values.get(key)
        if raw is None:
            continue
        if len(raw) != 1 or not raw[0].isdigit():
            raise LocalApiError(f"graph {key} is invalid")
        parsed[key] = int(raw[0])
    return parsed


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
