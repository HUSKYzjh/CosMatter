from __future__ import annotations

import json
import unittest
from pathlib import Path

from cosmatter.harness_catalog import default_cosmatter_plugin_catalogue


class DshPluginGroupTests(unittest.TestCase):
    def test_group_manifest_lists_installable_loopback_only_bundles(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "plugins" / "dsh-plugin-group.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "1.0")
        self.assertEqual(manifest["invariants"], [
            "loopback_only", "no_private_fulltext_or_credentials",
            "authorization_is_not_evidence_acceptance",
            "external_provider_dispatch_requires_durable_explicit_mission_consent",
            "no_private_fulltext_or_parser_output_from_dsh",
        ])
        packages = manifest["packages"]
        self.assertEqual([item["package"] for item in packages], ["@cosmatter/dsh-mission-plugin", "@cosmatter/dsh-observability-plugin", "@cosmatter/dsh-policy-plugin", "@cosmatter/dsh-research-plugin", "@cosmatter/dsh-review-plugin", "@cosmatter/dsh-document-plugin", "@cosmatter/dsh-graph-plugin"])
        for item in packages:
            package_dir = root / "plugins" / item["path"]
            package = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(package["name"], item["package"])
            self.assertEqual(package["dsh"]["bundle"]["patch"], "./cordis.patch.yml")
            self.assertEqual(package["files"], ["lib", "cordis.patch.yml", "README.md"])
            self.assertTrue((package_dir / "src" / "index.ts").is_file())
            self.assertTrue((package_dir / "lib" / "index.js").is_file())
            self.assertTrue((package_dir / "README.md").is_file())
            patch = package_dir / "cordis.patch.yml"
            self.assertTrue(patch.is_file())
            patch_text = patch.read_text(encoding="utf-8")
            self.assertIn(f"id: {item['plugin_id']}", patch_text)
            self.assertIn(f"name: '{item['package']}'", patch_text)
            self.assertIn("baseUrl: http://127.0.0.1:", patch_text)
            self.assertNotIn("https://", patch_text)
            self.assertNotIn("http://localhost", patch_text)

    def test_group_tools_do_not_overlap(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "plugins" / "dsh-plugin-group.json").read_text(encoding="utf-8"))
        tools = [tool for package in manifest["packages"] for tool in package["tools"]]
        self.assertEqual(len(tools), len(set(tools)))
        self.assertTrue(all(tool.startswith("cosmatter_") for tool in tools))

    def test_catalogue_coverage_is_complete_and_explicit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "plugins" / "dsh-plugin-group.json").read_text(encoding="utf-8"))
        package_names = {item["package"] for item in manifest["packages"]}
        coverage = manifest["catalogue_coverage"]
        descriptor_ids = [item["descriptor"] for item in coverage]
        self.assertEqual(len(descriptor_ids), len(set(descriptor_ids)))
        self.assertEqual(set(descriptor_ids), {item.plugin_id for item in default_cosmatter_plugin_catalogue()})
        for item in coverage:
            self.assertEqual(set(item), {"descriptor", "status", "bundle", "reason"})
            self.assertIn(item["status"], {"exposed", "python_or_human_boundary"})
            self.assertIsInstance(item["reason"], str)
            self.assertTrue(item["reason"].strip())
            if item["status"] == "exposed":
                self.assertIn(item["bundle"], package_names)
            else:
                self.assertIsNone(item["bundle"])


if __name__ == "__main__":
    unittest.main()
