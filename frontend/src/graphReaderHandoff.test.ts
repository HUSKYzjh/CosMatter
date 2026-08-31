import { describe, expect, it } from "vitest";

import { readerRouteAfterCommittedSelection } from "./graphReaderHandoff";

describe("graph reader handoff", () => {
  it("opens the reader only after the matching selection has committed", () => {
    expect(readerRouteAfterCommittedSelection(true)).toBe("reader");
  });

  it("keeps the graph active when selection is rejected", () => {
    expect(readerRouteAfterCommittedSelection(false)).toBeNull();
  });
});
