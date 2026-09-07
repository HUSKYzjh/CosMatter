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

    def test_metadata_enrichment_help_exposes_bounded_scope(self) -> None:
        output = io.StringIO()
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stdout(output):
            main(["enrich-screened-metadata", "--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("1-10", output.getvalue())
        self.assertIn("1-12", output.getvalue())

    def test_sciverse_context_review_help_requires_exact_offset_and_private_paths(self) -> None:
        output = io.StringIO()
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stdout(output):
            main(["prepare-sciverse-context-review", "--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("exact non-negative character offset", output.getvalue())
        self.assertIn("outside the", output.getvalue())
        self.assertIn("mission run", output.getvalue())


if __name__ == "__main__":
    unittest.main()
