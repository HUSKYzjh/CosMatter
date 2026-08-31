import { describe, expect, it } from "vitest";

import { candidateFulltextGate } from "./candidateFulltextGate";
import type { CandidateScreening, CandidateScreeningCandidate } from "./localApi";
import type { LiteratureGraphNode } from "./model";

const candidate: CandidateScreeningCandidate = { document_id: "doc-1", title: "Candidate", source: "Crossref", publication_year: 2025 };
const paper: LiteratureGraphNode = { nodeId: "paper:doc-1", kind: "candidate_paper", label: "Candidate", trustStatus: "candidate" };
const screening = (decision = "include_for_fulltext", trust = "human_reviewed_candidate_screening_not_scientific_evidence"): CandidateScreening => ({ run_id: "run-1", trust_status: trust, candidate_count: 1, candidates: [candidate], decisions: [{ document_id: candidate.document_id, decision, reason_codes: ["material_match"] }] });

describe("candidateFulltextGate", () => {
  it("opens only a persisted included candidate that remains a reviewable graph paper", () => {
    expect(candidateFulltextGate(screening(), "run-1", [paper], candidate)).toEqual({ ready: true, reason: null });
  });

  it("rejects unpersisted screening and non-included decisions", () => {
    expect(candidateFulltextGate(screening("include_for_fulltext", "untrusted_candidate_metadata"), "run-1", [paper], candidate)).toEqual({ ready: false, reason: "screening" });
    expect(candidateFulltextGate(screening("needs_metadata_review"), "run-1", [paper], candidate)).toEqual({ ready: false, reason: "decision" });
  });

  it("rejects a candidate missing from the current literature graph", () => {
    expect(candidateFulltextGate(screening(), "run-1", [], candidate)).toEqual({ ready: false, reason: "paper" });
  });

  it("rejects a persisted screening artifact from another local run", () => {
    expect(candidateFulltextGate(screening(), "run-2", [paper], candidate)).toEqual({ ready: false, reason: "run" });
  });
});
