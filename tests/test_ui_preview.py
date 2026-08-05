import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cosmatter.cli import main
from cosmatter.config import Settings
from cosmatter.local_api import LocalMissionApi
from cosmatter.ui_preview import UiPreviewError, build_ui_preview_server


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