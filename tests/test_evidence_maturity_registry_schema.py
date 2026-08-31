import json
import unittest

from cosmatter.config import AGENT_ROOT


class EvidenceMaturityRegistrySchemaTests(unittest.TestCase):
    def test_schema_keeps_trial_and_human_authority_separate(self) -> None:
        path = AGENT_ROOT / "src" / "cosmatter" / "schemas" / "evidence_maturity_registry.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        claim = schema["$defs"]["claim"]["properties"]
        self.assertIn("delegated_automated_trial", claim["assessment_authority"]["enum"])
        self.assertIn("human_data_review", claim["assessment_authority"]["enum"])
        self.assertIn(
            "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence",
            schema["properties"]["trust_status"]["enum"],
        )
        self.assertEqual(
            claim["maturity_level"]["enum"],
            ["literature_mentioned", "data_supported", "reproducibility_ready", "independently_reproduced"],
        )


if __name__ == "__main__":
    unittest.main()
