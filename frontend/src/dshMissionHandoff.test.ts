import { describe, expect, it } from "vitest";
import { prepareDshMissionHandoff } from "./dshMissionHandoff";
import type { LaunchMissionBoundary, LaunchMissionField } from "./launchMissionValidation";

const empty: LaunchMissionBoundary = { question: "", material: "", property: "", scope: "" };
const brief: LaunchMissionBoundary = {
  question: 'How does the "A" treatment affect lattice spacing?\nCompare both series.',
  material: "oxide A; oxide B", property: "lattice spacing", scope: "measured films — including the `control`",
};

function copiedFields(message: string) {
  return JSON.parse(message.slice(message.indexOf("\n\n") + 2));
}

describe("DSH mission draft handoff", () => {
  it("copies the four edited fields as JSON and omits background data and permissions", () => {
    const candidate = { ...brief, material: "  oxide B  ", prompt: "earlier private draft", run_id: "old_run", consent: true };
    const text = prepareDshMissionHandoff(candidate, "en")!.message!;
    expect(copiedFields(text)).toEqual({ ...brief, material: "oxide B" });
    expect(text).toContain("cosmatter_mission_create once");
    expect(text).toContain("workbench_url");
    expect(text).not.toMatch(/earlier private draft|old_run|consent|--port/);
    expect(candidate.material).toBe("  oxide B  ");
  });

  it("carries a raw question into chat and asks for the missing boundaries", () => {
    const message = prepareDshMissionHandoff({ ...empty, question: brief.question }, "zh")!.message!;
    expect(copiedFields(message)).toEqual({ question: brief.question });
    for (const label of ["研究对象", "研究目标", "比较范围"]) expect(message).toContain(label);
    expect(message).toContain("等我确认");
    expect(message).not.toContain("cosmatter_mission_create");
  });

  it("keeps supplied fields while asking the user to replace visible placeholders", () => {
    const partial = { ...brief, material: "待人工确认", scope: "to be completed" };
    const result = prepareDshMissionHandoff(partial, "en")!;
    expect(copiedFields(result.message!)).toEqual({ question: brief.question, property: brief.property });
    expect(result.message).toContain("material and study scope");
    expect(result.message).not.toMatch(/cosmatter_mission_create|待人工确认|to be completed/);
  });

  it("keeps the original question in a clarification when it mentions an unspecified condition", () => {
    const question = "Which sample temperatures were not specified in the report?";
    const message = prepareDshMissionHandoff({ ...empty, question }, "en")!.message!;
    expect(copiedFields(message)).toEqual({ question });
    expect(message).toContain("wait for me to confirm");
    expect(message).not.toContain("cosmatter_mission_create");
  });

  it("copies the original research scope for both a complete brief and a partial brief", () => {
    const scope = "分别比较已标注样品和测量频率未指定的样品";
    const complete = { ...brief, scope };
    const message = prepareDshMissionHandoff(complete, "zh")!.message!;
    expect(copiedFields(message)).toEqual(complete);
    expect(message).toContain("cosmatter_mission_create");
    const partial = prepareDshMissionHandoff({ ...complete, question: "待确认" }, "zh")!.message!;
    expect(copiedFields(partial)).toEqual({ material: brief.material, property: brief.property, scope });
    expect(partial).toContain("请先向我询问研究问题");
  });

  it("offers no copy for blank drafts and for a lone placeholder boundary", () => {
    expect(prepareDshMissionHandoff({ ...empty, question: "  " }, "zh")).toBeNull();
    expect(prepareDshMissionHandoff({ ...empty, material: "not specified" }, "en")?.message).toBeNull();
    expect(prepareDshMissionHandoff({ ...empty, question: " Not specified. " }, "en")?.message).toBeNull();
  });

  it.each<[LaunchMissionField, number]>([["question", 3000], ["material", 300], ["property", 300], ["scope", 1000]])(
    "accepts the native %s limit and asks the user to shorten overflow without truncating it", (key, max) => {
      // Astral characters take two UTF-16 units in the native JavaScript client.
      const value = "🧪".repeat(max / 2);
      const result = prepareDshMissionHandoff({ ...brief, [key]: ` ${value} ` }, "en")!;
      expect(copiedFields(result.message!)[key]).toBe(value);
      expect(result.overLimit).toEqual([]);
      const oversized = { ...brief, [key]: `${value}a` };
      const blocked = prepareDshMissionHandoff(oversized, "en")!;
      expect(blocked.message).toBeNull();
      expect(blocked.overLimit).toEqual([{ field: key, label: expect.any(String), length: max + 1, limit: max }]);
      expect(blocked.hint).not.toContain(value);
      expect(oversized[key]).toBe(`${value}a`);
    },
  );

  it("reports every oversized field with its localized label and trimmed length", () => {
    const oversized = { ...brief, material: ` ${"材".repeat(301)} `, scope: "🧪".repeat(501) };
    expect(prepareDshMissionHandoff(oversized, "zh")?.overLimit).toEqual([
      { field: "material", label: "研究对象", length: 301, limit: 300 },
      { field: "scope", label: "比较范围", length: 1002, limit: 1000 },
    ]);
  });
});
