import type { RecordedSourceMapSegment } from "./localApi";

export type EvidenceDraftIssue = "candidate" | "segment" | "claim" | "conditions-json" | "conditions-required" | "confidence" | "confirmation" | "handler" | null;

export interface EvidenceDraftValidation {
  ready: boolean;
  issue: EvidenceDraftIssue;
  conditions: Record<string, string | number | null> | null;
  confidence: number | null;
}

const REQUIRED_CONDITIONS = ["sample_form", "strain_percent", "substrate", "thickness_nm", "temperature_k", "method"] as const;

/**
 * Mirrors only the browser-safe subset of the loopback EvidenceCard gate.
 * The server remains authoritative and revalidates the selected Source Map
 * segment, screening decision, and exact provenance binding.
 */
export function validateEvidenceDraft(input: {
  candidateLinked: boolean;
  segmentId: string;
  segments: RecordedSourceMapSegment[];
  claim: string;
  conditionsText: string;
  confidenceText: string;
  confirmed: boolean;
  hasRecordHandler: boolean;
}): EvidenceDraftValidation {
  if (!input.candidateLinked) return { ready: false, issue: "candidate", conditions: null, confidence: null };
  if (!input.segments.some((segment) => segment.segment_id === input.segmentId)) return { ready: false, issue: "segment", conditions: null, confidence: null };
  if (!input.claim.trim()) return { ready: false, issue: "claim", conditions: null, confidence: null };
  let conditions: Record<string, string | number | null>;
  try {
    const parsed: unknown = JSON.parse(input.conditionsText);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") return { ready: false, issue: "conditions-json", conditions: null, confidence: null };
    if (Object.values(parsed as Record<string, unknown>).some((value) => value !== null && typeof value !== "string" && typeof value !== "number")) return { ready: false, issue: "conditions-json", conditions: null, confidence: null };
    conditions = parsed as Record<string, string | number | null>;
  } catch {
    return { ready: false, issue: "conditions-json", conditions: null, confidence: null };
  }
  if (REQUIRED_CONDITIONS.some((key) => conditions[key] === null || conditions[key] === "" || conditions[key] === "unknown" || conditions[key] === undefined)) return { ready: false, issue: "conditions-required", conditions: null, confidence: null };
  const confidence = Number(input.confidenceText);
  if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) return { ready: false, issue: "confidence", conditions: null, confidence: null };
  if (!input.confirmed) return { ready: false, issue: "confirmation", conditions: null, confidence: null };
  if (!input.hasRecordHandler) return { ready: false, issue: "handler", conditions: null, confidence: null };
  return { ready: true, issue: null, conditions, confidence };
}
