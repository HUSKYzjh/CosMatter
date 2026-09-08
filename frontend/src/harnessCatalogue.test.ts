import { expect, it } from "vitest";

import { isHarnessPluginCatalogue } from "./localApi";

const descriptor = (pluginId = "literature.metadata_retrieval") => ({
  plugin_id: pluginId,
  title: "书目元数据检索",
  domain: "retrieval",
  entrypoint: "cosmatter.metadata_search:MetadataSearch",
  api_version: "2.0" as const,
  capabilities: ["metadata_search"],
  data_classification: "public_metadata",
  automation_class: "external_authorized" as const,
  required_authorizations: ["mission_scoped_egress_consent"],
  requires_human_review: false,
  contract: { input_schema: "cosmatter.plugin-input/v1", output_schema: "cosmatter.plugin-output/v1", execution_mode: "provider_request", lifecycle: "authorize -> dispatch -> receipt" },
  execution_boundary: "Descriptor only; no provider request is granted by this catalogue.",
});

it("accepts a bounded static Harness catalogue", () => {
  expect(isHarnessPluginCatalogue({ catalogue_api_version: "2.0", plugins: [descriptor()], trust_status: "static_catalogue_not_plugin_execution_or_evidence_acceptance" })).toBe(true);
});

it("rejects duplicate identifiers and execution-looking trust labels", () => {
  expect(isHarnessPluginCatalogue({ catalogue_api_version: "2.0", plugins: [descriptor(), descriptor()], trust_status: "static_catalogue_not_plugin_execution_or_evidence_acceptance" })).toBe(false);
  expect(isHarnessPluginCatalogue({ catalogue_api_version: "2.0", plugins: [descriptor()], trust_status: "plugins_enabled" })).toBe(false);
});
