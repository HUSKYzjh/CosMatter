import { describe, expect, it } from "vitest";
import { matchReaderEvidenceQuote } from "./readerEvidenceQuote";

const line = (number: number, text: string, truncated = false) => ({ number, text, truncated });

describe("verified evidence quote highlighting", () => {
  it("preserves surrounding text, line breaks and literal markup", () => {
    const lines = [line(5, "先看 🧪 [测量]"), line(6, "<5 K>。")];
    const parts = matchReaderEvidenceQuote(lines, { start: 5, end: 6 }, "[测量]\n<5 K>");
    expect(parts?.get(5)).toEqual({ before: "先看 🧪 ", quote: "[测量]", after: "" });
    expect(parts?.get(6)).toEqual({ before: "", quote: "<5 K>", after: "。" });
  });

  it("counts only matches inside the cited range, including overlapping matches", () => {
    const lines = [line(8, "300 K"), line(9, "also 300 K")];
    expect(matchReaderEvidenceQuote(lines, { start: 9, end: 9 }, "300 K")?.get(9)?.quote).toBe("300 K");
    expect(matchReaderEvidenceQuote(lines, { start: 8, end: 9 }, "300 K")).toBeNull();
    expect(matchReaderEvidenceQuote([line(1, "aaa")], { start: 1, end: 1 }, "aa")).toBeNull();
  });

  it("leaves only line-level provenance when a range is incomplete, truncated or has no exact match", () => {
    const range = { start: 10, end: 11 };
    expect(matchReaderEvidenceQuote([line(10, "300 K")], range, "300 K")).toBeNull();
    expect(matchReaderEvidenceQuote([line(10, "300 K"), line(11, "prefix", true)], range, "300 K")).toBeNull();
    expect(matchReaderEvidenceQuote([line(10, "300 K"), line(11, "500 K")], range, "300K")).toBeNull();
  });
});
