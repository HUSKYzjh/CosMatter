import { describe, expect, it } from "vitest";

import { bfoTemplateLink, bfoTemplateLinkMatchesMission } from "./bfoTemplateLink";

describe("BFO template session link", () => {
  it("links only known BFO templates to the explicit mission that confirmed them", () => {
    expect(bfoTemplateLink("mission-1", "bfo-phase-boundary")).toEqual({ missionId: "mission-1", templateId: "bfo-phase-boundary" });
    expect(bfoTemplateLink("mission-1", "contrast")).toBeNull();
  });

  it("does not carry a template contract across a different mission", () => {
    const link = bfoTemplateLink("mission-1", "bfo-domain-coupling");
    expect(bfoTemplateLinkMatchesMission(link, "mission-1")).toBe(true);
    expect(bfoTemplateLinkMatchesMission(link, "mission-2")).toBe(false);
  });
});
