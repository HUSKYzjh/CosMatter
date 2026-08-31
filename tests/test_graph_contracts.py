from __future__ import annotations

import unittest
from pathlib import Path

from cosmatter.graph_builder import build_accepted_evidence_graph
from cosmatter.graph_contracts import GraphContractError, GraphNode, GraphSnapshot
from cosmatter.graph_projection import bounded_graph_projection, external_graph_projection
from cosmatter.graph_validation import validate_graph_snapshot
from cosmatter.models import AccessPolicy, EvidenceCard, MissionBrief, Provenance, ReviewStatus, Stance
from cosmatter.verification import VerificationDecision


class GraphContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission = MissionBrief("How does strain change phase stability?", "BiFeO3", "phase stability", "epitaxial films")
        self.accepted = EvidenceCard(
            "A reported claim that must not be copied into the graph.", Stance.SUPPORT, "BiFeO3", "phase stability",
            {"substrate": "SrTiO3", "thickness_nm": 25}, "private source quotation",
            Provenance("paper-1", "markdown_line:10-11", "fixture", content_hash="a" * 64, access_policy=AccessPolicy.AUTHORIZED),
            review_status=ReviewStatus.ACCEPTED, evidence_id="evidence-1",
        )
        self.rejected = EvidenceCard(
            "A rejected claim", Stance.CONTRADICT, "BiFeO3", "phase stability", {}, "rejected quote",
            Provenance("paper-2", "p.2", "fixture"), evidence_id="evidence-2",
        )

    def test_only_accepted_evidence_becomes_a_minimized_projection(self) -> None:
        snapshot = build_accepted_evidence_graph(
            self.mission, (self.accepted, self.rejected),
            (
                VerificationDecision(self.mission.mission_id, "evidence-1", ReviewStatus.ACCEPTED, "reviewed"),
                VerificationDecision(self.mission.mission_id, "evidence-2", ReviewStatus.REJECTED, "not sufficient"),
            ),
        )
        payload = external_graph_projection(snapshot)
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(len([node for node in payload["nodes"] if node["node_type"] == "EvidenceCard"]), 1)
        serialised = str(payload)
        self.assertNotIn("private source quotation", serialised)
        self.assertNotIn("markdown_line", serialised)
        self.assertNotIn("A reported claim", serialised)
        self.assertIn("claim_digest", serialised)

    def test_projection_rejects_duplicate_verification_decisions(self) -> None:
        decision = VerificationDecision(self.mission.mission_id, "evidence-1", ReviewStatus.ACCEPTED, "reviewed")
        with self.assertRaisesRegex(ValueError, "multiple verification"):
            build_accepted_evidence_graph(self.mission, (self.accepted,), (decision, decision))

    def test_bounded_projection_filters_and_declares_truncation(self) -> None:
        snapshot = build_accepted_evidence_graph(self.mission, (self.accepted,), (VerificationDecision(self.mission.mission_id, "evidence-1", ReviewStatus.ACCEPTED, "reviewed"),))
        page = bounded_graph_projection(snapshot, node_types=("EvidenceCard",), limit=1)
        self.assertEqual(page["page"]["node_total"], 1)
        self.assertFalse(page["page"]["truncated"])
        self.assertEqual(page["nodes"][0]["node_type"], "EvidenceCard")

    def test_validation_rejects_raw_content_attribute(self) -> None:
        snapshot = GraphSnapshot(
            mission_id="mission-1", graph_id="graph:" + "a" * 32,
            source_artifact_hashes=("a" * 64,),
            nodes=(
                GraphNode("mission:" + "b" * 32, "Mission", "BiFeO3", {}),
                GraphNode("evidence:" + "c" * 32, "EvidenceCard", "evidence", {"review_status": "accepted", "claim_digest": "a", "provenance_digest": "b", "quote": "must fail"}),
            ), edges=(),
        )
        with self.assertRaises(GraphContractError):
            validate_graph_snapshot(snapshot)

    def test_versioned_json_schema_and_shacl_shapes_ship_with_the_contract(self) -> None:
        schema_root = Path(__file__).parents[1] / "src" / "cosmatter" / "schemas" / "graph"
        self.assertIn('"schema_version": {"const": "1.0"}', (schema_root / "graph_snapshot.schema.json").read_text(encoding="utf-8"))
        self.assertIn("cmg:EvidenceNodeShape", (schema_root / "graph_snapshot.shacl.ttl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
