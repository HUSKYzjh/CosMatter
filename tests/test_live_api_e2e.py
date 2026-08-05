import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from cosmatter.config import Settings
from cosmatter.local_api import LocalMissionApi
from cosmatter.ui_preview import build_ui_preview_server


class ProviderFixture(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.path == "/chat/completions":
            payload = {"model": "deepseek-fixture", "choices": [{"message": {"content": "untrusted plan draft"}}]}
        elif self.path == "/agentic-search":
            payload = {"hits": [{"doc_id": "fixture-paper", "title": "Fixture materials paper", "is_content_accessible": True}]}
        else:
            self.send_error(404)
            return
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("x-request-id", "provider-fixture")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        return


def post(url: str, payload: object) -> dict:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


class LiveApiEndToEndTests(unittest.TestCase):
    def test_loopback_ui_to_real_adapters_with_isolated_provider_fixture(self):
        provider = ThreadingHTTPServer(("127.0.0.1", 0), ProviderFixture)
        provider_thread = threading.Thread(target=provider.serve_forever, daemon=True)
        provider_thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                web = root / "web"
                web.mkdir()
                (web / "index.html").write_text("fixture UI", encoding="utf-8")
                base = f"http://127.0.0.1:{provider.server_port}"
                settings = Settings.load({
                    "LLM_PROVIDER": "deepseek", "LLM_MODEL": "deepseek-v4-flash", "DEEPSEEK_API_KEY": "fixture-deepseek-token",
                    "LLM_BASE_URL": base, "SCIVERSE_API_TOKEN": "fixture-sciverse-token", "SCIVERSE_BASE_URL": base,
                    "API_MAX_RETRIES": "1",
                })
                api = LocalMissionApi(root / "runs", settings_loader=lambda: settings)
                server = build_ui_preview_server(0, web, api=api)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    app = f"http://127.0.0.1:{server.server_port}"
                    created = post(f"{app}/api/missions", {"run_id": "e2e_live", "question": "map phase reports", "material": "BiFeO3", "property": "phase stability", "scope": "films"})
                    draft = post(f"{app}/api/runs/{created['run_id']}/draft-plan", {})
                    self.assertEqual(draft["trust_status"], "untrusted_draft")
                    approved = post(f"{app}/api/runs/e2e_live/approve-plan", {"subquestions": ["conditions"], "queries": ["BiFeO3 phase stability"], "counter_queries": ["BiFeO3 contradictory phases"]})
                    self.assertEqual(approved["queries"], ["BiFeO3 phase stability"])
                    result = post(f"{app}/api/runs/e2e_live/execute-query", {"query_index": 0, "counter": False})
                    self.assertEqual(result["candidates"][0]["document_id"], "fixture-paper")
                    with urlopen(f"{app}/api/runs/e2e_live/ui", timeout=3) as response:
                        bundle = response.read().decode("utf-8")
                    self.assertIn('"mission_id"', bundle)
                    graph = json.loads(bundle)["literature_graph"]
                    self.assertIn("candidate_paper", {node["kind"] for node in graph["nodes"]})
                    self.assertIn("retrieval_candidate", {edge["edge_type"] for edge in graph["edges"]})
                    self.assertNotIn("fixture-deepseek-token", bundle)
                    self.assertNotIn("fixture-sciverse-token", bundle)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)
        finally:
            provider.shutdown()
            provider.server_close()
            provider_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
