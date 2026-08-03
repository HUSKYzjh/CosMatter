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
    def test_static_fleet_pages_reference_only_local_assets_and_have_no_secret_markers(self) -> None:
        web_dir = AGENT_ROOT / "web"
        expected_scripts = {
            "index.html": ["shell.js", "app.js"],
            "workflow.html": ["shell.js", "workflow.js"],
            "network.html": ["shell.js", "network.js"],
            "paper.html": ["shell.js", "paper.js"],
            "extensions.html": ["shell.js", "extensions.js"],
        }
        for page, scripts in expected_scripts.items():
            html = (web_dir / page).read_text(encoding="utf-8")
            parser = _AssetParser()
            parser.feed(html)
            self.assertEqual(parser.links, ["styles.css"])
            self.assertEqual(parser.scripts, scripts)
            self.assertIn('data-theme-select', html)
            self.assertNotIn("DEEPSEEK_API_KEY", html)
            self.assertNotIn("SCIVERSE_API_TOKEN", html)
        for script in {script for scripts in expected_scripts.values() for script in scripts}:
            source = (web_dir / script).read_text(encoding="utf-8")
            self.assertNotIn("fetch(", source)
            self.assertNotIn("DEEPSEEK_API_KEY", source)
            self.assertNotIn("SCIVERSE_API_TOKEN", source)
        workflow_html = (web_dir / "workflow.html").read_text(encoding="utf-8")
        workflow_script = (web_dir / "workflow.js").read_text(encoding="utf-8")
        self.assertIn('id="reading-guide-cards"', workflow_html)
        self.assertIn("function renderReadingGuide(guide)", workflow_script)
        network_html = (web_dir / "network.html").read_text(encoding="utf-8")
        network_script = (web_dir / "network.js").read_text(encoding="utf-8")
        self.assertIn("graph-legend", network_html)
        paper_html = (web_dir / "paper.html").read_text(encoding="utf-8")
        paper_script = (web_dir / "paper.js").read_text(encoding="utf-8")
        self.assertIn('id="paper-guide-select"', paper_html)
        self.assertIn("function renderPaper(bundle)", paper_script)
        for semantic_edge in ("retrieval_candidate", "source_provenance", "support", "contradict", "open_question"):
            self.assertIn(semantic_edge, network_script)
        stylesheet = (web_dir / "styles.css").read_text(encoding="utf-8")
        for theme in ('data-theme="dark"', 'data-theme="light"', 'data-theme="eye"'):
            self.assertIn(theme, stylesheet)


if __name__ == "__main__":
    unittest.main()
