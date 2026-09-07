import { describe, expect, it } from "vitest";

import { readBundle } from "./model";

const mission = { mission_id: "mission-route", question: "Can configuration search improve the target property without a surrogate?", material: "(Pb_x Sr_1-x)TiO3", property_name: "dielectric and piezoelectric response", scope: "MD-only property evaluation" };

const item = (overrides: Record<string, unknown> = {}) => ({
  order: 1,
  document_id: "doc-algorithm",
  title: "Replica exchange configuration search",
  publication_year: 2025,
  source: "fixture",
  locator_hint: null,
  track: "primary",
  role: "primary_candidate",
  content_status: "metadata_only",
  evidence_ids: [],
  doi: null,
  routing_signals: [],
  research_track: "algorithm",
  route_eligibility: "primary_allowed",
  facet_signals: ["configuration_search_method"],
  ...overrides,
});

const policy = (overrides: Record<string, unknown> = {}) => ({
  schema_version: "cosmatter.research-route-policy/v1",
  trust_status: "deterministic_metadata_routing_not_relevance_judgment",
  classification_status: "current_candidate_pool",
  track_minimums: { exact_material: 4, mechanism_analogue: 3, algorithm: 4 },
  counterevidence_minimum: 1,
  available_track_counts: { exact_material: 0, mechanism_analogue: 0, algorithm: 1 },
  selected_track_counts: { exact_material: 0, mechanism_analogue: 0, algorithm: 1 },
  available_counterevidence_count: 0,
  selected_counterevidence_count: 0,
  ...overrides,
});

const guide = (overrides: Record<string, unknown> = {}) => ({
  schema_version: "1.3",
  mission_id: "mission-route",
  trust_status: "derived_from_approved_artifacts",
  items: [item()],
  caveats: ["Navigation only; not a relevance judgment."],
  route_policy: policy(),
  ...overrides,
});

describe("research guide projection", () => {
  it("accepts a consistent backend route without projecting provider scores or query text", () => {
    const bundle = readBundle({ mission, research_guide: guide() });
    expect(bundle.researchGuide).toMatchObject({
      trustStatus: "derived_from_approved_artifacts",
      items: [{ documentId: "doc-algorithm", researchTrack: "algorithm", routeEligibility: "primary_allowed" }],
      routePolicy: { classificationStatus: "current_candidate_pool", selectedCounterevidenceCount: 0 },
    });
    expect(JSON.stringify(bundle.researchGuide)).not.toContain("query");
    expect(JSON.stringify(bundle.researchGuide)).not.toContain("score");
  });

  it("fails closed when policy counts or fields are inconsistent", () => {
    const wrongCounts = readBundle({ mission, research_guide: guide({ route_policy: policy({ selected_track_counts: { exact_material: 1, mechanism_analogue: 0, algorithm: 0 } }) }) });
    const wrongQuota = readBundle({ mission, research_guide: guide({ route_policy: policy({ track_minimums: { exact_material: 0, mechanism_analogue: 0, algorithm: 0 } }) }) });
    const extraField = readBundle({ mission, research_guide: guide({ items: [item({ relevance_score: 0.99 })] }) });
    const wrongMission = readBundle({ mission, research_guide: guide({ mission_id: "other" }) });
    expect(wrongCounts.researchGuide).toBeNull();
    expect(wrongQuota.researchGuide).toBeNull();
    expect(extraField.researchGuide).toBeNull();
    expect(wrongMission.researchGuide).toBeNull();
  });
});
