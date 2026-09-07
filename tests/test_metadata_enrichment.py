import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cosmatter.candidate_screening import candidate_screening_from_automated_trial, write_automated_trial_candidate_screening
from cosmatter.cli import main
from cosmatter.metadata_enrichment import (
    MetadataEnrichmentError,
    build_metadata_enrichment,
    load_metadata_enrichment,
    merge_metadata_enrichment,
    resolved_dois,
    write_metadata_enrichment,
)
from cosmatter.models import FlightPlan, MissionBrief, PaperCandidate


def candidate(document_id: str, title: str, *, year: int | None = 2024, doi: str | None = None) -> dict[str, object]:
    return PaperCandidate(
        document_id=document_id,
        title=title,
        query="approved query",
        source="Sciverse",
        publication_year=year,
        doi=doi,
    ).to_dict()


def provider(source: str, title: str, doi: str, *, year: int | None = 2024) -> PaperCandidate:
    return PaperCandidate(
        document_id=f"{source.casefold()}:{doi}",
        title=title,
        query=title,
        source=source,
        publication_year=year,
        doi=doi,
    )


class MetadataEnrichmentTests(unittest.TestCase):
    def test_exact_title_and_year_resolve_known_doi(self) -> None:
        payload = {"candidates": [candidate("doc_1", "A PST configuration study.")]}
        artifact = build_metadata_enrichment(
            "mission_1",
            payload,
            ("doc_1",),
            {
                "doc_1": {
                    "Crossref": (provider("Crossref", "A PST configuration study", "10.1000/PST.1"),),
                    "OpenAlex": (provider("OpenAlex", "A PST configuration study.", "https://doi.org/10.1000/pst.1"),),
                }
            },
        )

        self.assertEqual(artifact["summary"]["resolved_count"], 1)
        self.assertEqual(artifact["records"][0]["doi"], "10.1000/pst.1")
        self.assertEqual(resolved_dois(artifact), {"doc_1": "10.1000/pst.1"})

    def test_conflicting_exact_dois_fail_closed(self) -> None:
        payload = {"candidates": [candidate("doc_1", "Same title")]}
        artifact = build_metadata_enrichment(
            "mission_1",
            payload,
            ("doc_1",),
            {
                "doc_1": {
                    "Crossref": (provider("Crossref", "Same title", "10.1000/one"),),
                    "OpenAlex": (provider("OpenAlex", "Same title", "10.1000/two"),),
                }
            },
        )

        self.assertEqual(artifact["records"][0]["status"], "conflict")
        self.assertIsNone(artifact["records"][0]["doi"])
        self.assertEqual(resolved_dois(artifact), {})

    def test_near_title_or_wrong_year_does_not_resolve(self) -> None:
        payload = {"candidates": [candidate("doc_1", "Exact title", year=2024)]}
        artifact = build_metadata_enrichment(
            "mission_1",
            payload,
            ("doc_1",),
            {
                "doc_1": {
                    "Crossref": (provider("Crossref", "Exact title: review", "10.1000/near", year=2024),),
                    "OpenAlex": (provider("OpenAlex", "Exact title", "10.1000/wrong-year", year=2023),),
                }
            },
        )
        self.assertEqual(artifact["records"][0]["status"], "not_found")

    def test_all_provider_failures_are_distinct_from_not_found(self) -> None:
        payload = {"candidates": [candidate("doc_1", "Exact title")]}
        artifact = build_metadata_enrichment(
            "mission_1",
            payload,
            ("doc_1",),
            {"doc_1": {"Crossref": None, "OpenAlex": None}},
        )
        self.assertEqual(artifact["records"][0]["status"], "provider_failed")
        self.assertEqual(artifact["summary"]["provider_call_failure_count"], 2)

    def test_loader_rejects_stale_candidate_set(self) -> None:
        payload = {"candidates": [candidate("doc_1", "Exact title")]}
        artifact = build_metadata_enrichment(
            "mission_1",
            payload,
            ("doc_1",),
            {"doc_1": {"Crossref": ()}},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_metadata_enrichment(Path(directory), artifact)
            self.assertIsNotNone(load_metadata_enrichment(path, "mission_1", payload))
            changed = {"candidates": [candidate("doc_1", "Changed title")]}
            with self.assertRaisesRegex(MetadataEnrichmentError, "stale"):
                load_metadata_enrichment(path, "mission_1", changed)

    def test_bounded_batches_merge_without_overwriting_prior_records(self) -> None:
        payload = {
            "candidates": [
                candidate("doc_1", "First title"),
                candidate("doc_2", "Second title"),
            ]
        }
        first = build_metadata_enrichment(
            "mission_1", payload, ("doc_1",),
            {"doc_1": {"Crossref": (provider("Crossref", "First title", "10.1000/one"),)}},
        )
        second = build_metadata_enrichment(
            "mission_1", payload, ("doc_2",),
            {"doc_2": {"Crossref": (), "OpenAlex": None}},
        )
        merged = merge_metadata_enrichment(first, second, "mission_1", payload)

        self.assertEqual(merged["requested_document_count"], 2)
        self.assertEqual([record["document_id"] for record in merged["records"]], ["doc_1", "doc_2"])
        self.assertEqual(merged["summary"]["resolved_count"], 1)
        self.assertEqual(merged["summary"]["not_found_count"], 1)
        self.assertEqual(merged["summary"]["provider_call_failure_count"], 1)
        with self.assertRaisesRegex(MetadataEnrichmentError, "overwrite"):
            merge_metadata_enrichment(merged, second, "mission_1", payload)

    def test_cumulative_artifact_can_cross_the_twelve_document_call_boundary(self) -> None:
        payload = {"candidates": [candidate(f"doc_{index}", f"Title {index}") for index in range(13)]}
        first_ids = tuple(f"doc_{index}" for index in range(12))
        first = build_metadata_enrichment(
            "mission_1", payload, first_ids,
            {document_id: {"Crossref": ()} for document_id in first_ids},
        )
        second = build_metadata_enrichment(
            "mission_1", payload, ("doc_12",), {"doc_12": {"Crossref": ()}},
        )

        merged = merge_metadata_enrichment(first, second, "mission_1", payload)
        self.assertEqual(merged["requested_document_count"], 13)
        with self.assertRaisesRegex(MetadataEnrichmentError, "1 to 12"):
            build_metadata_enrichment(
                "mission_1", payload, tuple(f"doc_{index}" for index in range(13)),
                {f"doc_{index}": {"Crossref": ()} for index in range(13)},
            )

    def test_cli_enriches_only_screened_candidates_and_records_no_title(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "enrichment_cli"
            run_dir.mkdir()
            mission = MissionBrief("why", "PST", "dielectric", "fixed composition", mission_id="mission_enrichment")
            plan = FlightPlan(mission.mission_id, ("subquestion",), ("approved query",), ("counter query",))
            payload = {
                "candidates": [
                    candidate("selected_doc", "Exact selected title"),
                    candidate("pending_doc", "Do not query this title"),
                ]
            }
            screening = candidate_screening_from_automated_trial(
                mission.mission_id,
                payload,
                {
                    "decisions": [
                        {"document_id": "selected_doc", "decision": "include_for_fulltext", "reason_codes": ["material_match"]},
                        {"document_id": "pending_doc", "decision": "needs_metadata_review", "reason_codes": ["not_enough_metadata"]},
                    ]
                },
            )
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(payload), encoding="utf-8")
            write_automated_trial_candidate_screening(run_dir, screening)
            resolved = provider("Crossref", "Exact selected title", "10.1000/selected")
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.MetadataSearchAdapter") as adapter,
                contextlib.redirect_stdout(output),
            ):
                adapter.return_value.search_crossref.return_value = (resolved,)
                status = main(
                    [
                        "enrich-screened-metadata", "--run-id", "enrichment_cli",
                        "--provider", "crossref", "--allow-delegated-automated-trial",
                    ]
                )
                guide_status = main(["build-reading-guide", "--run-id", "enrichment_cli"])
            artifact = json.loads((run_dir / "candidate_metadata_enrichment.json").read_text(encoding="utf-8"))
            guide = json.loads((run_dir / "reading_guide.json").read_text(encoding="utf-8"))
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual(status, 0)
        self.assertEqual(guide_status, 0)
        adapter.return_value.search_crossref.assert_called_once_with("Exact selected title", top_k=5)
        self.assertEqual(artifact["records"][0]["doi"], "10.1000/selected")
        selected_guide_item = next(item for item in guide["items"] if item["document_id"] == "selected_doc")
        self.assertEqual(selected_guide_item["doi"], "10.1000/selected")
        self.assertIn("normalized_doi_resolved", selected_guide_item["routing_signals"])
        self.assertNotIn("Exact selected title", audit)
        self.assertNotIn("Do not query this title", audit)

    def test_cli_resumes_explicit_all_candidate_coverage_in_bounded_batches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runs_dir = Path(directory)
            run_dir = runs_dir / "all_candidate_enrichment"
            run_dir.mkdir()
            mission = MissionBrief("why", "PST", "dielectric", "fixed composition", mission_id="mission_all")
            plan = FlightPlan(mission.mission_id, ("subquestion",), ("approved query",), ("counter query",))
            payload = {
                "candidates": [
                    candidate("known_doc", "Known DOI title", doi="10.1000/known"),
                    candidate("second_doc", "Second external title"),
                    candidate("third_doc", "Third external title"),
                    {**candidate("invalid_doi_doc", "Invalid DOI external title"), "doi": "not-a-doi"},
                ]
            }
            (run_dir / "mission.json").write_text(json.dumps(mission.to_dict()), encoding="utf-8")
            (run_dir / "flight_plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            (run_dir / "retrieval_candidates.json").write_text(json.dumps(payload), encoding="utf-8")
            output = io.StringIO()
            with (
                patch("cosmatter.cli._runs_dir", return_value=runs_dir),
                patch("cosmatter.cli.MetadataSearchAdapter") as adapter,
                contextlib.redirect_stdout(output),
            ):
                adapter.return_value.search_crossref.side_effect = lambda title, top_k: (
                    provider("Crossref", title, f"10.1000/{title.split()[0].casefold()}"),
                )
                first_status = main([
                    "enrich-screened-metadata", "--run-id", "all_candidate_enrichment",
                    "--provider", "crossref", "--max-documents", "2", "--all-candidates",
                ])
                first_output = json.loads(output.getvalue())
                output.seek(0)
                output.truncate(0)
                second_status = main([
                    "enrich-screened-metadata", "--run-id", "all_candidate_enrichment",
                    "--provider", "crossref", "--max-documents", "2", "--all-candidates",
                ])
                second_output = json.loads(output.getvalue())
                output.seek(0)
                output.truncate(0)
                complete_status = main([
                    "enrich-screened-metadata", "--run-id", "all_candidate_enrichment",
                    "--provider", "crossref", "--max-documents", "2", "--all-candidates",
                ])
                complete_output = json.loads(output.getvalue())
            artifact = json.loads((run_dir / "candidate_metadata_enrichment.json").read_text(encoding="utf-8"))
            audit = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        self.assertEqual((first_status, second_status, complete_status), (0, 0, 0))
        self.assertEqual([item.args[0] for item in adapter.return_value.search_crossref.call_args_list], ["Second external title", "Third external title", "Invalid DOI external title"])
        self.assertEqual(artifact["requested_document_count"], 4)
        self.assertEqual(artifact["summary"]["already_present_count"], 1)
        self.assertEqual(artifact["summary"]["resolved_count"], 3)
        self.assertEqual(first_output["remaining_document_count"], 2)
        self.assertFalse(first_output["complete"])
        self.assertEqual(second_output["remaining_document_count"], 0)
        self.assertEqual(complete_output["processed_document_count"], 0)
        self.assertTrue(complete_output["complete"])
        self.assertNotIn("Second external title", audit)
        self.assertNotIn("Third external title", audit)


if __name__ == "__main__":
    unittest.main()
