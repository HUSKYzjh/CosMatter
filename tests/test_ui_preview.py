import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cosmatter.cli import main
from cosmatter.config import Settings
from cosmatter.deepseek import DraftCompletion
from cosmatter.local_api import LocalMissionApi
from cosmatter.mineru import MinerUBatch
from cosmatter.sciverse import SciverseResponse
from cosmatter.ui_preview import UiPreviewError, build_ui_preview_server


class _HttpFakeSciverse:
    def __init__(self, _settings):
        pass

    def agentic_search(self, _query, *, top_k):
        return SciverseResponse(
            payload={"hits": [{"doc_id": "http-doc", "title": "HTTP candidate", "is_content_accessible": True, "score": 0.9}]},
            status_code=200,
            request_id="http-search",
        )


class _HttpFakeDeepSeek:
    def __init__(self, _settings):
        pass

    def draft(self, *, system_prompt, user_prompt):
        return DraftCompletion(
            content='{"queries": ["BiFeO3 phase stability"]}',
            model="test-deepseek",
            request_id="http-plan",
        )


class _HttpFakeMinerU:
    def __init__(self, _settings):
        pass

    def submit_local_file(self, _file_name, _content):
        return MinerUBatch(batch_id="http-batch", upload_url="redacted", state="pending")


class UiPreviewTests(unittest.TestCase):
    def _server(self, web: Path, bundle: Path | None = None):
        server = build_ui_preview_server(0, web, ui_bundle=bundle)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_serves_only_loopback_static_ui_with_security_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            web = Path(directory)
            (web / "index.html").write_text("<h1>preview</h1>", encoding="utf-8")
            server, thread = self._server(web)
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=2) as response:
                    self.assertIn(b"preview", response.read())
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertIn("connect-src 'none'", response.headers["Content-Security-Policy"])
                with self.assertRaises(HTTPError) as context:
                    urlopen(f"http://127.0.0.1:{server.server_port}/ui.json", timeout=2)
                self.assertEqual(context.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_serves_only_the_explicit_redacted_ui_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("<h1>solid</h1>", encoding="utf-8")
            bundle = root / "ui.json"
            bundle.write_text('{"schema_version":"1.0","mission":{"mission_id":"m"}}', encoding="utf-8")
            server, thread = self._server(web, bundle)
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/ui.json", timeout=2) as response:
                    self.assertIn(b'"mission_id":"m"', response.read())
                    self.assertIn("application/json", response.headers["Content-Type"])
                    self.assertIn("connect-src 'self'", response.headers["Content-Security-Policy"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_http_candidate_screening_then_authorized_pdf_stays_in_same_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("<h1>preview</h1>", encoding="utf-8")
            api = LocalMissionApi(
                root / "runs",
                settings_loader=lambda: Settings.load(
                    {"LLM_PROVIDER": "deepseek", "LLM_MODEL": "test", "DEEPSEEK_API_KEY": "test", "SCIVERSE_API_TOKEN": "test", "MINERU_API_TOKEN": "test"}
                ),
            )
            api.create_mission({"run_id": "http_flow", "question": "map conditions", "material": "BiFeO3", "property": "phase stability", "scope": "films"})
            api.approve_plan("http_flow", {"subquestions": ["Which conditions differ?"], "queries": ["BiFeO3 phase stability"], "counter_queries": ["BiFeO3 counterevidence"]})
            with patch("cosmatter.local_api.SciverseAdapter", _HttpFakeSciverse):
                api.execute_plan_query("http_flow", {"query_index": 0, "counter": False})
            server = build_ui_preview_server(0, web, api=api)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(f"{base}/api/runs/http_flow/candidate-screening", timeout=2) as response:
                    checklist = json.loads(response.read().decode("utf-8"))
                self.assertEqual(checklist["decisions"][0]["decision"], "unreviewed")
                screening = Request(
                    f"{base}/api/runs/http_flow/candidate-screening",
                    data=json.dumps({"decisions": [{"document_id": "http-doc", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(screening, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                boundary = "CosMatterBoundary"
                multipart = (
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload\"\r\n\r\n"
                    + json.dumps({"run_id": "http_flow", "candidate_document_id": "http-doc", "consent": True})
                    + f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"authorized.pdf\"\r\nContent-Type: application/pdf\r\n\r\n"
                ).encode("utf-8") + b"%PDF-1.7 test\r\n" + f"--{boundary}--\r\n".encode("utf-8")
                upload = Request(
                    f"{base}/api/pdf-runs",
                    data=multipart,
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                    method="POST",
                )
                with patch("cosmatter.local_api.MinerUAdapter", _HttpFakeMinerU), patch("cosmatter.local_api.write_pdf", return_value=(Path("private.pdf"), "digest")):
                    with urlopen(upload, timeout=2) as response:
                        result = json.loads(response.read().decode("utf-8"))
                self.assertEqual(result["run_id"], "http_flow")
                self.assertEqual(result["candidate_document_id"], "http-doc")
                registry_path = root / "runs" / "http_flow" / "pdf_intake_tasks.json"
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                intake = registry["tasks"][0]
                intake["state"] = "done"; intake["markdown_sha256"] = "a" * 64
                registry["tasks"][0] = intake
                registry_path.write_text(json.dumps(registry), encoding="utf-8")
                source_map_request = Request(
                    f"{base}/api/runs/http_flow/pdf/source-map",
                    data=json.dumps({"human_confirmed": True, "segments": [{"locator": "markdown_line:2-2", "kind": "paragraph", "quote": "Human-checked evidence line."}]}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with patch("cosmatter.local_api.read_markdown", return_value=b"# Title\nHuman-checked evidence line.\n"):
                    with urlopen(source_map_request, timeout=2) as response:
                        source_map_result = json.loads(response.read().decode("utf-8"))
                self.assertEqual(source_map_result["document_id"], "http-doc")
                self.assertEqual(source_map_result["segment_count"], 1)
                self.assertNotIn("Human-checked evidence line.", json.dumps(source_map_result))
                with urlopen(f"{base}/api/runs/http_flow/pdf/source-map", timeout=2) as response:
                    restored_source_map = json.loads(response.read().decode("utf-8"))
                self.assertEqual(restored_source_map["segments"][0]["segment_id"], "private_md_001")
                self.assertNotIn("Human-checked evidence line.", json.dumps(restored_source_map))
                material_facts_request = Request(
                    f"{base}/api/runs/http_flow/pdf/material-facts",
                    data=json.dumps({"human_confirmed": True, "facts": [{"fact_id": "http_phase", "segment_id": "private_md_001", "category": "property", "name": "phase boundary", "value": "shifts", "unit": None, "normalized_value": "shifts", "normalized_unit": None, "qualifiers": {}}]}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urlopen(material_facts_request, timeout=2) as response:
                    material_facts_result = json.loads(response.read().decode("utf-8"))
                self.assertEqual(material_facts_result["document_id"], "http-doc")
                self.assertEqual(material_facts_result["fact_count"], 1)
                evidence_request = Request(
                    f"{base}/api/runs/http_flow/pdf/evidence-card",
                    data=json.dumps({"human_confirmed": True, "segment_id": "private_md_001", "claim": "Human-reviewed located claim", "stance": "support", "conditions": {"sample_form": "film", "strain_percent": 0, "substrate": "synthetic", "thickness_nm": 10, "temperature_k": 300, "method": "xrd"}, "reviewer_confidence": 0.8}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urlopen(evidence_request, timeout=2) as response:
                    evidence_result = json.loads(response.read().decode("utf-8"))
                self.assertEqual(evidence_result["review_status"], "accepted")
                self.assertNotIn("Human-checked evidence line.", json.dumps(evidence_result))
                with urlopen(f"{base}/api/runs/http_flow/ui", timeout=2) as response:
                    hydrated_ui = json.loads(response.read().decode("utf-8"))
                self.assertEqual(hydrated_ui["evidence_cards"][0]["review_status"], "accepted")
                self.assertEqual(hydrated_ui["evidence_cards"][0]["provenance"]["document_id"], "http-doc")
                self.assertTrue(any(edge["source_id"] == "paper:http-doc" and edge["target_id"] == f"evidence:{evidence_result["evidence_id"]}" and edge["edge_type"] == "source_provenance" for edge in hydrated_ui["literature_graph"]["edges"]))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
    def test_cli_rejects_path_traversal_before_starting_preview(self) -> None:
        self.assertEqual(main(["preview-ui", "--solid", "--run-id", "../not-a-run", "--port", "8876"]), 2)

    def test_rejects_non_user_ports_and_non_ui_bundle_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            web = Path(directory)
            (web / "index.html").write_text("preview", encoding="utf-8")
            with self.assertRaises(UiPreviewError):
                build_ui_preview_server(80, web)
            other = web / "private.json"
            other.write_text("{}", encoding="utf-8")
            with self.assertRaises(UiPreviewError):
                build_ui_preview_server(0, web, ui_bundle=other)

    def test_auto_mission_route_uses_harness_authorization_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("preview", encoding="utf-8")
            api = LocalMissionApi(root / "runs")
            server = build_ui_preview_server(0, web, api=api)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/missions/auto",
                    data=json.dumps({
                        "question": "How do growth conditions change phase stability in BiFeO3 films?",
                        "material": "BiFeO3",
                        "property": "phase stability",
                        "scope": "epitaxial films",
                        "consent": True,
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                authorized = {
                    "run_id": "auto_http_001",
                    "trust_status": "metadata_only_automatic_run",
                    "harness_authorization": {"trust_status": "authorization_checked_before_automatic_dispatch"},
                }
                with patch("cosmatter.ui_preview.run_authorized_automatic_mission", return_value=authorized) as dispatch:
                    with urlopen(request, timeout=2) as response:
                        body = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 201)
                self.assertEqual(body["run_id"], "auto_http_001")
                self.assertIn("harness_authorization", body)
                self.assertIs(dispatch.call_args.args[0], api)
                self.assertTrue(dispatch.call_args.args[1]["consent"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
    def test_auto_mission_route_runs_harness_checked_metadata_job(self) -> None:
        """The public loopback route keeps the Harness decision and evidence boundary."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("preview", encoding="utf-8")
            api = LocalMissionApi(
                root / "runs",
                settings_loader=lambda: Settings.load(
                    {
                        "LLM_PROVIDER": "deepseek",
                        "LLM_MODEL": "test",
                        "DEEPSEEK_API_KEY": "private-test-token",
                        "SCIVERSE_API_TOKEN": "private-sciverse-token",
                    }
                ),
            )
            server = build_ui_preview_server(0, web, api=api)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                request = Request(
                    f"{base}/api/missions/auto",
                    data=json.dumps(
                        {
                            "run_id": "auto_http_real",
                            "question": "How do growth conditions change phase stability in BiFeO3 films?",
                            "material": "BiFeO3",
                            "property": "phase stability",
                            "scope": "epitaxial films",
                            "sources": ["sciverse"],
                            "consent": True,
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with patch("cosmatter.local_api.DeepSeekAdapter", _HttpFakeDeepSeek), patch(
                    "cosmatter.local_api.SciverseAdapter", _HttpFakeSciverse
                ):
                    with urlopen(request, timeout=2) as response:
                        created = json.loads(response.read().decode("utf-8"))
                    authorization = created["harness_authorization"]
                    self.assertEqual(created["run_id"], "auto_http_real")
                    self.assertEqual(
                        authorization["trust_status"], "authorization_checked_before_automatic_dispatch"
                    )
                    self.assertTrue(all(item["permitted"] for item in authorization["plugin_authorization_decisions"]))
                    for _ in range(100):
                        with urlopen(f"{base}/api/runs/auto_http_real/status", timeout=2) as response:
                            status = json.loads(response.read().decode("utf-8"))
                        if status["automatic_execution"]["state"] in {"succeeded", "failed", "cancelled"}:
                            break
                        time.sleep(0.01)
                self.assertEqual(status["automatic_execution"]["state"], "succeeded")
                self.assertEqual(status["automatic_execution"]["candidate_count"], 1)
                with urlopen(f"{base}/api/runs/auto_http_real/ui", timeout=2) as response:
                    ui_bundle = json.loads(response.read().decode("utf-8"))
                node_kinds = {node["kind"] for node in ui_bundle["literature_graph"]["nodes"]}
                self.assertNotIn("accepted_evidence", node_kinds)
                with urlopen(f"{base}/api/runs/auto_http_real/candidate-screening", timeout=2) as response:
                    checklist = json.loads(response.read().decode("utf-8"))
                self.assertEqual(checklist["candidate_count"], 1)
                self.assertEqual(checklist["decisions"][0]["decision"], "unreviewed")
                self.assertEqual(
                    checklist["trust_status"], "blank_human_candidate_screening_template_not_a_result"
                )
                audit_lines = (root / "runs" / "auto_http_real" / "events.jsonl").read_text(encoding="utf-8").splitlines()
                events = [json.loads(line)["event_type"] for line in audit_lines]
                self.assertIn("harness_authorization_checked", events)
                self.assertIn("automatic_metadata_query_executed", events)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_local_api_is_opt_in_loopback_only_and_never_returns_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web = root / "web"
            web.mkdir()
            (web / "index.html").write_text("preview", encoding="utf-8")
            api = LocalMissionApi(
                root / "runs",
                settings_loader=lambda: Settings.load(
                    {"LLM_PROVIDER": "deepseek", "LLM_MODEL": "test", "DEEPSEEK_API_KEY": "private-test-token"}
                ),
            )
            server = build_ui_preview_server(0, web, api=api)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(f"{base}/api/status", timeout=2) as response:
                    payload = response.read().decode("utf-8")
                    self.assertIn('"deepseek": true', payload)
                    self.assertNotIn("private-test-token", payload)
                    self.assertIn("connect-src 'self'", response.headers["Content-Security-Policy"])
                request = Request(
                    f"{base}/api/missions",
                    data=b'{"run_id":"http_live","question":"map conditions","material":"BiFeO3","property":"phase stability","scope":"films"}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=2) as response:
                    self.assertEqual(response.status, 201)
                    self.assertIn(b'"run_id": "http_live"', response.read())
                with self.assertRaises(HTTPError) as context:
                    urlopen(f"{base}/api/runs/../../.env/ui", timeout=2)
                self.assertEqual(context.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
