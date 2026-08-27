import { describe, expect, it } from "vitest";

import { isCurrentCandidateResponse } from "./launchCandidateRequest";

describe("launch candidate request guard", () => {
  it("accepts only the latest response for the unchanged prompt", () => {
    expect(isCurrentCandidateResponse(3, 3, "compare film phases", "compare film phases")).toBe(true);
  });

  it("rejects a response superseded by a newer draft", () => {
    expect(isCurrentCandidateResponse(2, 3, "old prompt", "new prompt")).toBe(false);
  });

  it("rejects a response whose prompt changed even when its numeric token matches", () => {
    expect(isCurrentCandidateResponse(3, 3, "old prompt", "new prompt")).toBe(false);
  });
});
