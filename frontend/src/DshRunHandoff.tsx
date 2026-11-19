import { DshCommandText } from "./DshCommandText";
import { createMemo, Show, useContext } from "solid-js";
import { createDshClipboard, DshManualCopy } from "./DshManualCopy";
import { DshCommandRow } from "./DshSessionLaunch";
import { DshReadProfile, dshReadIssue, type DshReadCommand, type DshReadIssue } from "./dshReadProfile";
import { isLocalRunId, localRunArtifactsLink, localRunScreeningLink } from "./liveRunIdentity";
import { BUNDLE_REPAIR_COMMAND, dshProfileCheckCommand, localEvidenceLink, localWorkbenchLocation, type DshEvidenceTarget } from "./dshLocalCommands";
import { ActionButton } from "./uiPrimitives";
import type { UiLocale } from "./fleetRegistry";

function DshReadRecovery(props: { issue: DshReadIssue; locale: UiLocale; focusAfterRefresh: () => void }) {
  const profile = useContext(DshReadProfile)!;
  const port = Number(localWorkbenchLocation()?.port || "80");
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const hint = () => {
    const issue = props.issue;
    if (issue.kind === "repair") return x(
      `插件 ${issue.bundle} 缺少有效文件。在 CosMatter 仓库根目录运行补齐命令，然后刷新插件状态。`,
      `Bundle ${issue.bundle} is missing valid files. Run the repair from the CosMatter repository root and refresh the bundle status.`);
    return x(`隔离核验未注册 ${issue.missingTools.join("、")}。核对已安装的插件版本后，在终端运行核验命令并刷新插件状态。`,
      `The isolated check did not register ${issue.missingTools.join(", ")}. Check the installed bundle version, run the terminal check and refresh the bundle status.`);
  };
  return <div class="dsh-read-recovery">
    <p>{hint()}</p>
    <DshCommandRow locale={props.locale} command={props.issue.kind === "repair" ? BUNDLE_REPAIR_COMMAND : dshProfileCheckCommand(port)}
      label={props.issue.kind === "repair" ? x("复制补齐命令", "Copy repair command") : x("复制核验命令", "Copy check command")} />
    <ActionButton size="sm" busy={profile.health() === "loading"} busyLabel={x("正在读取…", "Reading…")}
      onClick={() => { props.focusAfterRefresh(); profile.refresh(); }}>{x("刷新插件状态", "Refresh bundle status")}</ActionButton>
  </div>;
}

function DshCommandHandoff(props: { read: DshReadCommand; command: string; label: string; locale: UiLocale; description?: string }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const profile = useContext(DshReadProfile);
  const issue = createMemo(() => profile && dshReadIssue(props.read, profile.profile(), profile.health()));
  const { copy, feedback } = createDshClipboard<"command">();
  let summary!: HTMLElement;

  return <details class="harness-disclosure dsh-run-handoff">
    <summary ref={summary}><span>{props.label}</span></summary>
    <div>
      <Show when={issue()} fallback={<>
      <Show when={props.description}><p>{props.description}</p></Show>
      <DshCommandText command={props.command} />
      <ActionButton size="sm" onClick={(event) => void copy("command", () => issue() ? null : props.command, event.currentTarget)}>{x("复制 DSH 命令", "Copy DSH command")}</ActionButton>
      <Show when={feedback()}>{(state) => <Show when={state().copied} fallback={<DshManualCopy locale={props.locale}
        label={x("DSH 命令", "DSH command")} value={state().value} source={state().source} />}>
        <p role="status">{x("DSH 命令已复制。", "DSH command copied.")}</p>
      </Show>}</Show>
      </>}>{(problem) => <DshReadRecovery issue={problem()} locale={props.locale} focusAfterRefresh={() => summary.focus()} />}</Show>
    </div>
  </details>;
}

export function DshRunHandoff(props: { runId: string; locale: UiLocale }) {
  const location = localWorkbenchLocation();
  return <Show when={location && isLocalRunId(props.runId)}>
    <DshCommandHandoff read="status" locale={props.locale} command={`cosmatter dsh-run-status ${props.runId} --port ${location?.port || "80"}`}
      label={props.locale === "zh" ? "在 DSH 查看进度" : "Check progress in DSH"}
      description={props.locale === "zh"
        ? "在 CosMatter 的终端环境运行命令，读取当前进度和下一阶段的门禁。"
        : "Run this in the CosMatter terminal environment to read progress and requirements for the next stage."} />
  </Show>;
}

export function DshRecentRunsHandoff(props: { locale: UiLocale }) {
  const location = localWorkbenchLocation();
  if (!location) return null;
  return <DshCommandHandoff read="recent" locale={props.locale} command={`cosmatter dsh-recent-runs --port ${location.port || "80"}`}
    label={props.locale === "zh" ? "在 DSH 查找最近任务" : "Find recent runs in DSH"}
    description={props.locale === "zh"
      ? "在 CosMatter 的终端环境运行命令，即可获取最近的运行 ID 和本机打开链接。"
      : "Run this in the CosMatter terminal environment to find recent run IDs and local workbench links."} />;
}

export function DshRunArtifactsHandoff(props: { runId: string; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const location = localWorkbenchLocation();
  const href = () => location && isLocalRunId(props.runId) ? localRunArtifactsLink(location.origin, props.runId) : null;
  return <Show when={href()} keyed>{(link) =>
    <DshLinkedHandoff read="artifacts" locale={props.locale} link={link} linkLabel={x("工件目录链接", "Artifact list link")}
      copyLabel={x("复制工件目录链接", "Copy artifact list link")} copiedLabel={x("工件目录链接已复制。", "Artifact list link copied.")}
      command={`cosmatter dsh-run-artifacts ${props.runId} --port ${location?.port || "80"}`}
      commandLabel={x("查看工件目录命令", "View artifact list command")} />
  }</Show>;
}

export function DshEvidenceHandoff(props: DshEvidenceTarget & { runId: string; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  return <Show when={localEvidenceLink(props.runId, props)} keyed>{(link) =>
    <DshLinkedHandoff read="evidence" locale={props.locale} link={link} linkLabel={x("证据链接", "Evidence link")}
      copyLabel={x("复制证据链接", "Copy evidence link")} copiedLabel={x("证据链接已复制。", "Evidence link copied.")}
      command={`cosmatter dsh-evidence '${link}'`} commandLabel={x("查看证据命令", "View evidence command")} />
  }</Show>;
}

export function DshScreeningHandoff(props: { runId: string; revision: string; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const location = localWorkbenchLocation();
  const href = () => location && isLocalRunId(props.runId) && /^[a-f0-9]{64}$/.test(props.revision)
    ? localRunScreeningLink(location.origin, props.runId, props.revision) : null;
  return <Show when={href()} keyed>{(link) =>
    <DshLinkedHandoff read="screening" locale={props.locale} link={link} linkLabel={x("筛选清单链接", "Screening checklist link")}
      copyLabel={x("复制筛选链接", "Copy screening link")} copiedLabel={x("筛选链接已复制。", "Screening link copied.")}
      command={`cosmatter dsh-screening '${link}'`} commandLabel={x("查看筛选清单命令", "View screening checklist command")}
      description={x("命令读取本机已保存的清单和决定。未提交的草稿保留在当前浏览器标签页。", "The command reads the saved checklist and decisions. Draft edits stay in this browser tab.")} />
  }</Show>;
}

function DshLinkedHandoff(props: { read: DshReadCommand; locale: UiLocale; link: string; linkLabel: string; copyLabel: string; copiedLabel: string; command: string; commandLabel: string; description?: string }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const profile = useContext(DshReadProfile);
  const issue = createMemo(() => profile && dshReadIssue(props.read, profile.profile(), profile.health()));
  let linkButton!: HTMLButtonElement;
  const { copy, feedback } = createDshClipboard<"link" | "command">();
  let preview!: HTMLDetailsElement;

  const copyCommand = async (button: HTMLButtonElement) => {
    if (await copy("command", () => issue() ? null : props.command, button) === false) preview.open = true;
  };

  return <div class="dsh-linked-handoff">
    <div class="dsh-linked-actions">
      <ActionButton ref={linkButton} size="sm" onClick={(event) => void copy("link", () => props.link, event.currentTarget)}>{props.copyLabel}</ActionButton>
      <Show when={!issue()}><ActionButton size="sm" onClick={(event) => void copyCommand(event.currentTarget)}>{x("复制 DSH 命令", "Copy DSH command")}</ActionButton></Show>
    </div>
    <Show when={feedback()}>{(state) => <Show when={state().copied} fallback={<DshManualCopy locale={props.locale}
      label={state().target === "link" ? props.linkLabel : x("DSH 命令", "DSH command")} value={state().value} source={state().source} />}>
      <p role="status">{state().target === "command" ? x("DSH 命令已复制。", "DSH command copied.") : props.copiedLabel}</p>
    </Show>}</Show>
    <Show when={issue()} fallback={<details ref={preview} class="harness-disclosure dsh-run-handoff">
      <summary><span>{props.commandLabel}</span></summary>
      <div>
        <Show when={props.description}><p>{props.description}</p></Show>
        <DshCommandText command={props.command} />
      </div>
    </details>}>{(problem) => <DshReadRecovery locale={props.locale} issue={problem()} focusAfterRefresh={() => linkButton.focus()} />}</Show>
  </div>;
}
