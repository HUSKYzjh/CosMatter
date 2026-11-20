import { DshCommandText } from "./DshCommandText";
import { formatDshCommand } from "./dshTerminalCommand";
import { canRepairBundleRegistration } from "./dshReadProfile";
import { For, Show, batch, createEffect, createMemo, createSignal, createUniqueId, on, onMount } from "solid-js";
import { packages } from "../../plugins/dsh-plugin-group.json";
import { continuationStageLabel } from "./continuationStage";
import { DSH_STAGE_NOTES, DSH_STAGE_TOOLS } from "./dshStageTools";
import { BUNDLE_REPAIR_COMMAND, dshCatalogueCommand, dshProfileCheckCommand, localWorkbenchLocation, updatedWorkbenchCommand, type DshEvidenceTarget } from "./dshLocalCommands";
import type { UiLocale } from "./fleetRegistry";
import type { DshProfileHealth, DshProfileStatus, HarnessPluginDescriptor, WorkflowStageName } from "./localApi";
import { ActionButton, StatusBadge } from "./uiPrimitives";
import { createDshClipboard, DshManualCopy } from "./DshManualCopy";

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

const ACCESS_LABELS: Record<Access, readonly [string, string]> = {
  read: ["本机读取", "Local read"],
  local: ["本机登记", "Local record"],
  review: ["人工审核后登记", "Human review required"],
  external: ["需逐任务授权", "Mission authorization required"],
};
const ACCESS_FILTER_EN: Partial<Record<Access, string>> = { review: "Human review", external: "Mission consent" };
const ACCESS_TYPES = Object.keys(ACCESS_LABELS) as Access[];
const normalizeSearch = (text: string) => text.normalize("NFKC").toLowerCase();
const TOOLS = packages.flatMap((bundle) => bundle.tools.map((name) => {
  const copy = TOOL_COPY[name];
  const terms = copy ? [
    ...copy.label, ...(copy.note ?? []), copy.descriptor,
    ...ACCESS_LABELS[copy.access], ACCESS_FILTER_EN[copy.access],
  ] : [];
  const searchText = normalizeSearch([name, bundle.package, ...terms].join(" "));
  return { name, bundle: bundle.package, copy, searchText };
}));

type CommandKind = "repair" | "verify" | "read" | "update";
const COMMAND_COPY: Record<CommandKind, Record<"hint" | "button" | "copied", readonly [string, string]>> = {
  update: {
    hint: ["此工作台缺少 DSH 近期任务链接接口。在已更新的 CosMatter 环境中新开终端运行命令，再打开终端打印的地址。", "This workbench lacks the DSH recent-run links endpoint. Run this in a new terminal in your updated CosMatter environment, then open the printed URL."],
    button: ["复制新版工作台命令", "Copy workbench command"], copied: ["工作台命令已复制。", "Workbench command copied."],
  },
  repair: {
    hint: ["在所选终端运行补齐命令，再刷新本卡。", "Run the repair in the selected terminal, then refresh this card."],
    button: ["复制补齐命令", "Copy repair command"], copied: ["补齐命令已复制。", "Repair command copied."],
  },
  verify: {
    hint: ["在终端核验当前插件组合和此端口，再刷新插件状态。", "Check the current bundle composition and this port in the terminal, then refresh the bundle status."],
    button: ["复制核验命令", "Copy check command"], copied: ["核验命令已复制。", "Check command copied."],
  },
  read: {
    hint: ["在所选的 CosMatter 终端环境中运行命令。", "Run this command in the selected CosMatter terminal environment."],
    button: ["复制 DSH 命令", "Copy DSH command"], copied: ["DSH 命令已复制。", "DSH command copied."],
  },
};
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

export function DshToolCatalogueContent(props: DshToolCatalogueProps & {
  initialStage?: WorkflowStageName | null;
  scrollResults?: boolean;
  onLookupReady?: (openTool: (name: string) => void) => void;
}) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const [query, setQuery] = createSignal("");
  const [filter, setFilter] = createSignal<Access | "all">("all");
  const [stageFilter, setStageFilter] = createSignal<WorkflowStageName | "all">(props.initialStage ?? "all");
  const clipboard = createDshClipboard<{ name: string; kind: "name" | "command" | "check" }>();
  let searchInput!: HTMLInputElement;
  let results!: HTMLDivElement;
  const searchId = createUniqueId();
  const location = localWorkbenchLocation();
  const checkCommand = location ? dshProfileCheckCommand(Number(location.port || "80")) : null;
  const formattedCheckCommand = () => checkCommand ? formatDshCommand(checkCommand) : null;
  if (props.scrollResults) {
    createEffect(on([query, filter, stageFilter], () => { results.scrollTop = 0; }, { defer: true }));
  }
  const pluginById = createMemo(() => new Map(props.plugins.map((plugin) => [plugin.plugin_id, plugin])));
  const authorizationFields = (copy?: ToolCopy) => copy?.descriptor
    ? pluginById().get(copy.descriptor)?.required_authorizations ?? [] : [];
  const versionsDiffer = () => {
    const composition = props.profile?.composition_check;
    const registry = props.profile?.tool_registry_check;
    return Boolean(composition && registry && composition.dsh_version !== registry.dsh_version);
  };
  const checkOutdated = () => props.profile?.composition_check?.matches_local_files === false
    || props.profile?.tool_registry_check?.matches_local_files === false || versionsDiffer();
  const registry = createMemo(() => {
    const check = props.profile?.tool_registry_check;
    return (props.profileHealth === "ready" || props.profileHealth === "loading") && check?.matches_local_files && !checkOutdated()
      ? { bundles: new Set(check.bundles), tools: new Set(check.registered_tools) }
      : null;
  });
  const matchingTools = createMemo(() => {
    const words = normalizeSearch(query()).trim().split(/\s+/).filter(Boolean);
    if (!words.length) return TOOLS;
    return TOOLS.filter(({ copy, searchText }) => {
      const fields = normalizeSearch(authorizationFields(copy).join(" "));
      return words.every((word) => searchText.includes(word) || fields.includes(word));
    });
  });
  type Tool = (typeof TOOLS)[number];
  const matchesStage = ({ name }: Tool) => {
    const stage = stageFilter();
    return stage === "all" || DSH_STAGE_TOOLS[stage].includes(name);
  };
  const matchesAccess = ({ copy }: Tool) => filter() === "all" || filter() === copy?.access;
  const inScope = (tool: Tool) => matchesStage(tool) && matchesAccess(tool);
  const visibleTools = createMemo(() => matchingTools().filter(inScope));
  const hasFilters = () => stageFilter() !== "all" || filter() !== "all";
  const noKeywordMatches = () => Boolean(query().trim()) && !matchingTools().length;
  const scopeCount = createMemo(() => TOOLS.filter(inScope).length);
  const hasHiddenMatches = () => Boolean(query().trim()) && matchingTools().length > visibleTools().length;
  const blockingLabels = () => {
    const stage = stageFilter(), access = filter();
    const labels: string[] = [];
    if (stage !== "all" && !matchingTools().every(matchesStage)) labels.push(x(continuationStageLabel(stage, "zh"), STAGE_FILTER_EN[stage]));
    if (access !== "all" && !matchingTools().every(matchesAccess)) labels.push(x(ACCESS_LABELS[access][0], ACCESS_FILTER_EN[access] ?? ACCESS_LABELS[access][1]));
    return labels.join(x("、", ", "));
  };
  const searchHasResults = () => Boolean(query().trim()) && visibleTools().length > 0;
  const singleMatch = () => searchHasResults() && visibleTools().length === 1;
  function focusTool(item: HTMLDetailsElement | null) {
    if (!item) return;
    item.open = true;
    item.querySelector("summary")?.focus();
  }
  onMount(() => props.onLookupReady?.(name => {
    const tool = TOOLS.find(entry => entry.name === name);
    if (!tool) return;
    batch(() => {
      if (!matchingTools().includes(tool)) setQuery(name);
      if (!matchesStage(tool)) setStageFilter("all");
      if (!matchesAccess(tool)) setFilter("all");
    });
    queueMicrotask(() => focusTool(results.querySelector<HTMLDetailsElement>(`[data-tool-name="${CSS.escape(name)}"]`)));
  }));
  const plainKey = (event: KeyboardEvent) => !event.isComposing && event.keyCode !== 229
    && !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;
  const browseFromSearch = (event: KeyboardEvent) => {
    if (!plainKey(event) || !searchHasResults()) return;
    if (event.key !== "ArrowDown" && !(event.key === "Enter" && singleMatch())) return;
    const item = results.querySelector<HTMLDetailsElement>(".dsh-tool-item");
    if (!item) return;
    event.preventDefault();
    if (event.key === "Enter") focusTool(item);
    else item.querySelector("summary")?.focus();
  };
  const browseFromSummary = (event: KeyboardEvent & { currentTarget: HTMLElement }) => {
    if (!plainKey(event) || !searchHasResults() || (event.key !== "ArrowDown" && event.key !== "ArrowUp")) return;
    const row = event.currentTarget.closest("li");
    const next = event.key === "ArrowDown" ? row?.nextElementSibling : row?.previousElementSibling;
    event.preventDefault();
    if (next) next.querySelector("summary")?.focus();
    else if (event.key === "ArrowUp") searchInput.focus();
  };
  const stageNote = () => {
    const stage = stageFilter();
    return stage === "all" ? undefined : DSH_STAGE_NOTES[stage];
  };
  const clearFilters = () => {
    const keepCompatible = hasHiddenMatches();
    batch(() => {
      if (!keepCompatible || !matchingTools().every(matchesStage)) setStageFilter("all");
      if (!keepCompatible || !matchingTools().every(matchesAccess)) setFilter("all");
    });
    searchInput.focus();
  };
  const recoverEmptySearch = () => {
    const scopeHasTools = scopeCount() > 0;
    batch(() => {
      setQuery("");
      if (!scopeHasTools) { setStageFilter("all"); setFilter("all"); }
    });
    searchInput.focus();
  };
  const installStatus = (bundle: string) => props.profile && props.profile.installation_state !== "unavailable"
    ? props.profile.packages.find((item) => item.package === bundle)?.install_status : undefined;
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
    if (versionsDiffer()) return x("组合和注册回执的 DSH 版本不同，待复核", "The composition and registry checks used different DSH versions.");
    if (checkOutdated()) return x("本机文件已变化，待复核", "Local files changed; recheck needed");
    if (!check) return x("安装文件已验证，待核验组合", "Files verified; composition unchecked");
    return x("安装文件与 tui 配置组合已核验", "Files and TUI composition verified");
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
            <input ref={searchInput} id={searchId} type="search" value={query()} maxLength={160} onKeyDown={browseFromSearch}
              aria-describedby={searchHasResults() ? `${searchId}-hint` : undefined} onInput={(event) => setQuery(event.currentTarget.value)} />
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
        <Show when={hasFilters()}>
          <ActionButton size="sm" variant={hasHiddenMatches() ? "secondary" : "quiet"} onClick={clearFilters}>{hasHiddenMatches()
            ? x(`查看全部 ${matchingTools().length} 项匹配`, matchingTools().length === 1 ? "Show 1 match across all tools" : `Show all ${matchingTools().length} matches`)
            : x("清除筛选", "Clear filters")}</ActionButton>
        </Show>
      </div>
    </div>
    <div ref={results} class="dsh-tool-results" role={props.scrollResults ? "region" : undefined}
      aria-label={props.scrollResults ? x("工具结果", "Tool results") : undefined} tabIndex={props.scrollResults ? 0 : undefined}>
      <Show when={searchHasResults()}><p id={`${searchId}-hint`}>{singleMatch()
        ? x("在搜索框按 Enter 展开此工具。", "Press Enter in the search field to open this tool.")
        : x("按向下键进入结果，用上下键选择工具，按 Enter 展开。", "Press Down Arrow to reach the results, Up or Down Arrow to choose a tool, and Enter to open it.")}</p></Show>
      <Show when={stageNote()}>{(note) => <p class="dsh-stage-note">{x(...note())}</p>}</Show>
      <Show when={visibleTools().length > 0} fallback={<div class="dsh-tool-empty">
        <p>{noKeywordMatches() ? x("全部工具中均未找到这个关键词。", "No tools match this search, even without filters.")
          : x(`当前筛选没有匹配工具（${blockingLabels()}）。`, `No tools match the active filters (${blockingLabels()}).`)}</p>
        <Show when={noKeywordMatches()}><ActionButton size="sm" onClick={recoverEmptySearch}>
          {hasFilters() && scopeCount() > 0
            ? x(`查看当前筛选的 ${scopeCount()} 个工具`, `Show ${scopeCount()} ${scopeCount() === 1 ? "tool" : "tools"} with these filters`)
            : x(`查看全部 ${TOOLS.length} 个工具`, `Show all ${TOOLS.length} tools`)}
        </ActionButton></Show>
      </div>}>
        <ul class="dsh-tool-list">
          <For each={visibleTools()}>{(tool) => {
            let summary!: HTMLElement;
            const authorizations = () => authorizationFields(tool.copy);
            const label = () => tool.copy ? x(...tool.copy.label) : tool.name;
            const registered = () => registry()?.bundles.has(tool.bundle) ? registry()?.tools.has(tool.name) : undefined;
            const repairRegistration = () => registered() === false && canRepairBundleRegistration(props.profile, tool.bundle);
            const needsRepair = () => {
              const status = installStatus(tool.bundle);
              if (!status) return false;
              const composition = props.profile?.composition_check;
              return status !== "verified" || Boolean(composition?.matches_local_files && !composition.bundles.includes(tool.bundle));
            };
            const commandKind = (): CommandKind => {
              if (location && props.profileHealth === "legacy" && tool.name === "cosmatter_recent_runs") return "update";
              if (checkCommand && (needsRepair() || repairRegistration())) return "repair";
              if (checkCommand && (registered() === false || checkOutdated())) return "verify";
              return "read";
            };
            const commandCopy = () => COMMAND_COPY[commandKind()];
            const additionalCheck = () => repairRegistration() ? formattedCheckCommand() : null;
            const command = createMemo(() => {
              if (commandKind() === "update") return formatDshCommand(updatedWorkbenchCommand(props.runId));
              if (commandKind() === "repair") return formatDshCommand(BUNDLE_REPAIR_COMMAND);
              if (commandKind() === "verify") return formattedCheckCommand();
              const read = dshCatalogueCommand(tool.name, props.runId, props.evidence);
              return read ? formatDshCommand(read) : null;
            });
            const toolStatus = () => {
              const status = clipboard.feedback();
              return status?.target.name === tool.name && status.source.isConnected ? status : null;
            };
            return <li>
              <details class="harness-disclosure dsh-tool-item" data-tool-name={tool.name}>
                <summary ref={summary} onKeyDown={browseFromSummary}>
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
                  <Show when={authorizations().length}>
                    <div class="dsh-tool-consents"><strong>{x("所需授权字段", "Required authorization fields")}</strong>
                      <For each={authorizations()}>{(authorization) => <code>{authorization}</code>}</For>
                    </div>
                  </Show>
                  <Show when={command()}>{(line) => <div class="dsh-tool-terminal">
                    <p>{repairRegistration()
                      ? x("在所选终端运行补齐命令，接着核验当前端口，再刷新插件状态。", "Run the repair in the selected terminal, then check this port and refresh the bundle status.")
                      : commandKind() === "verify" && checkOutdated()
                      ? x("在终端重新核验当前插件文件和注册状态，再刷新本卡。", "Run the check against the current bundle files and tool registry, then refresh this card.")
                      : x(...commandCopy().hint)}</p>
                    <DshCommandText command={line()} />
                    <Show when={additionalCheck()}>{(next) => <DshCommandText command={next()} />}</Show>
                  </div>}</Show>
                  <div class="dsh-tool-actions">
                    <Show when={command()}>
                      <ActionButton size="sm" onClick={(event) => void clipboard.copy({ name: tool.name, kind: "command" }, command, event.currentTarget)}>{x(...commandCopy().button)}</ActionButton>
                    </Show>
                    <Show when={additionalCheck()}>
                      <ActionButton size="sm" onClick={(event) => void clipboard.copy({ name: tool.name, kind: "check" }, additionalCheck, event.currentTarget)}>
                        {x(...COMMAND_COPY.verify.button)}
                      </ActionButton>
                    </Show>
                    <Show when={props.onRefreshProfile && (commandKind() !== "read" || props.profileHealth === "unavailable" || props.profile?.installation_state === "unavailable")}>
                      <ActionButton size="sm" busy={props.profileHealth === "loading"} busyLabel={x("正在读取…", "Reading…")}
                        onClick={() => { summary.focus(); props.onRefreshProfile?.(); }}>{x("刷新插件状态", "Refresh bundle status")}</ActionButton>
                    </Show>
                    <ActionButton size="sm" variant={command() ? "quiet" : "secondary"} onClick={(event) => void clipboard.copy({ name: tool.name, kind: "name" }, () => tool.name, event.currentTarget)}>{x("复制工具名", "Copy tool name")}</ActionButton>
                  </div>
                  <Show when={toolStatus()}>{(status) => <Show when={status().copied} fallback={<DshManualCopy
                    locale={props.locale} label={status().target.kind === "name" ? x("DSH 工具名", "DSH tool name") : x("DSH 命令", "DSH command")}
                    value={status().value} source={status().source} />}>
                    <p role="status">{status().target.kind === "name" ? x("工具名已复制。", "Tool name copied.")
                      : x(...(status().target.kind === "check" ? COMMAND_COPY.verify : commandCopy()).copied)}</p>
                  </Show>}</Show>
                </div>
              </details>
            </li>;
          }}</For>
        </ul>
      </Show>
    </div>
  </div>;
}
