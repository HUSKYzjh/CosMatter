import { For, Show, batch, createEffect, createMemo, createSignal, createUniqueId, on } from "solid-js";
import { packages } from "../../plugins/dsh-plugin-group.json";
import { continuationStageLabel } from "./continuationStage";
import { DSH_STAGE_NOTES, DSH_STAGE_TOOLS } from "./dshStageTools";
import { BUNDLE_REPAIR_COMMAND, dshCatalogueCommand, dshProfileCheckCommand, localWorkbenchLocation, type DshEvidenceTarget } from "./dshLocalCommands";
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

const normalizeSearch = (text: string) => text.normalize("NFKC").toLowerCase();
const TOOLS = packages.flatMap((bundle) => bundle.tools.map((name) => {
  const copy = TOOL_COPY[name];
  const searchText = normalizeSearch([name, bundle.package, ...(copy?.label ?? []), copy?.descriptor].join(" "));
  return { name, bundle: bundle.package, copy, searchText };
}));

const ACCESS_LABELS: Record<Access, readonly [string, string]> = {
  read: ["本机读取", "Local read"],
  local: ["本机登记", "Local record"],
  review: ["人工审核后登记", "Human review required"],
  external: ["需逐任务授权", "Mission authorization required"],
};
const ACCESS_TYPES = Object.keys(ACCESS_LABELS) as Access[];
type CommandKind = "repair" | "verify" | "read";
const COMMAND_COPY: Record<CommandKind, Record<"hint" | "button" | "copied", readonly [string, string]>> = {
  repair: {
    hint: ["在 CosMatter 仓库根目录运行补齐命令，再刷新本卡。", "Run the repair from the CosMatter repository root, then refresh this card."],
    button: ["复制补齐命令", "Copy repair command"], copied: ["补齐命令已复制。", "Repair command copied."],
  },
  verify: {
    hint: ["核对此插件的编译版本，更新后在终端重新核验，再刷新本卡。", "Check the installed bundle version. After updating, run the terminal check and refresh this card."],
    button: ["复制核验命令", "Copy check command"], copied: ["核验命令已复制。", "Check command copied."],
  },
  read: {
    hint: ["在 CosMatter 的 PowerShell 终端运行命令。", "Run this command in the CosMatter PowerShell environment."],
    button: ["复制 DSH 命令", "Copy DSH command"], copied: ["DSH 命令已复制。", "DSH command copied."],
  },
};
const ACCESS_FILTER_EN: Partial<Record<Access, string>> = { review: "Human review", external: "Mission consent" };
const STAGE_FILTER_EN: Record<WorkflowStageName, string> = {
  intake: "Mission setup",
  plan: "Plan review",
  retrieval: "Retrieval",
  screening: "Screening",
  parse: "Source parsing",
  extraction: "Extraction",
  gap: "Gap review",
  report: "Report",
  evaluation: "Evaluation",
};

export interface DshToolCatalogueProps {
  locale: UiLocale;
  plugins: readonly HarnessPluginDescriptor[];
  profile: DshProfileStatus | null;
  profileHealth: DshProfileHealth;
  onRefreshProfile?: () => void;
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

export function DshToolCatalogueContent(props: DshToolCatalogueProps & { initialStage?: WorkflowStageName | null; scrollResults?: boolean }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [query, setQuery] = createSignal("");
  const [filter, setFilter] = createSignal<Access | "all">("all");
  const [stageFilter, setStageFilter] = createSignal<WorkflowStageName | "all">(props.initialStage ?? "all");
  const [clipboard, setClipboard] = createSignal<{ name: string; kind: "name" | "command"; value: string; copied: boolean } | null>(null);
  let searchInput!: HTMLInputElement;
  let results!: HTMLDivElement;
  const searchId = createUniqueId();
  const location = localWorkbenchLocation();
  const checkCommand = location ? dshProfileCheckCommand(Number(location.port || "80")) : null;
  if (props.scrollResults) {
    createEffect(on([query, filter, stageFilter], () => { results.scrollTop = 0; }, { defer: true }));
  }
  const pluginById = createMemo(() => new Map(props.plugins.map((plugin) => [plugin.plugin_id, plugin])));
  const registry = createMemo(() => {
    const check = props.profile?.tool_registry_check;
    return (props.profileHealth === "ready" || props.profileHealth === "loading") && check?.matches_local_files
      ? { bundles: new Set(check.bundles), tools: new Set(check.registered_tools) }
      : null;
  });
  const matchingTools = createMemo(() => {
    const words = normalizeSearch(query()).trim().split(/\s+/).filter(Boolean);
    return TOOLS.filter(({ searchText }) => words.every((word) => searchText.includes(word)));
  });
  const visibleTools = createMemo(() => {
    const stage = stageFilter();
    return matchingTools().filter(({ name, copy }) => (stage === "all" || DSH_STAGE_TOOLS[stage].includes(name))
      && (filter() === "all" || filter() === copy?.access));
  });
  const hasHiddenMatches = () => Boolean(query().trim()) && matchingTools().length > visibleTools().length;
  const singleMatch = () => Boolean(query().trim()) && visibleTools().length === 1;
  const openMatch = (event: KeyboardEvent) => {
    if (event.key !== "Enter" || event.isComposing || event.keyCode === 229 || !singleMatch()) return;
    const item = results.querySelector<HTMLDetailsElement>(".dsh-tool-item");
    if (!item) return;
    event.preventDefault();
    item.open = true;
    item.querySelector("summary")?.focus();
  };
  const stageNote = () => {
    const stage = stageFilter();
    return stage === "all" ? undefined : DSH_STAGE_NOTES[stage];
  };
  const clearFilters = () => {
    batch(() => { setFilter("all"); setStageFilter("all"); });
    searchInput.focus();
  };
  const installStatus = (bundle: string) => props.profile && props.profile.installation_state !== "unavailable"
    ? props.profile.packages.find((item) => item.package === bundle)?.install_status : undefined;
  const checkOutdated = () => props.profile?.composition_check?.matches_local_files === false
    || props.profile?.tool_registry_check?.matches_local_files === false;
  const bundleState = (bundle: string) => {
    if (props.profileHealth === "loading") return x("正在刷新插件状态…", "Refreshing bundle status…");
    const status = installStatus(bundle);
    if (!status) {
      return x("本机安装状态未确认", "Local installation unconfirmed");
    }
    if (status === "missing_bundle") return x("本机缺少插件文件", "Bundle files missing");
    if (status === "invalid_bundle") return x("本机插件文件异常", "Invalid bundle files");
    if (status === "not_declared") return x("tui 尚未声明此插件", "Bundle absent from TUI dependencies");
    const check = props.profile?.composition_check;
    if (check?.matches_local_files && !check.bundles.includes(bundle)) return x("此插件未进入 tui 配置组合", "Bundle missing from TUI composition");
    if (checkOutdated()) return x("本机文件已变化，待复核", "Local files changed; recheck needed");
    if (!check) return x("安装文件已验证，待核验组合", "Files verified; composition unchecked");
    return x("安装文件与 tui 配置组合已核验", "Files and TUI composition verified");
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
    <div class="dsh-tool-controls">
      <Show when={props.currentStage}>{(stage) => <div class="dsh-current-stage">
        <p><span>{x("本机已核验阶段", "Locally verified stage")}</span><strong>{continuationStageLabel(stage(), props.locale)}</strong></p>
        <ActionButton size="sm" aria-pressed={stageFilter() === stage()} onClick={() => setStageFilter(stageFilter() === stage() ? "all" : stage())}>{x("只看本阶段", "Filter to this stage")}</ActionButton>
      </div>}</Show>
      <div class="dsh-tool-filters">
        <div class="dsh-tool-search">
          <label for={searchId}>{x("搜索工具或插件包", "Search tools or bundles")}</label>
          <div class="dsh-tool-search-field">
            <input ref={searchInput} id={searchId} type="search" value={query()} maxLength={160} onKeyDown={openMatch}
              aria-describedby={singleMatch() ? `${searchId}-hint` : undefined} onInput={(event) => setQuery(event.currentTarget.value)} />
            <Show when={query()}><ActionButton size="icon" variant="quiet" aria-label={x("清空关键词", "Clear search text")}
              onClick={() => { setQuery(""); searchInput.focus(); }}><span aria-hidden="true">×</span></ActionButton></Show>
          </div>
        </div>
        <label><span>{x("研究阶段", "Research stage")}</span>
          <select value={stageFilter()} onChange={(event) => setStageFilter(event.currentTarget.value as WorkflowStageName | "all")}>
            <option value="all">{x("全部阶段", "All stages")}</option>
            <For each={Object.keys(DSH_STAGE_TOOLS) as WorkflowStageName[]}>{(stage) =>
              <option value={stage}>{x(continuationStageLabel(stage, "zh"), STAGE_FILTER_EN[stage])}</option>
            }</For>
          </select>
        </label>
        <label><span>{x("授权类型", "Authorization type")}</span>
          <select value={filter()} onChange={(event) => setFilter(event.currentTarget.value as Access | "all")}>
            <option value="all">{x("全部类型", "All types")}</option>
            <For each={ACCESS_TYPES}>{(access) =>
              <option value={access}>{x(ACCESS_LABELS[access][0], ACCESS_FILTER_EN[access] ?? ACCESS_LABELS[access][1])}</option>
            }</For>
          </select>
        </label>
      </div>
      <div class="dsh-tool-filter-status">
        <p class="dsh-tool-count" role="status">{x(`显示 ${visibleTools().length}/${TOOLS.length} 个工具`, `Showing ${visibleTools().length} of ${TOOLS.length} tools`)}</p>
        <Show when={stageFilter() !== "all" || filter() !== "all"}>
          <ActionButton size="sm" variant={hasHiddenMatches() ? "secondary" : "quiet"} onClick={clearFilters}>{hasHiddenMatches()
            ? x(`查看全部 ${matchingTools().length} 项匹配`, matchingTools().length === 1 ? "Show 1 match across all tools" : `Show all ${matchingTools().length} matches`)
            : x("清除筛选", "Clear filters")}</ActionButton>
        </Show>
      </div>
    </div>
    <div ref={results} class="dsh-tool-results" role={props.scrollResults ? "region" : undefined}
      aria-label={props.scrollResults ? x("工具结果", "Tool results") : undefined} tabIndex={props.scrollResults ? 0 : undefined}>
      <Show when={singleMatch()}><p id={`${searchId}-hint`}>{x("在搜索框按 Enter 展开此工具。", "Press Enter in the search field to open this tool.")}</p></Show>
      <Show when={stageNote()}>{(note) => <p class="dsh-stage-note">{x(...note())}</p>}</Show>
      <Show when={visibleTools().length > 0} fallback={<div class="dsh-tool-empty">
        <p>{hasHiddenMatches() ? x("匹配的工具在当前筛选范围之外。", "Matching tools are outside the active filters.")
          : x("没有符合条件的工具。", "No tools match these filters.")}</p>
      </div>}>
        <ul class="dsh-tool-list">
          <For each={visibleTools()}>{(tool) => {
            let summary!: HTMLElement;
            const descriptor = () => tool.copy?.descriptor ? pluginById().get(tool.copy.descriptor) : undefined;
            const label = () => tool.copy ? x(...tool.copy.label) : tool.name;
            const registered = () => registry()?.bundles.has(tool.bundle) ? registry()?.tools.has(tool.name) : undefined;
            const needsRepair = () => {
              const status = installStatus(tool.bundle);
              if (!status) return false;
              const composition = props.profile?.composition_check;
              return status !== "verified" || Boolean(composition?.matches_local_files && !composition.bundles.includes(tool.bundle));
            };
            const commandKind = (): CommandKind => {
              if (checkCommand && needsRepair()) return "repair";
              if (checkCommand && (registered() === false || checkOutdated())) return "verify";
              return "read";
            };
            const commandCopy = () => COMMAND_COPY[commandKind()];
            const command = createMemo(() => {
              if (commandKind() === "repair") return BUNDLE_REPAIR_COMMAND;
              if (commandKind() === "verify") return checkCommand;
              return dshCatalogueCommand(tool.name, props.runId, props.evidence);
            });
            const toolStatus = () => {
              const status = clipboard();
              return status?.name === tool.name && (status.kind === "name" || status.value === command()) ? status : null;
            };
            return <li>
              <details class="harness-disclosure dsh-tool-item">
                <summary ref={summary}>
                  <span>
                    <strong>{label()}</strong><code>{tool.name.split("_").map((segment, index, segments) =>
                      index === segments.length - 1 ? segment : <>{segment}_<wbr /></>)}</code>
                    <Show when={needsRepair()}><small class="dsh-tool-registration">{bundleState(tool.bundle)}</small></Show>
                    <Show when={!needsRepair() && registered() !== undefined}><small classList={{ "dsh-tool-registration": true, ready: registered() }}>
                      {registered() ? x("隔离核验已注册", "Registered in isolated check") : x("隔离核验未注册", "Missing from isolated registry")}
                    </small></Show>
                  </span>
                  <StatusBadge tone={tool.copy?.access === "external" || tool.copy?.access === "review" ? "attention" : "neutral"}>
                    {tool.copy ? x(...ACCESS_LABELS[tool.copy.access]) : x("查阅包说明", "See bundle documentation")}
                  </StatusBadge>
                </summary>
                <div class="dsh-tool-detail">
                  <code>{tool.bundle}</code>
                  <Show when={!needsRepair()}><p>{bundleState(tool.bundle)}</p></Show>
                  <Show when={tool.copy?.note}>{(note) => <p>{x(...note())}</p>}</Show>
                  <Show when={descriptor()?.required_authorizations.length}>
                    <div class="dsh-tool-consents"><strong>{x("所需授权字段", "Required authorization fields")}</strong>
                      <For each={descriptor()?.required_authorizations}>{(authorization) => <code>{authorization}</code>}</For>
                    </div>
                  </Show>
                  <Show when={command()}>{(line) => <div class="dsh-tool-terminal">
                    <p>{commandKind() === "verify" && checkOutdated()
                      ? x("在终端重新核验当前插件文件和注册状态，再刷新本卡。", "Run the check against the current bundle files and tool registry, then refresh this card.")
                      : x(...commandCopy().hint)}</p>
                    <code>{line()}</code>
                  </div>}</Show>
                  <div class="dsh-tool-actions">
                    <Show when={command()}>{(line) =>
                      <ActionButton size="sm" onClick={() => void copyTool(tool.name, "command", line())}>{x(...commandCopy().button)}</ActionButton>
                    }</Show>
                    <Show when={props.onRefreshProfile && (commandKind() !== "read" || props.profileHealth === "unavailable" || props.profile?.installation_state === "unavailable")}>
                      <ActionButton size="sm" busy={props.profileHealth === "loading"} busyLabel={x("正在读取…", "Reading…")}
                        onClick={() => { summary.focus(); props.onRefreshProfile?.(); }}>{x("刷新插件状态", "Refresh bundle status")}</ActionButton>
                    </Show>
                    <ActionButton size="sm" variant={command() ? "quiet" : "secondary"} onClick={() => void copyTool(tool.name, "name", tool.name)}>{x("复制工具名", "Copy tool name")}</ActionButton>
                  </div>
                  <Show when={toolStatus()}>{(status) => <>
                    <p role="status">{status().kind === "command"
                      ? status().copied ? x(...commandCopy().copied)
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
    </div>
  </div>;
}
