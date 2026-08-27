import tempfile
import unittest
from pathlib import Path

from cosmatter.external_resources import (
    ExternalResourceDisclosureError,
    validate_external_resource_disclosure,
    write_external_resource_disclosure,
)


def disclosure() -> dict:
    return {
        "schema_version": "1.0",
        "trust_status": "human_completed_external_resource_disclosure_not_execution_evidence",
        "resources": [{
            "name": "OpenAlex",
            "category": "database",
            "purpose": "Bibliographic metadata and citation navigation.",
            "access_method": "API",
            "version_or_access_date": "Accessed 2026-08-13; API version recorded in provider receipt.",
            "license_or_terms": "Verify current provider terms before submission.",
            "redistribution_boundary": "Only derived metadata permitted by the provider terms is exported.",
            "used_in_final_result": False,
        }],
        "reviewer": "Zhai Jiahui",
        "review_date": "2026-08-13",
    }


class ExternalResourceDisclosureTests(unittest.TestCase):
    def test_validated_disclosure_is_written_without_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_external_resource_disclosure(Path(directory), disclosure())
            self.assertTrue(path.is_file())
            self.assertEqual(validate_external_resource_disclosure(disclosure())["resources"][0]["name"], "OpenAlex")

    def test_rejects_private_path_or_credentials(self) -> None:
        payload = disclosure()
        payload["resources"][0]["license_or_terms"] = "Authorization: Bearer secret"
        with self.assertRaises(ExternalResourceDisclosureError):
            validate_external_resource_disclosure(payload)


if __name__ == "__main__":
    unittest.main()
