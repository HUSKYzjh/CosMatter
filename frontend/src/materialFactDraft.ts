const FACT_CATEGORIES = new Set([
  "composition", "structure", "property", "processing", "experimental_condition", "simulation_method",
]);

export type MaterialFactDraftIssue = "facts" | "identity" | "duplicate-id" | "category" | "segment" | "value" | "unit" | "qualifiers-json" | "qualifiers" | "confirmation" | "handler" | null;

export interface MaterialFactDraftInput {
  factId: string;
  segmentId: string;
  category: string;
  name: string;
  value: string;
  unit: string;
  normalizedValue: string;
  normalizedUnit: string;
  qualifiersJson: string;
}

export interface MaterialFactDraftValidation {
  ready: boolean;
  issue: MaterialFactDraftIssue;
}

const optionalShortText = (value: string, maximum: number) => !value.trim() || value.trim().length <= maximum;

/**
 * Browser-safe mirror of the loopback material-fact review shape checks.
 * Unit conversion consistency intentionally remains authoritative on the
 * local service, where the shared normalization registry is available.
 */
export function validateMaterialFactDraft(input: {
  facts: MaterialFactDraftInput[];
  segmentIds: readonly string[];
  confirmed: boolean;
  hasRecordHandler: boolean;
}): MaterialFactDraftValidation {
  if (input.facts.length < 1 || input.facts.length > 48) return { ready: false, issue: "facts" };
  const knownSegments = new Set(input.segmentIds);
  const factIds = new Set<string>();
  for (const fact of input.facts) {
    const factId = fact.factId.trim();
    const name = fact.name.trim();
    if (!factId || factId.length > 120 || !name || name.length > 180) return { ready: false, issue: "identity" };
    if (factIds.has(factId)) return { ready: false, issue: "duplicate-id" };
    factIds.add(factId);
    if (!FACT_CATEGORIES.has(fact.category)) return { ready: false, issue: "category" };
    if (!knownSegments.has(fact.segmentId)) return { ready: false, issue: "segment" };
    if (!optionalShortText(fact.value, 500) || !optionalShortText(fact.normalizedValue, 500)) return { ready: false, issue: "value" };
    if (!optionalShortText(fact.unit, 80) || !optionalShortText(fact.normalizedUnit, 80)) return { ready: false, issue: "unit" };
    let qualifiers: unknown;
    try { qualifiers = JSON.parse(fact.qualifiersJson); } catch { return { ready: false, issue: "qualifiers-json" }; }
    if (!qualifiers || Array.isArray(qualifiers) || typeof qualifiers !== "object") return { ready: false, issue: "qualifiers-json" };
    const entries = Object.entries(qualifiers as Record<string, unknown>);
    if (entries.length > 12 || entries.some(([key, value]) => !key.trim() || key.length > 100 || value !== null && (typeof value !== "string" && typeof value !== "number" || typeof value === "number" && !Number.isFinite(value)) || typeof value === "string" && (!value.trim() || value.length > 500))) return { ready: false, issue: "qualifiers" };
  }
  if (!input.confirmed) return { ready: false, issue: "confirmation" };
  if (!input.hasRecordHandler) return { ready: false, issue: "handler" };
  return { ready: true, issue: null };
}
