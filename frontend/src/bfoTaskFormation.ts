import { FLEETS, label, type UiLocale } from "./fleetRegistry";

export interface BfoFormationStation {
  fleetId: string;
  fleetLabel: string;
  role: string;
  intake: string;
  artifact: string;
  acceptanceGate: string;
}

type FormationCopy = { fleetId: string; roleZh: string; roleEn: string; artifactZh: string; artifactEn: string };

const formations: Record<string, readonly FormationCopy[]> = {
  "bfo-phase-boundary": [
    { fleetId: "pioneer", roleZh: "冻结问题与可比边界", roleEn: "Freeze question and comparison boundary", artifactZh: "任务简报", artifactEn: "mission brief" },
    { fleetId: "observatory", roleZh: "检索、筛选并登记授权全文", roleEn: "Retrieve, screen, and register authorised full text", artifactZh: "候选清单 / Source Map 草稿", artifactEn: "candidate list / Source Map drafts" },
    { fleetId: "sentinel", roleZh: "核对条件、单位与定位", roleEn: "Verify conditions, units, and locators", artifactZh: "已接受 EvidenceCard", artifactEn: "accepted EvidenceCards" },
    { fleetId: "constellation", roleZh: "组织论文、来源与条件的可审查星图", roleEn: "Organise an auditable map of papers, sources, and conditions", artifactZh: "带来源文献子图", artifactEn: "provenance-linked literature subgraph" },
    { fleetId: "diagnostics", roleZh: "比较相边界差异与未报告条件", roleEn: "Compare phase-boundary differences and missing conditions", artifactZh: "条件冲突矩阵", artifactEn: "condition conflict matrix" },
    { fleetId: "horizon", roleZh: "提出需验证的边界缺口", roleEn: "Propose boundary gaps requiring validation", artifactZh: "Gap 候选", artifactEn: "Gap candidates" },
  ],
  "bfo-domain-coupling": [
    { fleetId: "pioneer", roleZh: "冻结对象、取向与问题范围", roleEn: "Freeze object, orientation, and question scope", artifactZh: "任务简报", artifactEn: "mission brief" },
    { fleetId: "observatory", roleZh: "收集畴与耦合的原始报告", roleEn: "Collect primary reports of domains and coupling", artifactZh: "候选清单 / 来源草稿", artifactEn: "candidate list / source drafts" },
    { fleetId: "sentinel", roleZh: "核对样品、场史与表征条件", roleEn: "Verify samples, field history, and characterisation conditions", artifactZh: "条件化 EvidenceCard", artifactEn: "conditioned EvidenceCards" },
    { fleetId: "constellation", roleZh: "组织可审查的关系投影", roleEn: "Organise auditable relation projections", artifactZh: "带来源关系工件", artifactEn: "provenance-linked relation artifacts" },
    { fleetId: "diagnostics", roleZh: "定位可比性冲突与缺失变量", roleEn: "Locate comparability conflicts and missing variables", artifactZh: "缺失与冲突登记", artifactEn: "missingness and conflict register" },
    { fleetId: "horizon", roleZh: "将可比性空洞收敛为验证候选", roleEn: "Turn comparability gaps into validation candidates", artifactZh: "Gap 候选 / 验证路线", artifactEn: "Gap candidates / validation routes" },
  ],
  "bfo-defect-method": [
    { fleetId: "pioneer", roleZh: "冻结协议比较边界", roleEn: "Freeze protocol-comparison boundary", artifactZh: "任务简报", artifactEn: "mission brief" },
    { fleetId: "observatory", roleZh: "收集制备与测试协议报告", roleEn: "Collect preparation and test-protocol reports", artifactZh: "候选清单 / 来源草稿", artifactEn: "candidate list / source drafts" },
    { fleetId: "sentinel", roleZh: "核对缺陷、偏压与测试定位", roleEn: "Verify defect, bias, and test locators", artifactZh: "条件化 EvidenceCard", artifactEn: "conditioned EvidenceCards" },
    { fleetId: "constellation", roleZh: "组织协议与来源的可审查关系", roleEn: "Organise auditable relations between protocols and sources", artifactZh: "协议—来源关系投影", artifactEn: "protocol-to-source relation projection" },
    { fleetId: "diagnostics", roleZh: "拆分协议差异与未知条件", roleEn: "Separate protocol differences and unknown conditions", artifactZh: "条件冲突矩阵", artifactEn: "condition conflict matrix" },
    { fleetId: "horizon", roleZh: "提出受反例约束的验证路线", roleEn: "Propose validation routes bounded by counterevidence", artifactZh: "Gap 候选 / 验证路线", artifactEn: "Gap candidates / validation routes" },
  ],
};

type ContractCopy = { intakeZh: string; intakeEn: string; gateZh: string; gateEn: string };
const fleetContract: Record<string, ContractCopy> = {
  pioneer: { intakeZh: "可编辑问题与范围", intakeEn: "editable question and scope", gateZh: "人工确认任务边界", gateEn: "human confirmation of mission boundary" },
  observatory: { intakeZh: "已确认任务简报", intakeEn: "confirmed mission brief", gateZh: "批准计划与允许的元数据来源", gateEn: "approved plan and permitted metadata sources" },
  sentinel: { intakeZh: "候选与本机来源定位", intakeEn: "candidates and local source locations", gateZh: "人工来源／数据审核", gateEn: "human source/data review" },
  constellation: { intakeZh: "已审核事实与来源映射", intakeEn: "reviewed facts and source maps", gateZh: "人工核对跨源标识", gateEn: "human review of cross-source identities" },
  diagnostics: { intakeZh: "相反证据与条件字段", intakeEn: "opposing evidence and condition fields", gateZh: "跨文献对照与缺失字段已登记", gateEn: "cross-paper contrast and missing fields recorded" },
  horizon: { intakeZh: "受控比较与反例边界", intakeEn: "controlled comparison and counterevidence boundary", gateZh: "人工复核；候选不等于结论", gateEn: "human review; candidates are not conclusions" },
};

/** Planned roles only.  No formation item is an execution request. */
export function bfoTaskFormation(taskId: string, locale: UiLocale): BfoFormationStation[] {
  return (formations[taskId] ?? []).flatMap((item) => {
    const fleet = FLEETS.find((candidate) => candidate.id === item.fleetId);
    const contract = fleetContract[item.fleetId];
    if (!fleet || !contract) return [];
    return [{ fleetId: fleet.id, fleetLabel: label(fleet, locale), role: locale === "zh" ? item.roleZh : item.roleEn, intake: locale === "zh" ? contract.intakeZh : contract.intakeEn, artifact: locale === "zh" ? item.artifactZh : item.artifactEn, acceptanceGate: locale === "zh" ? contract.gateZh : contract.gateEn }];
  });
}
