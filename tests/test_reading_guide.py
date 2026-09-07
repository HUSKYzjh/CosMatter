import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.candidate_screening import candidate_screening_from_automated_trial, write_automated_trial_candidate_screening
from cosmatter.cli import main
from cosmatter.models import AccessPolicy, EvidenceCard, FlightPlan, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.reading_guide import ReadingGuideError, build_reading_guide, load_reading_guide
from cosmatter.verification import VerificationDecision


def candidate(document_id: str, query: str, *, accessible: bool, score: float, doi: str | None = None) -> dict[str, object]:
    return {
        "document_id": document_id,
        "title": f"Synthetic {document_id}",
        "query": query,
        "source": "Sciverse",
        "publication_year": 2025,
        "locator_hint": "page:1",
        "score": score,
        "is_content_accessible": accessible,
        "doi": doi,
    }


class ReadingGuideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief("why", "BiFeO3", "phase stability", "films", mission_id="mission_guide")
        self.plan = FlightPlan(self.mission.mission_id, ("conditions",), ("primary",), ("counter",))

    def test_orders_verified_then_primary_then_counter_without_query_text(self) -> None:
        card = EvidenceCard(
            "synthetic claim", Stance.CONTRADICT, "BiFeO3", "phase stability", {"sample_form": "film"},
            "synthetic quote", Provenance("counter_doc", "page:1", "fixture", access_policy=AccessPolicy.OA),
            evidence_id="evidence_counter",
        )
        decision = VerificationDecision(self.mission.mission_id, card.evidence_id, ReviewStatus.ACCEPTED, "complete")
        guide = build_reading_guide(
            self.mission,
            self.plan,
            {"candidates": [candidate("primary_doc", "primary", accessible=True, score=0.9), candidate("counter_doc", "counter", accessible=True, score=0.2), candidate("metadata_doc", "counter", accessible=False, score=0.8)]},
            (card,),
            (decision,),
        )

        self.assertEqual([item["document_id"] for item in guide["items"]], ["counter_doc", "primary_doc", "metadata_doc"])
        self.assertEqual(guide["items"][0]["role"], "verified_evidence")
        self.assertEqual(guide["items"][2]["content_status"], "metadata_only")
        serialized = json.dumps(guide)
        self.assertNotIn('"query"', serialized)
        self.assertNotIn('"score"', serialized)
        self.assertNotIn("primary\", \"counter", serialized)

    def test_rejects_candidate_outside_approved_plan(self) -> None:
        with self.assertRaises(ReadingGuideError):
            build_reading_guide(self.mission, self.plan, {"candidates": [candidate("bad_doc", "unapproved", accessible=True, score=1.0)]})

    def test_prioritizes_screened_candidates_and_retains_counterevidence_track(self) -> None:
        candidates = [
            candidate(f"primary_{index:02d}", "primary", accessible=True, score=1.0 - index / 100)
            for index in range(15)
        ]
        candidates.append(candidate("counter_low_score", "counter", accessible=True, score=0.01))
        payload = {"candidates": candidates}
        selected = {"primary_12", "primary_13", "primary_14"}
        screening = candidate_screening_from_automated_trial(
            self.mission.mission_id,
            payload,
            {
                "decisions": [
                    {
                        "document_id": item["document_id"],
                        "decision": "include_for_fulltext" if item["document_id"] in selected else "needs_metadata_review",
                        "reason_codes": ["material_match"] if item["document_id"] in selected else ["not_enough_metadata"],
                    }
                    for item in candidates
                ]
            },
        )

        guide = build_reading_guide(self.mission, self.plan, payload, screening=screening)

        routed_ids = [item["document_id"] for item in guide["items"]]
        self.assertTrue(selected.issubset(routed_ids))
        self.assertEqual(set(routed_ids[:3]), selected)
        self.assertIn("counterevidence", {item["track"] for item in guide["items"]})
        selected_item = next(item for item in guide["items"] if item["document_id"] == "primary_12")
        self.assertEqual(selected_item["routing_signals"][:2], ["screened_for_fulltext", "material_match"])

    def test_rejects_stale_screening(self) -> None:
        original = {"candidates": [candidate("primary_doc", "primary", accessible=True, score=0.7)]}
        screening = candidate_screening_from_automated_trial(
            self.mission.mission_id,
            original,
            {"decisions": [{"document_id": "primary_doc", "decision": "include_for_fulltext", "reason_codes": ["material_match"]}]},
        )
        changed = {"candidates": original["candidates"] + [candidate("counter_doc", "counter", accessible=True, score=0.6)]}

        with self.assertRaisesRegex(ReadingGuideError, "stale"):
            build_reading_guide(self.mission, self.plan, changed, screening=screening)

    def test_load_upgrades_legacy_route_without_inventing_screening_reasons(self) -> None:
        guide = build_reading_guide(
            self.mission,
            self.plan,
            {"candidates": [candidate("primary_doc", "primary", accessible=True, score=0.7)]},
        )
        legacy = {**guide, "schema_version": "1.0"}
        legacy["items"] = [
            {key: value for key, value in item.items() if key not in {"doi", "routing_signals"}}
            for item in guide["items"]
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reading_guide.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            loaded = load_reading_guide(path, self.mission.mission_id)

        self.assertEqual(loaded["schema_version"], "1.1")
        self.assertEqual(loaded["items"][0]["routing_signals"], ["provider_advertised_content"])
        self.assertIsNone(loaded["items"][0]["doi"])

    def test_cli_writes_guide_and_export_projects_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "guide_cli"
            run_dir.mkdir()
            (run_dir / "mission.json").write_text(json.dumps(self.mission.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(self.plan.to_dict()), encoding="utf-8")
            (run_dir / "retrieval_candidates.json").write_text(json.dumps({"candidates": [candidate("primary_doc", "primary", accessible=True, score=0.7)]}), encoding="utf-8")
            from cosmatter.dispatch import MissionDispatcher
            assignment = MissionDispatcher.from_project().assign(self.mission)
            (run_dir / "fleet_assignment.json").write_text(json.dumps(assignment.to_dict()), encoding="utf-8")
            output = io.StringIO()
            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(output):
                self.assertEqual(main(["build-reading-guide", "--run-id", "guide_cli"]), 0)
                self.assertEqual(main(["export-ui", "--run-id", "guide_cli"]), 0)
            guide = json.loads((run_dir / "reading_guide.json").read_text(encoding="utf-8"))
            bundle = json.loads((run_dir / "ui.json").read_text(encoding="utf-8"))

        self.assertEqual(guide["trust_status"], "derived_from_approved_artifacts")
        self.assertEqual(bundle["research_guide"]["items"][0]["document_id"], "primary_doc")
        self.assertIn("有界阅读路线已生成", [entry["action"] for entry in bundle["timeline"]])

    def test_cli_consumes_current_trial_screening(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "guide_screened_cli"
            run_dir.mkdir()
            candidates = [
                candidate(f"primary_{index:02d}", "primary", accessible=True, score=1.0 - index / 100)
                for index in range(15)
            ]
            candidates.append(candidate("counter_low_score", "counter", accessible=True, score=0.01))
            payload = {"candidates": candidates}
            selected = {"primary_12", "primary_13", "primary_14"}
            screening = candidate_screening_from_automated_trial(
                self.mission.mission_id,
                payload,
                {
                    "decisions": [
                        {
                            "document_id": item["document_id"],
                            "decision": "include_for_fulltext" if item["document_id"] in selected else "needs_metadata_review",
                            "reason_codes": ["material_match"] if item["document_id"] in selected else ["not_enough_metadata"],
                        }
                        for item in candidates
                    ]
                },
            )
            (run_dir / "mission.json").write_text(json.dumps(self.mission.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(self.plan.to_dict()), encoding="utf-8")
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(payload), encoding="utf-8")
            write_automated_trial_candidate_screening(run_dir, screening)

            with patch("cosmatter.cli._runs_dir", return_value=runs_dir), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["build-reading-guide", "--run-id", "guide_screened_cli"]), 0)
            guide = json.loads((run_dir / "reading_guide.json").read_text(encoding="utf-8"))

        routed_ids = {item["document_id"] for item in guide["items"]}
        self.assertTrue(selected.issubset(routed_ids))
        self.assertIn("counterevidence", {item["track"] for item in guide["items"]})


if __name__ == "__main__":
    unittest.main()
