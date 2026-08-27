import { describe, expect, it } from "vitest";

import { candidateScreeningProgress } from "./candidateScreeningProgress";
import type { CandidateScreening } from "./localApi";

const screening = (overrides: Partial<CandidateScreening> = {}): CandidateScreening => ({
  run_id: "run-1",
  trust_status: "blank_human_candidate_screening_template_not_a_result",
  candidate_count: 2,
  candidates: [
    { document_id: "paper-a", title: "A", source: "Sciverse", publication_year: 2024 },
    { document_id: "paper-b", title: "B", source: "OpenAlex", publication_year: 2023 },
  ],
  decisions: [],
  ...overrides,
});

describe("candidate screening progress", () => {
  it("keeps automatic candidates pending until a local checklist is loaded", () => {
    expect(candidateScreeningProgress(null, 3, true)).toEqual({
      state: "not_loaded", candidateCount: 3, reviewedCount: 0, pendingCount: 3, includedCount: 0,
    });
  });

  it("does not mistake a partly filled or blank checklist for a completed review", () => {
    expect(candidateScreeningProgress(screening({ decisions: [
      { document_id: "paper-a", decision: "include_for_fulltext", reason_codes: ["material_match"] },
    ] }), 2, true)).toMatchObject({ state: "in_progress", reviewedCount: 1, pendingCount: 1, includedCount: 0 });
  });

  it("exposes full-text eligibility only after a persisted complete human review", () => {
    const progress = candidateScreeningProgress(screening({
      trust_status: "human_reviewed_candidate_screening_not_scientific_evidence",
      decisions: [
        { document_id: "paper-a", decision: "include_for_fulltext", reason_codes: ["material_match"] },
        { document_id: "paper-b", decision: "exclude", reason_codes: ["out_of_scope_material"] },
      ],
    }), 2, true);
    expect(progress).toEqual({ state: "completed", candidateCount: 2, reviewedCount: 2, pendingCount: 0, includedCount: 1 });
  });

  it("does not invent a human-screening route in read-only preview mode", () => {
    expect(candidateScreeningProgress(null, 2, false)).toMatchObject({ state: "unavailable", pendingCount: 2 });
  });
});