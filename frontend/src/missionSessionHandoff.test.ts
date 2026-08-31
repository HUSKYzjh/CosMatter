import { describe, expect, it } from "vitest";

import { missionSessionHandoff } from "./missionSessionHandoff";

const base = { documentId: "paper-1", evidenceId: null, screeningAllowsSourceReview: false, privateFulltextReady: false, sourceMapRecorded: false, evidenceReady: false };

describe("missionSessionHandoff", () => {
  it("does not create a review anchor before a paper is explicitly selected", () => {
    expect(missionSessionHandoff({ ...base, documentId: null })).toEqual({ state: "awaiting_paper", documentId: null, evidenceId: null, destination: "graph" });
  });

  it("keeps a human inclusion decision below a private parse and recorded Source Map", () => {
    expect(missionSessionHandoff({ ...base, screeningAllowsSourceReview: true }).state).toBe("fulltext_authorized");
    expect(missionSessionHandoff({ ...base, screeningAllowsSourceReview: true, privateFulltextReady: true }).state).toBe("private_fulltext_ready");
    expect(missionSessionHandoff({ ...base, screeningAllowsSourceReview: true, privateFulltextReady: true, sourceMapRecorded: true }).state).toBe("source_map_recorded");
  });

  it("only advances to research extension after the existing evidence gate is passed", () => {
    const handoff = missionSessionHandoff({ ...base, evidenceId: "ev-1", sourceMapRecorded: true, evidenceReady: true });
    expect(handoff).toMatchObject({ state: "evidence_audited", documentId: "paper-1", evidenceId: "ev-1", destination: "horizon" });
  });
});
