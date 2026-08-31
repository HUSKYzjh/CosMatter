import { describe, expect, it } from "vitest";

import { createOperationActivity } from "./operationActivity";

describe("operation activity", () => {
  it("keeps a newer operation visible when an older request finishes late", () => {
    const activity = createOperationActivity();
    const older = activity.start("Older", "older request");
    const newer = activity.start("Newer", "newer request");

    expect(activity.finish(older.id)).toEqual(newer);
    expect(activity.current()).toEqual(newer);
  });

  it("clears the visible operation only when its own request finishes", () => {
    const activity = createOperationActivity();
    const current = activity.start("Current", "current request");

    expect(activity.finish(current.id)).toBeNull();
    expect(activity.current()).toBeNull();
  });
});
