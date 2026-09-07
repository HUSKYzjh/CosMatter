import contextlib
import io
import unittest

from cosmatter.cli import main


class CliHelpTests(unittest.TestCase):
    def test_sciverse_context_help_exposes_bounded_limit(self) -> None:
        output = io.StringIO()
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stdout(output):
            main(["sciverse-read-context", "--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("200-4000", output.getvalue())
        self.assertIn("non-negative character offset", output.getvalue())


if __name__ == "__main__":
    unittest.main()
