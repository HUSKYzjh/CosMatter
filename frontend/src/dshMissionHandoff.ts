import type { UiLocale } from "./fleetRegistry";
import { launchMissionMissingFields, type LaunchMissionBoundary, type LaunchMissionField } from "./launchMissionValidation";

// Keep the limits aligned with the native cosmatter_mission_create client.
const fields = [
  { key: "question", max: 3000, zh: "研究问题", en: "research question" },
  { key: "material", max: 300, zh: "研究对象", en: "material" },
  { key: "property", max: 300, zh: "研究目标", en: "target property" },
  { key: "scope", max: 1000, zh: "比较范围", en: "study scope" },
] as const;

interface DshMissionHandoff {
  hint: string;
  message: string | null;
  overLimit: { field: LaunchMissionField; label: string; length: number; limit: number }[];
}

export function prepareDshMissionHandoff(draft: LaunchMissionBoundary, locale: UiLocale): DshMissionHandoff | null {
  // Launch candidates may also carry UI identifiers and suggested routes.
  const values = { question: draft.question.trim(), material: draft.material.trim(), property: draft.property.trim(), scope: draft.scope.trim() };
  if (fields.every(({ key }) => !values[key])) return null;

  const zh = locale === "zh";
  const list = new Intl.ListFormat(locale, { type: "conjunction" });
  const overLimit = fields.filter(({ key, max }) => values[key].length > max)
    .map(field => ({ field: field.key, label: field[locale], length: values[field.key].length, limit: field.max }));
  if (overLimit.length) {
    return { message: null, overLimit, hint: zh ? "请先缩短以下字段，再复制草稿。" : "Shorten these fields before copying the draft." };
  }

  const missing = launchMissionMissingFields(values);
  let instruction: string;
  let hint: string;
  let data: Partial<LaunchMissionBoundary> = values;
  if (missing.length) {
    const labels = list.format(fields.filter(({ key }) => missing.includes(key)).map(field => field[locale]));
    hint = zh ? `请在 DSH 聊天中补齐${labels}，再确认任务。` : `Complete the ${labels} in DSH chat before confirming the mission.`;
    const provided = fields.filter(({ key }) => !missing.includes(key));
    if (!provided.length) return { message: null, overLimit, hint: zh ? "请先在任务草稿中填写研究问题或研究边界。" : "Enter a research question or study boundary in the draft first." };
    data = Object.fromEntries(provided.map(({ key }) => [key, values[key]]));
    instruction = zh ? `这是我的研究草稿。请先向我询问${labels}，等我确认完整简报后再创建本机任务。`
      : `Here is my research draft. Ask me for the ${labels} and wait for me to confirm the completed brief before creating a local mission.`;
  } else {
    hint = zh ? "将简报粘贴到 DSH 聊天框，核对后发送。" : "Paste the brief into DSH chat, review it, then send it.";
    instruction = zh ? "请使用以下简报字段调用一次 cosmatter_mission_create 创建本机任务，并返回 workbench_url。"
      : "Use the following brief fields to call cosmatter_mission_create once, create the local mission, and return workbench_url.";
  }
  return { hint, overLimit, message: `${instruction}\n\n${JSON.stringify(data, null, 2)}` };
}
