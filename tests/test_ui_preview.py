import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from cosmatter.cli import main
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