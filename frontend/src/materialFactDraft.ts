const FACT_CATEGORIES = new Set([
  "composition", "structure", "property", "processing", "experimental_condition", "simulation_method",
]);

export type MaterialFactDraftIssue = "facts" | "identity" | "duplicate-id" | "category" | "segment" | "value" | "unit" | "conversion" | "qualifiers-json" | "qualifiers" | "confirmation" | "handler" | null;

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

// This browser preflight intentionally mirrors only the explicit, deterministic
// subset of the loopback validator. It never infers a quantity from a field name
// or prose; unknown units and non-numeric values remain reviewable.
const unitAliases: Record<string, string> = {
  m: "m", cm: "cm", mm: "mm", um: "um", nm: "nm", pm: "pm", angstrom: "angstrom", å: "angstrom", a0: "bohr", bohr: "bohr",
  k: "k", kelvin: "k", degc: "degc", "°c": "degc", celsius: "degc",
  pa: "pa", kpa: "kpa", mpa: "mpa", gpa: "gpa", bar: "bar",
  ev: "ev", mev: "mev", kev: "kev", j: "j",
  "c/m2": "c/m2", "uc/cm2": "uc/cm2", "v/m": "v/m", "kv/cm": "kv/cm", "mv/cm": "mv/cm",
  "%": "percent", percent: "percent", fraction: "fraction",
  "a/m": "a/m", "ka/m": "ka/m", "ma/m": "ma/m", "emu/cm3": "emu/cm3",
  hz: "hz", khz: "khz", mhz: "mhz", ghz: "ghz", "kg/m3": "kg/m3", "g/cm3": "g/cm3",
};
const unitFactors: Record<string, Record<string, number>> = {
  length: { m: 1, cm: 1e-2, mm: 1e-3, um: 1e-6, nm: 1e-9, pm: 1e-12, angstrom: 1e-10, bohr: 5.29177210903e-11 },
  pressure: { pa: 1, kpa: 1e3, mpa: 1e6, gpa: 1e9, bar: 1e5 }, energy: { ev: 1, mev: 1e-3, kev: 1e3, j: 6.241509074e18 },
  polarization: { "c/m2": 1, "uc/cm2": 1e-2 }, electric_field: { "v/m": 1, "kv/cm": 1e5, "mv/cm": 1e8 },
  strain: { fraction: 1, percent: 1e-2 }, magnetization: { "a/m": 1, "ka/m": 1e3, "ma/m": 1e6, "emu/cm3": 1e3 },
  frequency: { hz: 1, khz: 1e3, mhz: 1e6, ghz: 1e9 }, density: { "kg/m3": 1, "g/cm3": 1e3 },
};
const canonicalUnit = (value: string) => unitAliases[value.normalize("NFKC").toLowerCase().replace(/\s/g, "").replace(/\^/g, "").replace(/[μµ]/g, "u")];
const numericValue = (value: string) => value.trim() ? Number(value) : null;
const unitFamily = (unit: string) => unit === "k" || unit === "degc" ? "temperature" : Object.entries(unitFactors).find(([, factors]) => unit in factors)?.[0];
function hasConsistentKnownConversion(value: string, unit: string, normalizedValue: string, normalizedUnit: string): boolean {
  const sourceValue = numericValue(value); const targetValue = numericValue(normalizedValue);
  if (sourceValue === null || targetValue === null || !Number.isFinite(sourceValue) || !Number.isFinite(targetValue)) return true;
  const sourceUnit = canonicalUnit(unit); const targetUnit = canonicalUnit(normalizedUnit);
  if (!sourceUnit || !targetUnit) return true;
  const family = unitFamily(sourceUnit);
  if (!family || family !== unitFamily(targetUnit)) return false;
  const expected = family === "temperature"
    ? (targetUnit === "k" ? (sourceUnit === "k" ? sourceValue : sourceValue + 273.15) : (sourceUnit === "k" ? sourceValue - 273.15 : sourceValue))
    : sourceValue * unitFactors[family][sourceUnit] / unitFactors[family][targetUnit];
  return Math.abs(expected - targetValue) <= Math.max(1e-10, Math.abs(expected) * 1e-7);
}

/**
 * Browser-safe mirror of the loopback material-fact review shape checks.
 * Known numeric conversions receive an immediate advisory check here; the
 * local service remains authoritative and repeats its own validation.
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
    if (!hasConsistentKnownConversion(fact.value, fact.unit, fact.normalizedValue, fact.normalizedUnit)) return { ready: false, issue: "conversion" };
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
