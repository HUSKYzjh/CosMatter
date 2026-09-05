import { describe, expect, it } from "vitest";

import {
  BLANK_QUESTION_REVIEW_STATUS,
  QUESTION_REVIEW_CHECKS,
  REVIEWED_QUESTION_STATUS,
  exportQuestionSetReviewDraft,
  parseQuestionSetReviewDraft,
  questionSetReviewReadiness,
  type QuestionSetReviewDraft,
} from "./questionSetReviewDraft";

function fixture(): QuestionSetReviewDraft {
  return {
    schema_version: "cosmatter.question-set-review/v1",
    question_set_id: "bfo-core-v1",
    material_family: "BiFeO3",
    trust_status: BLANK_QUESTION_REVIEW_STATUS,
    review_instructions: { decision: "Review every question.", checks: "Complete every check.", note: "Record a bounded reason." },
    questions: ["q1", "q2", "q3"].map((questionId, index) => ({
      question_id: questionId,
      question: `Which bounded BiFeO3 property is reported in case ${index + 1}?`,
      material: "BiFeO3",
      target_property: "bounded property",
      scope: "Compare source-located reports only.",
      intended_evidence_level: "data_supported" as const,
      review_decision: "unreviewed" as const,
      review_checks: Object.fromEntries(QUESTION_REVIEW_CHECKS.map((check) => [check, null])) as QuestionSetReviewDraft["questions"][number]["review_checks"],
      review_note: "",
    })),
  };
}

function completeReview(): QuestionSetReviewDraft {
  const value = fixture();
  value.questions = value.questions.map((question) => ({
    ...question,
    review_decision: "include",
    review_checks: Object.fromEntries(QUESTION_REVIEW_CHECKS.map((check) => [check, true])) as QuestionSetReviewDraft["questions"][number]["review_checks"],
    review_note: "Included after independent review of wording and scope.",
  }));
  return value;
}

describe("question-set review draft", () => {
  it("parses an exact local draft and reports every incomplete gate", () => {
    const parsed = parseQuestionSetReviewDraft(fixture());
    expect(questionSetReviewReadiness(parsed)).toEqual({
      questionCount: 3,
      decidedCount: 0,
      checksCompletedCount: 0,
      notesCompletedCount: 0,
      includedCount: 0,
      invalidIncludedCount: 0,
      readyForAttestation: false,
    });
  });

  it("requires all checks, notes, decisions, and at least three included questions", () => {
    const complete = completeReview();
    expect(questionSetReviewReadiness(complete).readyForAttestation).toBe(true);
    complete.questions[0].review_checks.scope_bounded = false;
    const readiness = questionSetReviewReadiness(complete);
    expect(readiness.readyForAttestation).toBe(false);
    expect(readiness.invalidIncludedCount).toBe(1);
  });

  it("sets reviewed trust only after a complete independently attested review", () => {
    expect(exportQuestionSetReviewDraft(completeReview(), false).trust_status).toBe(BLANK_QUESTION_REVIEW_STATUS);
    expect(exportQuestionSetReviewDraft(fixture(), true).trust_status).toBe(BLANK_QUESTION_REVIEW_STATUS);
    expect(exportQuestionSetReviewDraft(completeReview(), true).trust_status).toBe(REVIEWED_QUESTION_STATUS);
  });

  it("rejects extra fields and duplicate question identities", () => {
    expect(() => parseQuestionSetReviewDraft({ ...fixture(), private_path: "C:/private" })).toThrow(/Unsupported/);
    const duplicate = fixture();
    duplicate.questions[1].question_id = duplicate.questions[0].question_id;
    expect(() => parseQuestionSetReviewDraft(duplicate)).toThrow(/unique/);
  });
});
