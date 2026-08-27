import { describe, expect, it } from "vitest";

import { isScreeningComplete, recordedIncludedCandidates, screeningDraftForCandidates, screeningSubmission } from "./candidateScreeningDraft";
import type { CandidateScreening } from "./localApi";

const screening = (decisions: CandidateScreening["decisions"] = []): CandidateScreening => ({
  run_id: "run-1", trust_status: "unreviewed", candidate_count: 2,
  candidates: [
    { document_id: "paper-a", title: "A", source: "OpenAlex", publication_year: 2024 },
    { document_id: "paper-b", title: "B", source: "Crossref", publication_year: 2023 },
  ],
  decisions,
});

describe("candidate screening coverage", () => {
  it("does not treat an empty recorded-decision list as a completed screening", () => {
    const draft = screeningDraftForCandidates(screening());
    expect(isScreeningComplete(screening().candidates, draft)).toBe(false);
  });

  it("requires every current candidate, not merely every stale decision", () => {
    const current = screening([{ document_id: "paper-a", decision: "include_for_fulltext", reason_codes: ["material_match"] }]);
    const draft = screeningDraftForCandidates(current);
    expect(isScreeningComplete(current.candidates, draft)).toBe(false);
  });

  it("submits exactly current candidate IDs after all decisions are complete", () => {
    const current = screening([
      { document_id: "paper-a", decision: "include_for_fulltext", reason_codes: ["material_match"] },
      { document_id: "paper-b", decision: "exclude", reason_codes: ["out_of_scope_material"] },
      { document_id: "stale-paper", decision: "include_for_fulltext", reason_codes: ["method_match"] },
    ]);
    const draft = screeningDraftForCandidates(current);
    expect(isScreeningComplete(current.candidates, draft)).toBe(true);
    expect(screeningSubmission(current.candidates, draft).map((item) => item.document_id)).toEqual(["paper-a", "paper-b"]);
  });

  it("does not expose browser-only include edits as a persisted full-text authorization", () => {
    const unreviewed = screening([{ document_id: "paper-a", decision: "include_for_fulltext", reason_codes: ["material_match"] }]);
    expect(recordedIncludedCandidates(unreviewed)).toEqual([]);
    const reviewed = {
      ...unreviewed,
      trust_status: "human_reviewed_candidate_screening_not_scientific_evidence" as const,
      decisions: [
        { document_id: "paper-b", decision: "include_for_fulltext", reason_codes: ["property_match"] },
        { document_id: "paper-a", decision: "exclude", reason_codes: ["out_of_scope_material"] },
      ],
    };
    expect(recordedIncludedCandidates(reviewed).map((candidate) => candidate.document_id)).toEqual(["paper-b"]);
  });
});
