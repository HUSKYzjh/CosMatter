import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.config import data_root


class DataRootTests(unittest.TestCase):
    def test_uses_explicit_local_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"COSMATTER_DATA_ROOT": directory}
        ):
            self.assertEqual(data_root(), Path(directory).resolve())

    def test_uses_dedicated_workspace_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "development" / "CosMatter"
            runtime = workspace / "case-data" / "runtime"
            runtime.mkdir(parents=True)
            with patch("cosmatter.config.AGENT_ROOT", project), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(data_root(), runtime)


if __name__ == "__main__":
    unittest.main()
