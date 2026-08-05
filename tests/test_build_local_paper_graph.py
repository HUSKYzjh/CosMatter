import importlib.util
import tempfile
import unittest
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_local_paper_graph.py"
    spec = importlib.util.spec_from_file_location("local_paper_graph", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalPaperGraphTests(unittest.TestCase):
    def test_inventory_is_bounded_balanced_and_path_safe(self) -> None:
        module = _module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "library"
            for collection in ("A", "B"):
                folder = root / collection
                folder.mkdir(parents=True)
                for index in range(4):
                    (folder / f"202{index} - {collection} paper {index}.pdf").write_bytes(b"%PDF")
            bundle = module.build_bundle(root, 6)
        graph = bundle["literature_graph"]
        nodes = graph["nodes"]
        papers = [node for node in nodes if node["kind"] == "candidate_paper"]
        collections = [node for node in nodes if node["kind"] == "local_collection"]
        self.assertEqual(len(papers), 6)
        self.assertEqual(len(collections), 2)
        self.assertEqual({paper["publication_year"] for paper in papers}, {2020, 2021, 2022})
        self.assertNotIn(str(root), str(bundle))
        self.assertTrue(all(paper["is_content_accessible"] is False for paper in papers))


if __name__ == "__main__":
    unittest.main()
