import { describe, expect, it } from "vitest";

import { availableRetrievalSources, reconcileRetrievalSources } from "./localApiCapabilities";

describe("local API capability snapshot", () => {
  it("lists only providers confirmed by the latest local status response", () => {
    const providers = { sciverse: true, openalex: false, crossref: true, deepseek: true };
    expect(availableRetrievalSources(providers)).toEqual(["sciverse", "crossref"]);
  });

  it("keeps a viable user selection and replaces a fully stale selection", () => {
    const providers = { sciverse: true, openalex: false, crossref: true };
    expect(reconcileRetrievalSources(["crossref"], providers)).toEqual(["crossref"]);
    expect(reconcileRetrievalSources(["openalex"], providers)).toEqual(["sciverse", "crossref"]);
  });
});
