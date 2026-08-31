import { describe, expect, it } from "vitest";

import { demoBundle, readBundle } from "./model";
import { evidenceMaturityProjection } from "./evidenceMaturityProjection";

const base = { schema_version: "1.0", mission: { mission_id: "maturity-demo", question: "Can the claim be bounded?", material: "BiFeO3", property_name: "phase stability", scope: "epitaxial thin films" } };
const support = [{ run_id: "run-1", document_id: "doc-1", document_version: "preprint", independence_group: "group-1", source_map_status: "automated_trial_only", data_status: "not_checked", conditions_status: "not_checked", stance: "supports" }];
const reproducibility = { protocol_status: "not_checked", materials_status: "not_checked", measurement_status: "not_checked", raw_data_status: "not_checked", assessment: "not_assessed" };
const independentReproduction = { status: "not_attempted", independent_run_id: null, result_comparison: "not_available", review_status: "not_reviewed" };
const claim = (overrides = {}) => ({ claim_id: "claim-1", claim_text: "A bounded literature statement.", maturity_level: "literature_mentioned", assessment_authority: "delegated_automated_trial", support_records: support, reproducibility, independent_reproduction: independentReproduction, limitations: ["Not human reviewed."], ...overrides });

describe("evidence maturity projection", () => {
  it("keeps the demo bundle unclassified when no registry is imported", () => {
    const projection = evidenceMaturityProjection(demoBundle);
    expect(projection.registry).toBeNull();
    expect(demoBundle.evidenceMaturityRegistryStatus).toBe("not_supplied");
    expect(Object.values(projection.counts)).toEqual([0, 0, 0, 0]);
  });

  it("keeps a delivery-rejected registry out of the read-only projection", () => {
    const bundle = readBundle({ ...base, evidence_maturity_registry_delivery_status: "rejected" });
    expect(bundle.evidenceMaturityRegistry).toBeNull();
    expect(bundle.evidenceMaturityRegistryStatus).toBe("rejected");
  });

  it("rejects an accepted delivery marker when its registry is absent", () => {
    const bundle = readBundle({ ...base, evidence_maturity_registry_delivery_status: "accepted" });
    expect(bundle.evidenceMaturityRegistry).toBeNull();
    expect(bundle.evidenceMaturityRegistryStatus).toBe("rejected");
  });

  it("projects only schema-identified maturity claims", () => {
    const bundle = readBundle({ ...base, evidence_maturity_registry_delivery_status: "accepted", evidence_maturity_registry: { schema_version: "cosmatter.evidence-maturity-registry/v1", registry_id: "registry-1", question_id: "maturity-demo", trust_status: "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence", claims: [claim()] } });
    const projection = evidenceMaturityProjection(bundle);
    expect(projection.registry?.claims).toHaveLength(1);
    expect(projection.registry?.claims[0]).toMatchObject({ supportRecordCount: 1, supportDocumentCount: 1, independenceGroupCount: 1, sourceMapStatuses: ["automated_trial_only"] });
    expect(projection.counts.literature_mentioned).toBe(1);
    expect(projection.counts.data_supported).toBe(0);
  });

  it("does not trust a syntactically valid registry without an accepted delivery binding", () => {
    const bundle = readBundle({ ...base, evidence_maturity_registry: { schema_version: "cosmatter.evidence-maturity-registry/v1", registry_id: "registry-1", question_id: "maturity-demo", trust_status: "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence", claims: [claim()] } });
    expect(bundle.evidenceMaturityRegistry).toBeNull();
    expect(bundle.evidenceMaturityRegistryStatus).toBe("rejected");
    expect(evidenceMaturityProjection(bundle).counts).toEqual({ literature_mentioned: 0, data_supported: 0, reproducibility_ready: 0, independently_reproduced: 0 });
  });

  it("rejects an otherwise accepted registry that belongs to a different mission", () => {
    const bundle = readBundle({ ...base, evidence_maturity_registry_delivery_status: "accepted", evidence_maturity_registry: { schema_version: "cosmatter.evidence-maturity-registry/v1", registry_id: "registry-1", question_id: "other-mission", trust_status: "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence", claims: [claim()] } });
    expect(bundle.evidenceMaturityRegistry).toBeNull();
    expect(bundle.evidenceMaturityRegistryStatus).toBe("rejected");
  });

  it("rejects a registry with an unknown maturity level", () => {
    const bundle = readBundle({ ...base, evidence_maturity_registry: { schema_version: "cosmatter.evidence-maturity-registry/v1", registry_id: "registry-1", question_id: "maturity-demo", trust_status: "human_reviewed_evidence_maturity_registry_not_scientific_conclusion", claims: [claim({ maturity_level: "proven", assessment_authority: "human_data_review" })] } });
    expect(evidenceMaturityProjection(bundle).registry).toBeNull();
  });

  it("rejects an automated trial that attempts a data-supported upgrade", () => {
    const bundle = readBundle({ ...base, evidence_maturity_registry: { schema_version: "cosmatter.evidence-maturity-registry/v1", registry_id: "registry-1", question_id: "maturity-demo", trust_status: "delegated_automated_trial_evidence_maturity_registry_not_scientific_evidence", claims: [claim({ maturity_level: "data_supported" })] } });
    expect(evidenceMaturityProjection(bundle).registry).toBeNull();
    expect(bundle.evidenceMaturityRegistryStatus).toBe("rejected");
  });

  it("rejects a human-labelled data upgrade without reviewed numeric data and complete conditions", () => {
    const bundle = readBundle({ ...base, evidence_maturity_registry: { schema_version: "cosmatter.evidence-maturity-registry/v1", registry_id: "registry-1", question_id: "maturity-demo", trust_status: "human_reviewed_evidence_maturity_registry_not_scientific_conclusion", claims: [claim({ maturity_level: "data_supported", assessment_authority: "human_data_review" })] } });
    expect(evidenceMaturityProjection(bundle).registry).toBeNull();
  });

  it("rejects independent reproduction without its human-reviewed independent run", () => {
    const bundle = readBundle({ ...base, evidence_maturity_registry: { schema_version: "cosmatter.evidence-maturity-registry/v1", registry_id: "registry-1", question_id: "maturity-demo", trust_status: "human_reviewed_evidence_maturity_registry_not_scientific_conclusion", claims: [claim({ maturity_level: "independently_reproduced", assessment_authority: "independent_reproduction_review" })] } });
    expect(evidenceMaturityProjection(bundle).registry).toBeNull();
  });

  it("accepts only a distinct, tolerance-confirmed independent reproduction", () => {
    const reviewedSupport = [{ ...support[0], source_map_status: "human_reviewed", data_status: "numeric_or_figure_data_human_checked", conditions_status: "complete_human_checked" }];
    const accepted = readBundle({ ...base, evidence_maturity_registry_delivery_status: "accepted", evidence_maturity_registry: { schema_version: "cosmatter.evidence-maturity-registry/v1", registry_id: "registry-1", question_id: "maturity-demo", trust_status: "human_reviewed_evidence_maturity_registry_not_scientific_conclusion", claims: [claim({ maturity_level: "independently_reproduced", assessment_authority: "independent_reproduction_review", support_records: reviewedSupport, independent_reproduction: { status: "replicated", independent_run_id: "lab-run-2", result_comparison: "within_predefined_tolerance", review_status: "human_reviewed" } })] } });
    expect(accepted.evidenceMaturityRegistryStatus).toBe("accepted");
    const rejected = readBundle({ ...base, evidence_maturity_registry: { schema_version: "cosmatter.evidence-maturity-registry/v1", registry_id: "registry-1", question_id: "maturity-demo", trust_status: "human_reviewed_evidence_maturity_registry_not_scientific_conclusion", claims: [claim({ maturity_level: "independently_reproduced", assessment_authority: "independent_reproduction_review", support_records: reviewedSupport, independent_reproduction: { status: "not_replicated", independent_run_id: "lab-run-2", result_comparison: "outside_predefined_tolerance", review_status: "human_reviewed" } })] } });
    expect(rejected.evidenceMaturityRegistryStatus).toBe("rejected");
  });
});
