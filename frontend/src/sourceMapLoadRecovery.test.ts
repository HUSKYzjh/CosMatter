import { describe, expect, it } from "vitest";

import { shouldAutoLoadRecordedSourceMap } from "./sourceMapLoadRecovery";

const ready = { taskKey: "pdf-1", hasLoader: true, ready: true, sourceMapRecorded: true, hasRecordedSegments: false, loading: false, attemptedFor: null };

describe("shouldAutoLoadRecordedSourceMap", () => {
  it("loads a recorded Source Map once for its active private task", () => {
    expect(shouldAutoLoadRecordedSourceMap(ready)).toBe(true);
    expect(shouldAutoLoadRecordedSourceMap({ ...ready, attemptedFor: "pdf-1" })).toBe(false);
  });

  it("keeps downstream recovery locked when the map cannot safely be loaded", () => {
    expect(shouldAutoLoadRecordedSourceMap({ ...ready, hasLoader: false })).toBe(false);
    expect(shouldAutoLoadRecordedSourceMap({ ...ready, hasRecordedSegments: true })).toBe(false);
    expect(shouldAutoLoadRecordedSourceMap({ ...ready, loading: true })).toBe(false);
    expect(shouldAutoLoadRecordedSourceMap({ ...ready, sourceMapRecorded: false })).toBe(false);
  });
});
