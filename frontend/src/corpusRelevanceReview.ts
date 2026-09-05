export const HUMAN_GOLD_SCHEMA = "1.0" as const;
export const BLANK_HUMAN_GOLD_STATUS = "blank_human_annotation_template_not_evaluation_result" as const;
export const REVIEWED_HUMAN_GOLD_STATUS = "human_reviewed_gold_standard_for_evaluation" as const;
export const CORPUS_MANIFEST_STATUS = "human_reviewed_authorized_corpus_manifest_not_evaluation_result" as const;
export const CORPUS_ACCESS_BOUNDARY = "institutional_access_local_review_only_no_fulltext_redistribution" as const;
export const DOCUMENT_ACCESS_POLICY = "institutional_access_internal_review_only" as const;

export const HUMAN_GOLD_INSTRUCTION_FIELDS = [
  "retrieval_relevance",
  "evidence_annotations",
  "material_fact_annotations",
  "comparison_annotations",
  "gap_annotations",
] as const;

export type HumanGoldInstructionField = typeof HUMAN_GOLD_INSTRUCTION_FIELDS[number];
export type RetrievalRelevance = "unreviewed" | "relevant" | "partially_relevant" | "not_relevant";

export interface HumanGoldDocument {
  document_id: string;
  retrieval_relevance: RetrievalRelevance;
  evidence_annotations: unknown[];
  material_fact_annotations: unknown[];
  comparison_annotations: unknown[];
  gap_annotations: unknown[];
}

export interface HumanGoldDraft {
  schema_version: typeof HUMAN_GOLD_SCHEMA;
  mission_id: string;
  corpus_id: string;
  trust_status: typeof BLANK_HUMAN_GOLD_STATUS | typeof REVIEWED_HUMAN_GOLD_STATUS;
  annotation_instructions: Record<HumanGoldInstructionField, string>;
  documents: HumanGoldDocument[];
}

export interface CorpusManifestDocument {
  document_id: string;
  title: string;
  doi: string | null;
  access_policy: typeof DOCUMENT_ACCESS_POLICY;
}

export interface CorpusManifest {
  schema_version: typeof HUMAN_GOLD_SCHEMA;
  mission_id: string;
  corpus_id: string;
  material: string;
  trust_status: typeof CORPUS_MANIFEST_STATUS;
  access_boundary: typeof CORPUS_ACCESS_BOUNDARY;
  documents: CorpusManifestDocument[];
}

export interface CorpusRelevanceReadiness {
  documentCount: number;
  reviewedCount: number;
  counts: Record<RetrievalRelevance, number>;
  readyForAttestation: boolean;
}

const GOLD_ROOT_FIELDS = ["schema_version", "mission_id", "corpus_id", "trust_status", "annotation_instructions", "documents"];
const GOLD_DOCUMENT_FIELDS = ["document_id", "retrieval_relevance", "evidence_annotations", "material_fact_annotations", "comparison_annotations", "gap_annotations"];
const MANIFEST_ROOT_FIELDS = ["schema_version", "mission_id", "corpus_id", "material", "trust_status", "access_boundary", "documents"];
const MANIFEST_DOCUMENT_FIELDS = ["document_id", "title", "doi", "access_policy"];
const RELEVANCE = new Set<RetrievalRelevance>(["unreviewed", "relevant", "partially_relevant", "not_relevant"]);

export function parseHumanGoldDraft(value: unknown): HumanGoldDraft {
  if (
    !isExactRecord(value, GOLD_ROOT_FIELDS)
    || value.schema_version !== HUMAN_GOLD_SCHEMA
    || !isBoundedText(value.mission_id, 180)
    || !isBoundedText(value.corpus_id, 120)
    || (value.trust_status !== BLANK_HUMAN_GOLD_STATUS && value.trust_status !== REVIEWED_HUMAN_GOLD_STATUS)
  ) throw new Error("Unsupported human-gold review file.");

  const instructions = value.annotation_instructions;
  if (
    !isExactRecord(instructions, [...HUMAN_GOLD_INSTRUCTION_FIELDS])
    || !HUMAN_GOLD_INSTRUCTION_FIELDS.every((field) => isBoundedText(instructions[field], 1_000))
  ) throw new Error("Human-gold annotation instructions are invalid.");

  if (!Array.isArray(value.documents) || value.documents.length < 1 || value.documents.length > 250) {
    throw new Error("Human-gold review must contain 1 to 250 documents.");
  }
  const documentIds = new Set<string>();
  for (const item of value.documents) {
    if (!isExactRecord(item, GOLD_DOCUMENT_FIELDS)) throw new Error("Human-gold document fields are invalid.");
    if (!isBoundedText(item.document_id, 180) || documentIds.has(item.document_id.trim()) || !RELEVANCE.has(item.retrieval_relevance as RetrievalRelevance)) {
      throw new Error("Human-gold document identity or relevance is invalid.");
    }
    if (!GOLD_DOCUMENT_FIELDS.slice(2).every((field) => Array.isArray(item[field]))) {
      throw new Error("Human-gold annotation fields must be arrays.");
    }
    documentIds.add(item.document_id.trim());
  }
  if (value.trust_status === REVIEWED_HUMAN_GOLD_STATUS && value.documents.some((item) => item.retrieval_relevance === "unreviewed")) {
    throw new Error("A reviewed human-gold file cannot contain unreviewed documents.");
  }
  if (value.trust_status === REVIEWED_HUMAN_GOLD_STATUS && !value.documents.some((item) => item.retrieval_relevance === "relevant")) {
    throw new Error("A reviewed human-gold file must contain at least one relevant document.");
  }
  return structuredClone(value) as unknown as HumanGoldDraft;
}

export function parseCorpusManifest(value: unknown): CorpusManifest {
  if (
    !isExactRecord(value, MANIFEST_ROOT_FIELDS)
    || value.schema_version !== HUMAN_GOLD_SCHEMA
    || !isBoundedText(value.mission_id, 180)
    || !isBoundedText(value.corpus_id, 120)
    || !isBoundedText(value.material, 300)
    || value.trust_status !== CORPUS_MANIFEST_STATUS
    || value.access_boundary !== CORPUS_ACCESS_BOUNDARY
    || !Array.isArray(value.documents)
    || value.documents.length < 1
    || value.documents.length > 250
  ) throw new Error("Unsupported authorized corpus manifest.");

  const documentIds = new Set<string>();
  for (const item of value.documents) {
    if (
      !isExactRecord(item, MANIFEST_DOCUMENT_FIELDS)
      || !isBoundedText(item.document_id, 180)
      || documentIds.has(item.document_id.trim())
      || !isBoundedText(item.title, 500)
      || (item.doi !== null && !isBoundedText(item.doi, 500))
      || item.access_policy !== DOCUMENT_ACCESS_POLICY
    ) throw new Error("Authorized corpus manifest document fields are invalid.");
    documentIds.add(item.document_id.trim());
  }
  return structuredClone(value) as unknown as CorpusManifest;
}

export function bindManifestToHumanGold(draft: HumanGoldDraft, manifest: CorpusManifest): CorpusManifest {
  if (draft.mission_id !== manifest.mission_id || draft.corpus_id !== manifest.corpus_id || draft.documents.length !== manifest.documents.length) {
    throw new Error("Corpus manifest does not match the human-gold identity or document count.");
  }
  const goldIds = new Set(draft.documents.map((item) => item.document_id));
  if (manifest.documents.some((item) => !goldIds.has(item.document_id))) {
    throw new Error("Corpus manifest document IDs do not match the human-gold review.");
  }
  return structuredClone(manifest);
}

export function corpusRelevanceReadiness(draft: HumanGoldDraft): CorpusRelevanceReadiness {
  const counts: Record<RetrievalRelevance, number> = { unreviewed: 0, relevant: 0, partially_relevant: 0, not_relevant: 0 };
  for (const item of draft.documents) counts[item.retrieval_relevance] += 1;
  const reviewedCount = draft.documents.length - counts.unreviewed;
  return {
    documentCount: draft.documents.length,
    reviewedCount,
    counts,
    readyForAttestation: counts.unreviewed === 0 && counts.relevant > 0,
  };
}

export function exportHumanGoldDraft(draft: HumanGoldDraft, independentlyAttested: boolean): HumanGoldDraft {
  const copy = structuredClone(draft);
  copy.trust_status = independentlyAttested && corpusRelevanceReadiness(copy).readyForAttestation
    ? REVIEWED_HUMAN_GOLD_STATUS
    : BLANK_HUMAN_GOLD_STATUS;
  return copy;
}

function isExactRecord(value: unknown, fields: readonly string[]): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === fields.length && fields.every((field) => Object.prototype.hasOwnProperty.call(value, field)));
}

function isBoundedText(value: unknown, maximum: number): value is string {
  return typeof value === "string" && Boolean(value.trim()) && value.trim().length <= maximum;
}
