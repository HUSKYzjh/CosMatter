import { For, Show, createMemo } from "solid-js";

import { EVIDENCE_MATURITY_LEVELS, evidenceMaturityProjection } from "./evidenceMaturityProjection";
import type { EvidenceMaturityLevel, ImportedBundle } from "./model";

const copy = (locale: "zh" | "en", zh: string, en: string) => locale === "zh" ? zh : en;
const levelCopy: Record<EvidenceMaturityLevel, { zh: string; en: string; detailZh: string; detailEn: string }> = {
  literature_mentioned: { zh: "文献提及", en: "Literature mentioned", detailZh: "已识别文献讨论或报告该主张；不等于数据核验。", detailEn: "An identified paper discusses or reports the claim; data are not yet verified." },
  data_supported: { zh: "有数据支撑", en: "Data supported", detailZh: "人工核对定位、数据/图表与条件；不作跨条件泛化。", detailEn: "Human-reviewed locators, data/figures, and conditions; no cross-condition generalisation." },
  reproducibility_ready: { zh: "可复现", en: "Reproducibility ready", detailZh: "协议、材料、测量与数据状态足以预注册复现实验。", detailEn: "Protocol, materials, measurements, and data status support a preregistered replication." },
  independently_reproduced: { zh: "已经复现", en: "Independently reproduced", detailZh: "独立运行在预定义条件与容差下经人工复核。", detailEn: "An independent run is human-reviewed against predefined conditions and tolerance." },
};

function deliveryCopy(locale: "zh" | "en", status: ImportedBundle["evidenceMaturityRegistryStatus"], claimCount: number, source: ImportedBundle["source"]) {
  if (status === "accepted") return source === "loopback"
    ? copy(locale, `交付链接审计已通过 · ${claimCount} 条已登记主张`, `Delivery link audit passed · ${claimCount} registered claim(s)`)
    : copy(locale, `导入包声明交付已通过 · ${claimCount} 条已登记主张`, `Imported bundle declares delivery passed · ${claimCount} registered claim(s)`);
  if (status === "rejected") return copy(locale, "登记表已拒绝交付", "Registry delivery rejected");
  return copy(locale, "未导入登记表", "Registry not imported");
}

function deliveryDetail(locale: "zh" | "en", status: ImportedBundle["evidenceMaturityRegistryStatus"], source: ImportedBundle["source"]) {
  if (status === "accepted") return source === "loopback"
    ? copy(locale, "本机服务已核验登记表、审计收据与当前 Source Map 链接；该台账仍不构成科学结论。", "The local service verified the registry, audit receipt, and current Source Map links; this ledger is still not a scientific conclusion.")
    : copy(locale, "导入包声明其交付校验已通过；浏览器不会重新执行 Source Map 链接审计。请从本机服务重新导出以取得当前核验结果；该台账不构成科学结论。", "The imported bundle declares that delivery validation passed; the browser does not rerun the Source Map link audit. Re-export from the local service for a current verification result; this ledger is not a scientific conclusion.");
  if (status === "rejected") return copy(locale, "登记表、审计收据或当前 Source Map 链接未通过交付校验；所有成熟度升级均已隐藏。", "The registry, audit receipt, or current Source Map links did not pass delivery validation; every maturity upgrade is hidden.");
  return copy(locale, "本任务未导入经绑定审计的登记表；不会从 EvidenceCard 或 Source Map 推断成熟度等级。", "This task has no registry with a bound audit; maturity is never inferred from EvidenceCards or Source Maps.");
}

export function EvidenceMaturityPanel(props: { bundle: ImportedBundle; locale: "zh" | "en" }) {
  const projection = createMemo(() => evidenceMaturityProjection(props.bundle));
  const registryStatus = () => props.bundle.evidenceMaturityRegistryStatus;
  return <section class="evidence-maturity-panel" aria-label={copy(props.locale, "证据成熟度登记", "Evidence maturity registry")}>
    <header><div><small>{copy(props.locale, "主张证明标准 / 只读", "CLAIM MATURITY / READ ONLY")}</small><h2>{copy(props.locale, "结论强度必须逐级登记", "Claim strength must be registered level by level")}</h2></div><span>{deliveryCopy(props.locale, registryStatus(), projection().registry?.claims.length ?? 0, props.bundle.source)}</span></header>
    <div class="evidence-maturity-levels" role="list"><For each={EVIDENCE_MATURITY_LEVELS}>{(level, index) => <article role="listitem" class={`maturity-${level}`}><small>{String(index() + 1).padStart(2, "0")}</small><strong>{copy(props.locale, levelCopy[level].zh, levelCopy[level].en)}</strong><span>{projection().counts[level]}</span><p>{copy(props.locale, levelCopy[level].detailZh, levelCopy[level].detailEn)}</p></article>}</For></div>
    <p class={`evidence-maturity-delivery state-${registryStatus()}`} role="status" aria-live="polite">{deliveryDetail(props.locale, registryStatus(), props.bundle.source)}</p>
    <Show when={projection().registry} fallback={<p class="evidence-maturity-empty">{registryStatus() === "rejected" ? copy(props.locale, "本次导入的登记表未通过字段、权威或复现门槛校验，故未显示任何成熟度升级。EvidenceCard、Source Map、材料事实和图谱节点不会被本界面自动升级。", "The imported registry did not pass field, authority, or reproduction-gate validation, so no maturity upgrade is shown. This UI never auto-promotes EvidenceCards, Source Maps, material facts, or graph nodes.") : copy(props.locale, "当前任务尚未导入证据成熟度登记表。EvidenceCard、Source Map、材料事实和图谱节点不会被本界面自动升级为任何成熟度等级。", "No evidence-maturity registry is imported for this task. This UI never auto-promotes EvidenceCards, Source Maps, material facts, or graph nodes to any maturity level.")}</p>}>
      {(registry) => <><p class="evidence-maturity-trust">{copy(props.locale, `登记表信任状态：${registry().trustStatus}。它是主张台账，不是科学结论。`, `Registry trust status: ${registry().trustStatus}. It is a claim ledger, not a scientific conclusion.`)}</p><ol class="evidence-maturity-claims"><For each={registry().claims.slice(0, 4)}>{(claim) => <li><small>{copy(props.locale, levelCopy[claim.maturityLevel].zh, levelCopy[claim.maturityLevel].en)}</small><strong>{claim.claimText}</strong><span>{copy(props.locale, `${claim.supportRecordCount} 条支撑记录 · ${claim.assessmentAuthority}`, `${claim.supportRecordCount} support record(s) · ${claim.assessmentAuthority}`)}</span><span>{copy(props.locale, `${claim.supportDocumentCount} 个文献版本 · ${claim.independenceGroupCount} 个独立性分组 · Source Map：${claim.sourceMapStatuses.join(" / ")}`, `${claim.supportDocumentCount} document version(s) · ${claim.independenceGroupCount} independence group(s) · Source Map: ${claim.sourceMapStatuses.join(" / ")}`)}</span><em>{claim.limitations[0] ?? copy(props.locale, "未提供限制说明", "No limitation statement provided")}</em></li>}</For></ol></>}
    </Show>
  </section>;
}
