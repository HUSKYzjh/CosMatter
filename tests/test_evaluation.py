import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.cli import main
from cosmatter.config import AGENT_ROOT
from cosmatter.evaluation import EvaluationError, evaluate_frozen_route_fixture, evaluate_route_diagnostics, write_evaluation_record
from cosmatter.models import AccessPolicy, EvidenceCard, Provenance, Stance


def fixture_cards(fixture: dict[str, object]) -> tuple[EvidenceCard, ...]:
    return tuple(
        EvidenceCard(
            claim="Synthetic regression record; not a scientific claim.",
            stance=Stance(item["stance"]),
            material=str(fixture["material"]),
            property_name=str(fixture["property_name"]),
            conditions=item["conditions"],
            quote="Synthetic fixture only; no paper text is included.",
            provenance=Provenance(item["evidence_id"], "fixture", "CosMatter frozen test", access_policy=AccessPolicy.LOCAL_ONLY),
            evidence_id=item["evidence_id"],
        )
        for item in fixture["evidence_cards"]
    )


class EvaluationTests(unittest.TestCase):
    def test_frozen_bfo_fixture_produces_reproducible_metrics(self) -> None:
        fixture = json.loads((AGENT_ROOT / "examples" / "frozen" / "bfo_route_diagnostics.json").read_text(encoding="utf-8"))
        report = evaluate_route_diagnostics(
            fixture_id="bfo_route_diagnostics_v0_1",
            mission_id="evaluation_mission",
            cards=fixture_cards(fixture),
            counterevidence_queries=tuple(fixture["counterevidence_queries"]),
            expected_evidence_status=fixture["expected_evidence_status"],
            expected_stances=fixture["expected_stances"],
            expected_differing_fields=tuple(fixture["expected_differing_fields"]),
        )

        self.assertEqual(report.citation_precision, 1.0)
        self.assertEqual(report.condition_completeness, 1.0)
        self.assertEqual(report.contradiction_precision, 1.0)
        self.assertEqual(report.reproducibility_consistency, 1.0)

    def test_cli_writes_an_evaluation_record_and_a_summary_audit_event(self) -> None:
        fixture_path = AGENT_ROOT / "examples" / "frozen" / "bfo_route_diagnostics.json"
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                status = main(["evaluate-fixture", "--fixture", str(fixture_path), "--run-id", "evaluation_cli"])
            payload = json.loads(output.getvalue())
            report = json.loads((runs_dir / "evaluation_cli" / "evaluation.json").read_text(encoding="utf-8"))
            audit = (runs_dir / "evaluation_cli" / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        self.assertEqual(payload["fixture_id"], "bfo_route_diagnostics_v0.1")
        self.assertEqual(report["reproducibility_consistency"], 1.0)
        self.assertIn("frozen_fixture_evaluated", audit)
        self.assertNotIn("Synthetic fixture only", audit)
    def test_loader_rejects_non_synthetic_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not_synthetic.json"
            path.write_text(json.dumps({"synthetic": False}), encoding="utf-8")
            with self.assertRaises(EvaluationError):
                evaluate_frozen_route_fixture(path, "evaluation_mission")
    def test_report_is_a_redacted_reproducible_work_product(self) -> None:
        fixture = json.loads((AGENT_ROOT / "examples" / "frozen" / "bfo_route_diagnostics.json").read_text(encoding="utf-8"))
        report = evaluate_route_diagnostics(
            fixture_id="bfo_route_diagnostics_v0_1",
            mission_id="evaluation_mission",
            cards=fixture_cards(fixture),
            counterevidence_queries=tuple(fixture["counterevidence_queries"]),
            expected_evidence_status=fixture["expected_evidence_status"],
            expected_stances=fixture["expected_stances"],
            expected_differing_fields=tuple(fixture["expected_differing_fields"]),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_evaluation_record(Path(directory), report)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["fixture_id"], "bfo_route_diagnostics_v0_1")
        self.assertNotIn("quote", payload)
        self.assertNotIn("api_key", json.dumps(payload).lower())


if __name__ == "__main__":
    unittest.main()
