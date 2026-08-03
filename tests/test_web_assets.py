import unittest
from html.parser import HTMLParser
from pathlib import Path

from cosmatter.config import AGENT_ROOT


class _AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "link" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"] or "")


class WebAssetTests(unittest.TestCase):
    def test_static_ui_references_local_assets_and_has_no_secret_markers(self) -> None:
        web_dir = AGENT_ROOT / "web"
        html = (web_dir / "index.html").read_text(encoding="utf-8")
        parser = _AssetParser()
        parser.feed(html)
        self.assertEqual(parser.links, ["styles.css"])
        self.assertEqual(parser.scripts, ["app.js"])
        self.assertTrue((web_dir / "styles.css").is_file())
        self.assertTrue((web_dir / "app.js").is_file())
        self.assertNotIn("DEEPSEEK_API_KEY", html)
        self.assertNotIn("SCIVERSE_API_TOKEN", html)
        self.assertNotIn("fetch(", (web_dir / "app.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
