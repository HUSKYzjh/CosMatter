import sqlite3
import unittest
from pathlib import Path


class EvidenceMaturityDatabaseSchemaTests(unittest.TestCase):
    def test_template_creates_the_bounded_relational_registry_tables(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = (root / "docs" / "templates" / "evidence_maturity_registry.sql").read_text(encoding="utf-8")
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(schema)
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        finally:
            connection.close()
        self.assertTrue({
            "evidence_maturity_registry", "research_claim", "document_version", "claim_support",
            "reproducibility_assessment", "independent_reproduction", "claim_limitation",
            "evidence_maturity_registry_audit",
        }.issubset(tables))
        self.assertNotIn("api_key", schema.casefold())
        self.assertNotIn("authorization", schema.casefold())
        self.assertNotIn("file://", schema.casefold())


if __name__ == "__main__":
    unittest.main()
