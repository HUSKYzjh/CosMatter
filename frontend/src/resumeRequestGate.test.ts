import { describe, expect, it } from "vitest";
import { queuedResumeCanCommit } from "./resumeRequestGate";

describe("queued resume gate", () => {
  it("permits a package only while its original task epoch remains current", () => {
    expect(queuedResumeCanCommit(12, 12)).toBe(true);
    expect(queuedResumeCanCommit(12, 13)).toBe(false);
  });
});
