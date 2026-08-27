import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from cosmatter.submission_bundle import build_source_bundle


class SubmissionBundleTests(unittest.TestCase):
    def test_bundle_whitelists_sources_and_excludes_secrets_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "CosMatter"
            (root / "src" / "cosmatter").mkdir(parents=True)
            (root / "frontend" / "src").mkdir(parents=True)
            (root / "frontend" / "public" / "background-sources").mkdir(parents=True)
            (root / "configs").mkdir()
            (root / "runs" / "private").mkdir(parents=True)
            (root / "README.md").write_text("readme", encoding="utf-8")
            (root / "LICENSE").write_text("license", encoding="utf-8")
            (root / "SECURITY.md").write_text("security", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]", encoding="utf-8")
            (root / ".gitignore").write_text(".env", encoding="utf-8")
            (root / "src" / "cosmatter" / "main.py").write_text("pass", encoding="utf-8")
            (root / "frontend" / "package.json").write_text("{}", encoding="utf-8")
            (root / "frontend" / "src" / "app.ts").write_text("export {}", encoding="utf-8")
            (root / "configs" / "example.json").write_text("{}", encoding="utf-8")
            (root / ".env").write_text("secret=value", encoding="utf-8")
            (root / "runs" / "private" / "paper.pdf").write_bytes(b"private")
            (root / "frontend" / "public" / "background-sources" / "source.png").write_bytes(b"editable visual source")
            result = build_source_bundle(repository_root=root, output_path=root / "submission" / "source.zip")
            with zipfile.ZipFile(root / "submission" / "source.zip") as archive:
                names = archive.namelist()
                manifest = json.loads(archive.read("CosMatter/SUBMISSION_BUNDLE_MANIFEST.json"))
        self.assertTrue(result["bundle_sha256"])
        self.assertIn("CosMatter/src/cosmatter/main.py", names)
        self.assertNotIn("CosMatter/.env", names)
        self.assertFalse(any("runs/" in name for name in names))
        self.assertNotIn("CosMatter/frontend/public/background-sources/source.png", names)
        self.assertEqual(manifest["source_file_count"], result["source_file_count"])


if __name__ == "__main__":
    unittest.main()
