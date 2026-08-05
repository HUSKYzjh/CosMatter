export interface Mission {
  missionId: string;
  question: string;
  material: string;
  property: string;
  scope: string;
}

export interface ImportedBundle {
  mission: Mission;
  source: "demo" | "local-file";
}

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function readBundle(value: unknown): ImportedBundle {
  if (!isRecord(value) || !isRecord(value.mission)) {
    throw new Error("工件缺少 mission 对象。");
  }

  const mission = value.mission;
  const missionId = text(mission.mission_id);
  const question = text(mission.question);
  const material = text(mission.material);
  const property = text(mission.property_name);
  const scope = text(mission.scope);

  if (!missionId || !question || !material || !property || !scope) {
    throw new Error("工件 mission 字段不完整，无法导入。");
  }

  return {
    mission: { missionId, question, material, property, scope },
    source: "local-file"
  };
}

export const demoBundle: ImportedBundle = {
  source: "demo",
  mission: {
    missionId: "mission_demo_bfo",
    question: "为什么两篇论文对 BiFeO3 外延薄膜应变相变有不同结论？",
    material: "BiFeO3",
    property: "phase stability",
    scope: "epitaxial thin films"
  }
};
