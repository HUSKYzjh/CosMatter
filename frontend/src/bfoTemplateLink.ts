import { isBfoTaskPresetId, type BfoTaskPresetId } from "./bfoTaskPresets";

export interface BfoTemplateLink {
  missionId: string;
  templateId: BfoTaskPresetId;
}

/** A template link is local UI context, not a run artifact or scientific claim. */
export function bfoTemplateLink(missionId: string, templateId: string | null | undefined): BfoTemplateLink | null {
  return missionId.trim() && isBfoTaskPresetId(templateId) ? { missionId, templateId } : null;
}

export function bfoTemplateLinkMatchesMission(link: BfoTemplateLink | null, missionId: string): boolean {
  return Boolean(link && link.missionId === missionId);
}
