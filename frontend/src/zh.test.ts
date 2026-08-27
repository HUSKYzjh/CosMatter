import { afterEach, describe, expect, it } from "vitest";

import { setUiLanguage, zh } from "./zh";

afterEach(() => setUiLanguage("zh"));

describe("UI language state", () => {
  it("switches dictionary text between Chinese and English", () => {
    setUiLanguage("en");
    expect(zh("Fleet Bridge")).toBe("Fleet Bridge");
    expect(zh("Paper reading desk")).toBe("Paper reading desk");

    setUiLanguage("zh");
    expect(zh("Fleet Bridge", "舰桥")).toBe("舰桥");
    expect(zh("Paper reading desk")).toBe("论文阅读台");
    expect(zh("Research extension")).toBe("研究拓展");
  });
});
