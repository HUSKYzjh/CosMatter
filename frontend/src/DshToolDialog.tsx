import { For, Show, createMemo, createSignal, onMount } from "solid-js";
import { DshToolCatalogueContent, type DshToolCatalogueProps } from "./DshToolCatalogue";
import { DshMissionDraft } from "./DshMissionDraft";
import type { LaunchMissionBoundary, LaunchMissionField } from "./launchMissionValidation";
import { DshCommandRow, DshSessionLaunch } from "./DshSessionLaunch";
import { OtherPortReceiptHelp, WorkbenchUpdateCommand } from "./WorkbenchUpdateCommand";
import { BUNDLE_REPAIR_COMMAND, dshProfileCheckCommand, localWorkbenchLocation } from "./dshLocalCommands";
import { DSH_TOOL_COUNT, dshSessionReadiness, missingRegisteredTools, type DshSessionReadiness } from "./dshSessionReadiness";
import { registryMatchesComposition } from "./dshReadProfile";
import type { HarnessCatalogueHealth } from "./localApi";
import { ActionButton } from "./uiPrimitives";
import "./dshSessionReceipt.css";

const views = ["catalogue", "session"] as const;
type DialogView = typeof views[number];

const SESSION_STATUS: Record<DshSessionReadiness, readonly [string, string]> = {
  checking: ["正在读取插件状态…", "Reading plugin status…"],
  "workbench-update": ["当前端口的工作台缺少 DSH 近期任务链接接口。", "The workbench on this port lacks the DSH recent-run links endpoint."],
  disconnected: ["请在已连接本机 API 的工作台查看会话状态。", "Open a workbench connected to the local API to check this session."],
  "repair-files": ["本机插件安装未齐。", "Some local plugin bundles need repair."],
  "profile-unavailable": ["未能读取本机插件安装状态。", "The local plugin installation status is unavailable."],
  "catalogue-unavailable": ["工作台未能读取插件目录。", "The workbench could not read the plugin catalogue."],
  "composition-unchecked": ["本机 tui 配置组合待核验。", "The local TUI configuration needs a composition check."],
  "repair-composition": ["本机 tui 配置缺少插件条目。", "The local TUI configuration is missing plugin entries."],
  "composition-check": ["本机 tui 配置组合需要重新核验。", "The local TUI configuration needs another composition check."],
  "registry-check": ["本机工具注册需要核验。", "Local tool registration needs checking."],
  "loopback-check": ["当前工作台端口的连通性待核验。", "DSH access to this workbench port needs checking."],
  ready: ["请从本机工作台打开 DSH 会话。", "Open the DSH session from the local workbench."],
};

export function DshToolDialog(props: DshToolCatalogueProps & {
  initialView?: DialogView;
  draft?: LaunchMissionBoundary | null;
  onEditDraftField?: (field: LaunchMissionField) => void;
  catalogueHealth: HarnessCatalogueHealth;
  onRefreshProfile: () => void;
  onRefreshCatalogue: () => void;
  onDismiss: () => void;
}) {
  let dialog!: HTMLDialogElement;
  let heading!: HTMLHeadingElement;
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const initialStage = props.currentStage;
  const [view, setView] = createSignal<DialogView>(props.initialView ?? "catalogue");
  const showLinkPreference = createSignal(false);
  const location = localWorkbenchLocation();
  const port = location ? Number(location.port || "80") : null;
  const readiness = createMemo(() => dshSessionReadiness(props.profile, props.profileHealth, props.catalogueHealth, port));
  const missingTools = createMemo(() => readiness() === "registry-check" ? missingRegisteredTools(props.profile) : []);
  let lookupTool: ((name: string) => void) | undefined;
  const statusLabel = () => {
    const state = readiness();
    const registry = props.profile?.tool_registry_check;
    const loopback = registry?.loopback_check;
    if (state === "loopback-check" && loopback?.port === port && loopback.status === "unavailable") {
      return x(`上次核验时，工具已注册，DSH 未能从工作台端口 ${port} 读取插件目录。`,
        `The last check confirmed tool registration, but DSH could not read the plugin catalogue on workbench port ${port}.`);
    }
    if (state === "registry-check" && registry) {
      if (!registryMatchesComposition(props.profile)) return x("工具注册回执已过期，请重新核验。", "The tool registration check is out of date. Run it again.");
      if (!missingTools().length) return x("核验未覆盖全部插件，请重新核验。", "Run the check again to cover every bundle.");
      return x(`已注册 ${registry.registered_tools.length}/${DSH_TOOL_COUNT} 个工具`, `Registered ${registry.registered_tools.length} of ${DSH_TOOL_COUNT} tools`);
    }
    return x(...SESSION_STATUS[state]);
  };
  const recoveryCommand = createMemo(() => {
    if (!port) return null;
    switch (readiness()) {
      case "repair-files":
      case "repair-composition": return BUNDLE_REPAIR_COMMAND;
      case "composition-unchecked":
      case "composition-check":
      case "registry-check":
      case "loopback-check": return dshProfileCheckCommand(port);
      default: return null;
    }
  });
  const selectTab = (tab: DialogView) => {
    setView(tab);
    dialog.querySelector<HTMLButtonElement>(`#dsh-${tab}-tab`)?.focus();
  };
  const navigateTabs = (event: KeyboardEvent) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    let next: DialogView;
    switch (event.key) {
      case "Home": next = "catalogue"; break;
      case "End": next = "session"; break;
      case "ArrowLeft":
      case "ArrowRight": next = view() === "catalogue" ? "session" : "catalogue"; break;
      default: return;
    }
    event.preventDefault();
    selectTab(next);
  };
  const wrapDialogFocus = (event: KeyboardEvent) => {
    if (event.key !== "Tab" || event.ctrlKey || event.altKey || event.metaKey || event.defaultPrevented) return;
    const first = dialog.querySelector<HTMLButtonElement>("header button");
    const active = document.activeElement;
    if (event.shiftKey && active !== first && active !== heading) return;
    const controls = dialog.querySelectorAll<HTMLElement>("button, input, select, textarea, summary, a[href], [tabindex]");
    const last = Array.from(controls).reverse().find(element =>
      element.tabIndex >= 0 && !element.matches(":disabled") && element.checkVisibility({ visibilityProperty: true }));
    if (!first || !last || (!event.shiftKey && active !== last)) return;
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
  };
  const refreshSession = () => {
    const state = readiness();
    selectTab("session");
    props.onRefreshProfile();
    if (state === "ready" || state === "catalogue-unavailable" || state === "disconnected") props.onRefreshCatalogue();
  };

  onMount(() => {
    dialog.showModal();
    const initialFocus = view() === "session" ? dialog.querySelector<HTMLButtonElement>("#dsh-session-tab")
      : window.matchMedia("(pointer: coarse)").matches ? heading : dialog.querySelector<HTMLInputElement>('input[type="search"]');
    initialFocus?.focus();
  });

  return <dialog ref={dialog} class="dsh-tool-dialog" aria-labelledby="dsh-tool-dialog-title" onKeyDown={wrapDialogFocus} onClose={() => props.onDismiss()}>
    <header>
      <h2 id="dsh-tool-dialog-title" ref={heading} tabIndex={-1}>{x("DSH 工具与会话", "DSH tools and sessions")}</h2>
      <ActionButton size="sm" variant="quiet" aria-label={x("关闭 DSH 面板", "Close DSH panel")}
        onClick={() => dialog.close()}>{x("关闭", "Close")}</ActionButton>
    </header>
    <div class="dsh-dialog-tabs" role="tablist" aria-label={x("DSH 视图", "DSH views")} onKeyDown={navigateTabs}>
      <For each={views}>{(tab) => <button type="button" role="tab" id={`dsh-${tab}-tab`} aria-controls={`dsh-${tab}-panel`}
        aria-selected={view() === tab} tabIndex={view() === tab ? 0 : -1} onClick={() => selectTab(tab)}>
        {tab === "catalogue" ? x("工具目录", "Tool catalogue") : x("DSH 会话", "DSH session")}
      </button>}</For>
    </div>
    <div class="dsh-dialog-catalogue" role="tabpanel" id="dsh-catalogue-panel" aria-labelledby="dsh-catalogue-tab" hidden={view() !== "catalogue"}>
      <DshToolCatalogueContent locale={props.locale} plugins={props.plugins} profile={props.profile} profileHealth={props.profileHealth}
        currentStage={props.currentStage} runId={props.runId} evidence={props.evidence} onRefreshProfile={props.onRefreshProfile} initialStage={initialStage}
        onLookupReady={openTool => { lookupTool = openTool; }} scrollResults />
    </div>
    <div class="dsh-dialog-session" role="tabpanel" id="dsh-session-panel" aria-labelledby="dsh-session-tab" tabIndex={0} hidden={view() !== "session"}>
      <Show when={readiness() === "ready" && port} fallback={<>
        <p role="status">{statusLabel()}</p>
        <Show when={missingTools().length > 0}>
          <details class="harness-disclosure dsh-registry-gaps" open={missingTools().length <= 3}>
            <summary><span>{x("注册缺项", "Missing registrations")}</span><strong>{missingTools().length}</strong></summary>
            <ul><For each={missingTools()}>{tool => <li>
              <button type="button" aria-label={x(`在目录中查看 ${tool.name}`, `View ${tool.name} in catalogue`)}
                onClick={() => { selectTab("catalogue"); lookupTool?.(tool.name); }}>{tool.name}</button>
              <code>{tool.bundle}</code>
            </li>}</For></ul>
          </details>
          <p>{x("在 CosMatter 仓库根目录运行补齐命令，重新链接缺少工具的插件包。", "Run the repair command from the CosMatter repository root to relink the bundles missing tools.")}</p>
          <DshCommandRow locale={props.locale} command={BUNDLE_REPAIR_COMMAND} label={x("复制补齐命令", "Copy repair command")} />
        </Show>
        <Show when={readiness() === "workbench-update"}><WorkbenchUpdateCommand locale={props.locale} runId={props.runId} /></Show>
        <Show when={recoveryCommand()}>{(command) => <>
          <p>{command() === BUNDLE_REPAIR_COMMAND
            ? x("在 CosMatter 仓库根目录运行补齐命令，然后刷新会话状态。", "Run the repair command from the CosMatter repository root, then refresh the session status.")
            : x("在 CosMatter 终端运行核验命令，然后刷新会话状态。", "Run the check in the CosMatter terminal, then refresh the session status.")}</p>
          <DshCommandRow locale={props.locale} command={command()} label={command() === BUNDLE_REPAIR_COMMAND
            ? x("复制补齐命令", "Copy repair command") : x("复制核验命令", "Copy check command")} />
        </>}</Show>
        <Show when={readiness() !== "ready"}>
          <ActionButton size="sm" busy={readiness() === "checking"} busyLabel={x("正在读取…", "Reading…")} onClick={refreshSession}>
            {readiness() === "catalogue-unavailable" ? x("重试目录连接", "Retry catalogue connection") : x("刷新会话状态", "Refresh session status")}
          </ActionButton>
        </Show>
        <OtherPortReceiptHelp locale={props.locale} runId={props.runId} readiness={readiness()}
          port={port} receiptPort={props.profile?.tool_registry_check?.loopback_check?.port} />
      </>}>{(localPort) => <>
        <Show when={props.profile?.tool_registry_check}>{(receipt) => <div class="dsh-session-receipt">
          <p>{x(`上次核验通过 · 工作台端口 ${localPort()}`, `Last check passed · Workbench port ${localPort()}`)}
            <time dateTime={receipt().checked_at}>{new Intl.DateTimeFormat(props.locale === "zh" ? "zh-CN" : "en",
              { dateStyle: "medium", timeStyle: "short" }).format(new Date(receipt().checked_at))}</time>
          </p>
          <ActionButton size="sm" variant="quiet" onClick={refreshSession}>{x("刷新会话状态", "Refresh session status")}</ActionButton>
        </div>}</Show>
        <DshSessionLaunch locale={props.locale} port={localPort()} runId={props.runId} showLinkPreference={showLinkPreference} />
      </>}</Show>
      <Show when={!props.runId && props.draft}>{(draft) => <DshMissionDraft locale={props.locale} draft={draft()} onEditField={props.onEditDraftField} />}</Show>
    </div>
  </dialog>;
}
