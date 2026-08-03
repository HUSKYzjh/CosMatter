import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from cosmatter.ui_preview import UiPreviewError, build_ui_preview_server


class UiPreviewTests(unittest.TestCase):
    def test_serves_only_loopback_static_ui_with_security_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            web = Path(directory); (web / "index.html").write_text("<h1>preview</h1>", encoding="utf-8")
            server = build_ui_preview_server(0, web)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=2) as response:
                    self.assertIn(b"preview", response.read())
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertIn("connect-src 'none'", response.headers["Content-Security-Policy"])
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_rejects_non_user_ports(self) -> None:
        with self.assertRaises(UiPreviewError):
            build_ui_preview_server(80)
