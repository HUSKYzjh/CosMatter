import type { LaunchCandidate } from "./Launchpad";

type Locale = "zh" | "en";
type Copy = { zh: string; en: string };
type Preset = { id: string; kind: LaunchCandidate["kind"]; question: Copy; material: Copy; property: Copy; scope: Copy; };

const presets: readonly Preset[] = [
  {
    id: "bfo-phase-boundary", kind: "contrast",
    question: { zh: "外延 BiFeO₃ 薄膜中，应变、厚度与氧化学势如何共同影响报告的相稳定性边界？", en: "How do strain, thickness, and oxygen chemical potential jointly affect reported phase-stability boundaries in epitaxial BiFeO₃ films?" },
    material: { zh: "BiFeO₃ 外延薄膜", en: "Epitaxial BiFeO₃ thin films" },
    property: { zh: "相稳定性边界与结构相", en: "Phase-stability boundaries and structural phase" },
    scope: { zh: "比较应变、厚度、氧分压／化学势、衬底与表征条件；区分直接测量与模型推断。", en: "Compare strain, thickness, oxygen pressure/chemical potential, substrate, and characterisation conditions; distinguish direct measurements from model inference." },
  },
  {
    id: "bfo-domain-coupling", kind: "mechanism",
    question: { zh: "BiFeO₃ 薄膜中的畴结构与铁电／反铁磁耦合报告，哪些样品和测量条件决定其是否可比较？", en: "Which sample and measurement conditions determine whether reports of domain structure and ferroelectric/antiferromagnetic coupling in BiFeO₃ films are comparable?" },
    material: { zh: "BiFeO₃ 薄膜与畴结构", en: "BiFeO₃ films and domain structures" },
    property: { zh: "铁电／磁有序耦合与畴响应", en: "Ferroelectric/magnetic-order coupling and domain response" },
    scope: { zh: "记录取向、应变、缺陷／氧空位、温度、场史、厚度与表征方法；只比较有明确定位的原始报告。", en: "Record orientation, strain, defects/oxygen vacancies, temperature, field history, thickness, and characterisation method; compare only explicitly located primary reports." },
  },
  {
    id: "bfo-defect-method", kind: "survey",
    question: { zh: "围绕 BiFeO₃ 薄膜缺陷与漏电行为，不同制备和测量协议报告了哪些可定位、可复核的差异？", en: "For defects and leakage behaviour in BiFeO₃ films, which located and reviewable differences are reported under different preparation and measurement protocols?" },
    material: { zh: "BiFeO₃ 薄膜、缺陷与电输运样品", en: "BiFeO₃ films, defects, and electrical-transport specimens" },
    property: { zh: "缺陷相关漏电与电学响应", en: "Defect-related leakage and electrical response" },
    scope: { zh: "比较沉积／退火、氧环境、电极、厚度、温度、偏压与测试协议；保留未报告条件。", en: "Compare deposition/annealing, oxygen environment, electrodes, thickness, temperature, bias, and test protocol; retain unreported conditions." },
  },
];

export type BfoTaskPresetId = typeof presets[number]["id"];
const presetIds = new Set<string>(presets.map((preset) => preset.id));
export function isBfoTaskPresetId(value: string | null | undefined): value is BfoTaskPresetId {
  return Boolean(value && presetIds.has(value));
}

/** Read-only mission templates; selecting one only fills an editable local brief. */
export function bfoTaskPresets(locale: Locale): LaunchCandidate[] {
  return presets.map((preset) => ({
    id: preset.id, kind: preset.kind,
    question: preset.question[locale], material: preset.material[locale], property: preset.property[locale], scope: preset.scope[locale],
  }));
}
