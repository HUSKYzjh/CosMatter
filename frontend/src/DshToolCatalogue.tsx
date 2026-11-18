import { For, Show, createMemo, createSignal } from "solid-js";
import { packages } from "../../plugins/dsh-plugin-group.json";
import { continuationStageLabel } from "./continuationStage";
import { DSH_STAGE_NOTES, DSH_STAGE_TOOLS } from "./dshStageTools";
import { dshCatalogueCommand, type DshEvidenceTarget } from "./dshLocalCommands";
import type { UiLocale } from "./fleetRegistry";
import type { DshProfileHealth, DshProfileStatus, HarnessPluginDescriptor, WorkflowStageName } from "./localApi";
import { ActionButton, StatusBadge } from "./uiPrimitives";

type Access = "read" | "local" | "review" | "external";
type ToolCopy = {
  label: readonly [string, string];
  access: Access;
  note?: readonly [string, string];
  descriptor?: string;
};

const TOOL_COPY: Readonly<Partial<Record<string, ToolCopy>>> = {
  cosmatter_mission_create: { label: ["建立本机任务", "Create a local mission"], access: "local" },
  cosmatter_recent_runs: { label: ["查找最近的本机任务", "Find recent local runs"], access: "read" },
  cosmatter_workflow_status: { label: ["读取任务进度", "Read workflow status"], access: "read" },
  cosmatter_stage_contract: { label: ["读取阶段门禁", "Read stage requirements"], access: "read" },
  cosmatter_operational_telemetry: { label: ["读取派发回执摘要", "Read dispatch receipt summary"], access: "read" },
  cosmatter_workflow_dag: { label: ["读取阶段依赖", "Read stage dependencies"], access: "read" },
  cosmatter_artifact_manifest: { label: ["读取获准工件目录", "Read approved artifact list"], access: "read" },
  cosmatter_plugin_catalogue: { label: ["读取插件契约目录", "Read plugin contracts"], access: "read" },
  cosmatter_plugin_authorization_plan: { label: ["检查授权条件", "Check authorization requirements"], access: "local", note: ["在任务日志登记授权判定，供操作者核对。", "Records an authorization assessment in the mission log."] },
  cosmatter_research_plan_draft: { label: ["生成检索计划草案", "Draft a retrieval plan"], access: "external", descriptor: "literature.plan_draft", note: ["使用 DeepSeek 生成待审核草案。", "Uses DeepSeek to draft a plan for review."] },
  cosmatter_research_plan_approve: { label: ["登记已审核的检索计划", "Record a reviewed retrieval plan"], access: "review" },
  cosmatter_research_query_execute: { label: ["执行书目查询", "Run a bibliographic query"], access: "external", descriptor: "literature.metadata_retrieval", note: ["执行已批准计划中的一条查询，返回待筛选候选。", "Runs one approved query and returns candidates for screening."] },
  cosmatter_candidate_screening_template: { label: ["读取候选筛选清单", "Read the candidate screening checklist"], access: "read" },
  cosmatter_candidate_screening_record: { label: ["登记人工筛选结果", "Record human screening decisions"], access: "review" },
  cosmatter_mineru_source_submit: { label: ["提交授权全文至 MinerU", "Submit an authorized source to MinerU"], access: "external", descriptor: "document.mineru_private_parse", note: ["候选需通过人工筛选，并确认内容访问权限。", "The candidate needs human screening and confirmed content access."] },
  cosmatter_mineru_task_poll: { label: ["查询 MinerU 任务状态", "Check MinerU task status"], access: "external", descriptor: "document.mineru_private_parse", note: ["读取既有任务状态，需要与提交时相同的授权。", "Reads an existing task’s status and requires the same authorizations as submission."] },
  cosmatter_graph_query: { label: ["读取已接受证据图", "Read the accepted-evidence graph"], access: "read" },
  cosmatter_accepted_evidence_search: { label: ["检索已接受证据的索引", "Search the accepted-evidence index"], access: "read" },
  cosmatter_graph_plan: { label: ["登记图谱检查计划", "Record a graph inspection plan"], access: "local", note: ["记录待人工检查的节点与理由。", "Records nodes and rationale for human inspection."] },
  cosmatter_graph_review_request: { label: ["提交图谱人工复核请求", "Request human graph review"], access: "local", note: ["提交待复核请求，由人工决定后续操作。", "Queues a review request for a human decision."] },
};

const TOOLS = packages.flatMap((bundle) => bundle.tools.map((name) => ({
  name,
  bundle: bundle.package,
  copy: TOOL_COPY[name],
})));

const ACCESS_LABELS: Record<Access, readonly [string, string]> = {
  read: ["本机读取", "Local read"],
  local: ["本机登记", "Local record"],
  review: ["人工审核后登记", "Human review required"],
  external: ["需逐任务授权", "Mission authorization required"],
};
const ACCESS_TYPES = Object.keys(ACCESS_LABELS) as Access[];

export interface DshToolCatalogueProps {
  locale: UiLocale;
  plugins: readonly HarnessPluginDescriptor[];
  profile: DshProfileStatus | null;
  profileHealth: DshProfileHealth;
  currentStage?: WorkflowStageName | null;
  runId?: string | null;
  evidence?: DshEvidenceTarget | null;
}

export function DshToolCatalogue(props: DshToolCatalogueProps) {
  return <details class="harness-disclosure dsh-tool-catalogue" aria-live="off">
    <summary><span>{props.locale === "zh" ? "查找 DSH 工具" : "Find DSH tools"}</span><strong>{TOOLS.length}</strong></summary>
    <DshToolCatalogueContent {...props} />
  </details>;
}

export function DshToolCatalogueContent(props: DshToolCatalogueProps & { initialStage?: WorkflowStageName | null }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [query, setQuery] = createSignal("");
  const [filter, setFilter] = createSignal<Access | "all">("all");
  const [stageFilter, setStageFilter] = createSignal<WorkflowStageName | "all">(props.initialStage ?? "all");
  const [clipboard, setClipboard] = createSignal<{ name: string; kind: "name" | "command"; value: string; copied: boolean } | null>(null);
  const pluginById = createMemo(() => new Map(props.plugins.map((plugin) => [plugin.plugin_id, plugin])));
  const registry = createMemo(() => {
    const check = props.profile?.tool_registry_check;
    return props.profileHealth === "ready" && check?.matches_local_files
      ? { bundles: new Set(check.bundles), tools: new Set(check.registered_tools) }
      : null;
  });
  const visibleTools = createMemo(() => {
    const search = query().trim().toLowerCase();
    const stage = stageFilter();
    return TOOLS.filter(({ name, bundle, copy }) => {
      if (stage !== "all" && !DSH_STAGE_TOOLS[stage].includes(name)) return false;
      if (filter() !== "all" && filter() !== copy?.access) return false;
      return [name, bundle, ...(copy?.label ?? []), copy?.descriptor].some((term) => term?.toLowerCase().includes(search));
    });
  });
  const stageNote = () => {
    const stage = stageFilter();
    return stage === "all" ? undefined : DSH_STAGE_NOTES[stage];
  };
  const clearFilters = () => { setQuery(""); setFilter("all"); setStageFilter("all"); };
  const bundleState = (bundle: string) => {
    if (props.profileHealth !== "ready" || !props.profile || props.profile.installation_state === "unavailable") {
      return x("本机安装状态未确认", "Local installation unconfirmed");
    }
    const status = props.profile.packages.find((item) => item.package === bundle);
    const check = props.profile.composition_check;
    if (status?.install_status !== "verified") return x("本机安装尚未验证", "Local installation unverified");
    if (!check) return x("安装文件已验证，待核验组合", "Files verified; composition unchecked");
    if (!check.matches_local_files) return x("本机文件已变化，待复核", "Local files changed; recheck needed");
    return check.bundles.includes(bundle)
      ? x("上次核验已组合，启动待确认", "Composed on last check; startup unconfirmed")
      : x("上次核验未组合此包", "Bundle absent from last composition check");
  };
  const copyTool = async (name: string, kind: "name" | "command", value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setClipboard({ name, kind, value, copied: true });
    } catch {
      setClipboard({ name, kind, value, copied: false });
    }
  };

  return <div class="dsh-tool-body">
      <p>{x("按阶段、工具名、插件包或授权类型查找。目录仅供查阅，运行前仍须核对阶段要求。", "Find tools by stage, name, bundle, or authorization. Check the stage requirements before running a tool.")}</p>
      <Show when={props.currentStage}>{(stage) => <div class="dsh-current-stage">
        <p><span>{x("本机已核验阶段", "Locally verified stage")}</span><strong>{continuationStageLabel(stage(), props.locale)}</strong></p>
        <ActionButton size="sm" aria-pressed={stageFilter() === stage()} onClick={() => setStageFilter(stageFilter() === stage() ? "all" : stage())}>{x("只看本阶段", "Filter to this stage")}</ActionButton>
      </div>}</Show>
      <div class="dsh-tool-filters">
        <label><span>{x("搜索工具或插件包", "Search tools or bundles")}</span>
          <input type="search" value={query()} maxLength={160} onInput={(event) => setQuery(event.currentTarget.value)} />
        </label>
        <label><span>{x("研究阶段", "Research stage")}</span>
          <select value={stageFilter()} onChange={(event) => setStageFilter(event.currentTarget.value as WorkflowStageName | "all")}>
            <option value="all">{x("全部阶段", "All stages")}</option>
            <For each={Object.keys(DSH_STAGE_TOOLS) as WorkflowStageName[]}>{(stage) => <option value={stage}>{continuationStageLabel(stage, props.locale)}</option>}</For>
          </select>
        </label>
        <label><span>{x("授权类型", "Authorization type")}</span>
          <select value={filter()} onChange={(event) => setFilter(event.currentTarget.value as Access | "all")}>
            <option value="all">{x("全部类型", "All types")}</option>
            <For each={ACCESS_TYPES}>{(access) => <option value={access}>{x(...ACCESS_LABELS[access])}</option>}</For>
          </select>
        </label>
      </div>
      <Show when={stageNote()}>{(note) => <p class="dsh-stage-note">{x(...note())}</p>}</Show>
      <p class="dsh-tool-count" role="status">{x(`显示 ${visibleTools().length}/${TOOLS.length} 个工具`, `Showing ${visibleTools().length} of ${TOOLS.length} tools`)}</p>
      <Show when={visibleTools().length > 0} fallback={<div class="dsh-tool-empty">
        <p>{x("没有符合条件的工具。", "No tools match these filters.")}</p>
        <ActionButton size="sm" onClick={clearFilters}>{x("清除筛选", "Clear filters")}</ActionButton>
      </div>}>
        <ul class="dsh-tool-list">
          <For each={visibleTools()}>{(tool) => {
            const descriptor = () => tool.copy?.descriptor ? pluginById().get(tool.copy.descriptor) : undefined;
            const label = () => tool.copy ? x(...tool.copy.label) : tool.name;
            const command = createMemo(() => dshCatalogueCommand(tool.name, props.runId, props.evidence));
            const toolStatus = () => {
              const status = clipboard();
              return status?.name === tool.name && (status.kind === "name" || status.value === command()) ? status : null;
            };
            const registered = () => registry()?.bundles.has(tool.bundle) ? registry()?.tools.has(tool.name) : undefined;
            return <li>
              <details class="harness-disclosure dsh-tool-item">
                <summary>
                  <span>
                    <strong>{label()}</strong><code>{tool.name.split("_").map((segment, index, segments) =>
                      index === segments.length - 1 ? segment : <>{segment}_<wbr /></>)}</code>
                    <Show when={registered() !== undefined}><small classList={{ "dsh-tool-registration": true, ready: registered() }}>
                      {registered() ? x("隔离核验已注册", "Registered in isolated check") : x("隔离核验未注册", "Missing from isolated registry")}
                    </small></Show>
                  </span>
                  <StatusBadge tone={tool.copy?.access === "external" || tool.copy?.access === "review" ? "attention" : "neutral"}>
                    {tool.copy ? x(...ACCESS_LABELS[tool.copy.access]) : x("查阅包说明", "See bundle documentation")}
                  </StatusBadge>
                </summary>
                <div class="dsh-tool-detail">
                  <code>{tool.bundle}</code>
                  <p>{bundleState(tool.bundle)}</p>
                  <Show when={tool.copy?.note}>{(note) => <p>{x(...note())}</p>}</Show>
                  <Show when={descriptor()?.required_authorizations.length}>
                    <div class="dsh-tool-consents"><strong>{x("所需授权字段", "Required authorization fields")}</strong>
                      <For each={descriptor()?.required_authorizations}>{(authorization) => <code>{authorization}</code>}</For>
                    </div>
                  </Show>
                  <Show when={command()}>{(line) => <div class="dsh-tool-terminal">
                    <p>{x("在 CosMatter 的 PowerShell 终端运行命令。", "Run this command in the CosMatter PowerShell environment.")}</p>
                    <code>{line()}</code>
                  </div>}</Show>
                  <div class="dsh-tool-actions">
                    <Show when={command()}>{(line) =>
                      <ActionButton size="sm" onClick={() => void copyTool(tool.name, "command", line())}>{x("复制 DSH 命令", "Copy DSH command")}</ActionButton>
                    }</Show>
                    <ActionButton size="sm" variant={command() ? "quiet" : "secondary"} onClick={() => void copyTool(tool.name, "name", tool.name)}>{x("复制工具名", "Copy tool name")}</ActionButton>
                  </div>
                  <Show when={toolStatus()}>{(status) => <>
                    <p role="status">{status().kind === "command"
                      ? status().copied ? x("DSH 命令已复制。", "DSH command copied.")
                        : x("剪贴板不可用，可选中上方命令复制。", "Clipboard unavailable. Select the command above to copy it.")
                      : status().copied ? x("工具名已复制。", "Tool name copied.")
                        : x("剪贴板不可用，请选中下方工具名手动复制。", "Clipboard unavailable. Select and copy the tool name below.")}</p>
                    <Show when={status().kind === "name" && !status().copied}><code class="dsh-tool-manual-copy">{tool.name}</code></Show>
                  </>}</Show>
                </div>
              </details>
            </li>;
          }}</For>
        </ul>
      </Show>
    </div>;
}
