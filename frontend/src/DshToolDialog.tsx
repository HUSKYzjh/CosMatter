import { For, Show, createMemo, createSignal, onMount } from "solid-js";
import { DshToolCatalogueContent, type DshToolCatalogueProps } from "./DshToolCatalogue";
import { DshCommandRow, DshSessionLaunch } from "./DshSessionLaunch";
import { BUNDLE_REPAIR_COMMAND, dshProfileCheckCommand, localWorkbenchLocation } from "./dshLocalCommands";
import { dshSessionReadiness, type DshSessionReadiness } from "./dshSessionReadiness";
import type { HarnessCatalogueHealth } from "./localApi";
import { ActionButton } from "./uiPrimitives";

const views = ["catalogue", "session"] as const;
type DialogView = typeof views[number];

const SESSION_STATUS: Record<DshSessionReadiness, readonly [string, string]> = {
  checking: ["正在读取插件状态…", "Reading plugin status…"],
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
  catalogueHealth: HarnessCatalogueHealth;
  onRefreshProfile: () => void;
  onRefreshCatalogue: () => void;
  onDismiss: () => void;
}) {
  let dialog!: HTMLDialogElement;
  let heading!: HTMLHeadingElement;
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const initialStage = props.currentStage;
  const [view, setView] = createSignal<DialogView>("catalogue");
  const location = localWorkbenchLocation();
  const port = location ? Number(location.port || "80") : null;
  const readiness = createMemo(() => dshSessionReadiness(props.profile, props.profileHealth, props.catalogueHealth, port));
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
  const refreshSession = () => {
    const state = readiness();
    selectTab("session");
    if (state !== "catalogue-unavailable") props.onRefreshProfile();
    if (state === "catalogue-unavailable" || state === "disconnected") props.onRefreshCatalogue();
  };

  onMount(() => {
    dialog.showModal();
    const initialFocus = window.matchMedia("(pointer: coarse)").matches ? heading : dialog.querySelector<HTMLInputElement>('input[type="search"]');
    initialFocus?.focus();
  });

  return <dialog ref={dialog} class="dsh-tool-dialog" aria-labelledby="dsh-tool-dialog-title" onClose={() => props.onDismiss()}>
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
        currentStage={props.currentStage} runId={props.runId} evidence={props.evidence} onRefreshProfile={props.onRefreshProfile} initialStage={initialStage} scrollResults />
    </div>
    <div class="dsh-dialog-session" role="tabpanel" id="dsh-session-panel" aria-labelledby="dsh-session-tab" hidden={view() !== "session"}>
      <Show when={readiness() === "ready" && port} fallback={<>
        <p role="status">{x(...SESSION_STATUS[readiness()])}</p>
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
      </>}>{(localPort) => <DshSessionLaunch locale={props.locale} port={localPort()} runId={props.runId} />}</Show>
    </div>
  </dialog>;
}
