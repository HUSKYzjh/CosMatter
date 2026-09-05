export const QUESTION_REVIEW_SCHEMA = "cosmatter.question-set-review/v1" as const;
export const BLANK_QUESTION_REVIEW_STATUS = "blank_human_question_set_review_not_frozen" as const;
export const REVIEWED_QUESTION_STATUS = "human_reviewed_question_set_for_evaluation" as const;

export const QUESTION_REVIEW_CHECKS = [
  "answerable_by_literature",
  "material_explicit",
  "target_property_explicit",
  "scope_bounded",
  "avoids_assumed_answer",
] as const;

export type QuestionReviewCheck = typeof QUESTION_REVIEW_CHECKS[number];
export type QuestionReviewDecision = "unreviewed" | "include" | "exclude";
export type QuestionReviewCheckValue = boolean | null;
export type QuestionEvidenceLevel = "literature_mentioned" | "data_supported" | "reproducible" | "already_reproduced";

export interface QuestionSetReviewQuestion {
  question_id: string;
  question: string;
  material: string;
  target_property: string;
  scope: string;
  intended_evidence_level: QuestionEvidenceLevel;
  review_decision: QuestionReviewDecision;
  review_checks: Record<QuestionReviewCheck, QuestionReviewCheckValue>;
  review_note: string;
}

export interface QuestionSetReviewDraft {
  schema_version: typeof QUESTION_REVIEW_SCHEMA;
  question_set_id: string;
  material_family: string;
  trust_status: typeof BLANK_QUESTION_REVIEW_STATUS | typeof REVIEWED_QUESTION_STATUS;
  review_instructions: { decision: string; checks: string; note: string };
  questions: QuestionSetReviewQuestion[];
}

export interface QuestionSetReviewReadiness {
  questionCount: number;
  decidedCount: number;
  checksCompletedCount: number;
  notesCompletedCount: number;
  includedCount: number;
  invalidIncludedCount: number;
  readyForAttestation: boolean;
}

const ROOT_FIELDS = ["schema_version", "question_set_id", "material_family", "trust_status", "review_instructions", "questions"];
const QUESTION_FIELDS = ["question_id", "question", "material", "target_property", "scope", "intended_evidence_level", "review_decision", "review_checks", "review_note"];
const INSTRUCTION_FIELDS = ["decision", "checks", "note"];
const EVIDENCE_LEVELS = new Set<QuestionEvidenceLevel>(["literature_mentioned", "data_supported", "reproducible", "already_reproduced"]);
const DECISIONS = new Set<QuestionReviewDecision>(["unreviewed", "include", "exclude"]);

export function parseQuestionSetReviewDraft(value: unknown): QuestionSetReviewDraft {
  if (!isExactRecord(value, ROOT_FIELDS) || value.schema_version !== QUESTION_REVIEW_SCHEMA || !isBoundedText(value.question_set_id, 120) || !isBoundedText(value.material_family, 300) || ![BLANK_QUESTION_REVIEW_STATUS, REVIEWED_QUESTION_STATUS].includes(value.trust_status as never)) {
    throw new Error("Unsupported question-set review file.");
  }
  const instructions = value.review_instructions;
  if (!isExactRecord(instructions, INSTRUCTION_FIELDS) || !INSTRUCTION_FIELDS.every((field) => isBoundedText(instructions[field], 1_000))) {
    throw new Error("Question-set review instructions are invalid.");
  }
  if (!Array.isArray(value.questions) || value.questions.length < 3 || value.questions.length > 50) {
    throw new Error("Question-set review must contain 3 to 50 questions.");
  }
  const identifiers = new Set<string>();
  const questionTexts = new Set<string>();
  for (const item of value.questions) {
    if (!isExactRecord(item, QUESTION_FIELDS)) throw new Error("Question-set item fields are invalid.");
    const limits: Record<string, number> = { question_id: 120, question: 1_000, material: 300, target_property: 300, scope: 1_000 };
    for (const [field, maximum] of Object.entries(limits)) if (!isBoundedText(item[field], maximum)) throw new Error(`Question-set ${field} is invalid.`);
    if (!EVIDENCE_LEVELS.has(item.intended_evidence_level as QuestionEvidenceLevel) || !DECISIONS.has(item.review_decision as QuestionReviewDecision)) throw new Error("Question-set review state is invalid.");
    const checks = item.review_checks;
    if (!isExactRecord(checks, [...QUESTION_REVIEW_CHECKS]) || !QUESTION_REVIEW_CHECKS.every((check) => checks[check] === true || checks[check] === false || checks[check] === null)) throw new Error("Question-set review checks are invalid.");
    if (typeof item.review_note !== "string" || item.review_note.length > 500) throw new Error("Question-set review note is invalid.");
    const questionId = (item.question_id as string).trim();
    const normalizedQuestion = normalizeIdentity(item.question as string);
    if (identifiers.has(questionId) || questionTexts.has(normalizedQuestion)) throw new Error("Question-set IDs and question texts must be unique.");
    identifiers.add(questionId);
    questionTexts.add(normalizedQuestion);
  }
  return structuredClone(value) as unknown as QuestionSetReviewDraft;
}

export function questionSetReviewReadiness(draft: QuestionSetReviewDraft): QuestionSetReviewReadiness {
  const questionCount = draft.questions.length;
  const decidedCount = draft.questions.filter((item) => item.review_decision !== "unreviewed").length;
  const checksCompletedCount = draft.questions.filter((item) => QUESTION_REVIEW_CHECKS.every((check) => typeof item.review_checks[check] === "boolean")).length;
  const notesCompletedCount = draft.questions.filter((item) => Boolean(item.review_note.trim()) && item.review_note.trim().length <= 500).length;
  const included = draft.questions.filter((item) => item.review_decision === "include");
  const invalidIncludedCount = included.filter((item) => !QUESTION_REVIEW_CHECKS.every((check) => item.review_checks[check] === true)).length;
  return {
    questionCount,
    decidedCount,
    checksCompletedCount,
    notesCompletedCount,
    includedCount: included.length,
    invalidIncludedCount,
    readyForAttestation: decidedCount === questionCount && checksCompletedCount === questionCount && notesCompletedCount === questionCount && included.length >= 3 && invalidIncludedCount === 0,
  };
}

export function exportQuestionSetReviewDraft(draft: QuestionSetReviewDraft, independentlyAttested: boolean): QuestionSetReviewDraft {
  const copy = structuredClone(draft);
  copy.trust_status = independentlyAttested && questionSetReviewReadiness(copy).readyForAttestation ? REVIEWED_QUESTION_STATUS : BLANK_QUESTION_REVIEW_STATUS;
  return copy;
}

function isExactRecord(value: unknown, fields: readonly string[]): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === fields.length && fields.every((field) => Object.prototype.hasOwnProperty.call(value, field)));
}

function isBoundedText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && Boolean(value.trim()) && value.trim().length <= maximum;
}

function normalizeIdentity(value: string): string {
  return [...value].filter((character) => /[\p{L}\p{N}]/u.test(character)).join("").toLocaleLowerCase();
}
