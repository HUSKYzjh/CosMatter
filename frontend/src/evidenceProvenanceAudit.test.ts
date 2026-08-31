import { expect, it } from "vitest";

import { evidenceProvenanceAuditComplete } from "./evidenceProvenanceAudit";

it("requires every accepted card to have an exact Source Map match", () => {
  expect(evidenceProvenanceAuditComplete({ acceptedEvidenceCount: 2, exactSourceMapMatchCount: 2, manualLocatorOnlyCount: 0, exactSourceMapMatchRate: 1 })).toBe(true);
  expect(evidenceProvenanceAuditComplete({ acceptedEvidenceCount: 2, exactSourceMapMatchCount: 1, manualLocatorOnlyCount: 1, exactSourceMapMatchRate: .5 })).toBe(false);
  expect(evidenceProvenanceAuditComplete({ acceptedEvidenceCount: 2, exactSourceMapMatchCount: 2, manualLocatorOnlyCount: 0, exactSourceMapMatchRate: 1 }, 3)).toBe(false);
  expect(evidenceProvenanceAuditComplete(null)).toBe(false);
});
