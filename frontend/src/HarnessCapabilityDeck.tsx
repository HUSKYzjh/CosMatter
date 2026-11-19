import { For, Show, createMemo, createSignal } from "solid-js";
import { packages } from "../../plugins/dsh-plugin-group.json";

import type { DshProfileHealth, DshProfileStatus, HarnessAuthorization, HarnessCatalogueHealth, HarnessPluginDescriptor, OperationalTelemetry, WorkflowStageName } from "./localApi";
import { ActionButton, StatusBadge } from "./uiPrimitives";
import type { UiLocale } from "./fleetRegistry";
import { harnessRuntimeSummary } from "./harnessRuntimeSummary";
import { DshToolCatalogue } from "./DshToolCatalogue";
import { BUNDLE_REPAIR_COMMAND, dshProfileCheckCommand, localWorkbenchLocation } from "./dshLocalCommands";
import { DshSessionLaunch } from "./DshSessionLaunch";
import { DSH_TOOL_COUNT as TOOL_COUNT, dshSessionReadiness } from "./dshSessionReadiness";

const t = (locale: UiLocale, zh: string, en: string) => locale === "zh" ? zh : en;
type ActivationAction = "bundles" | "terminal" | "profile" | "catalogue";
type ActivationVerdict = {
  state: "checking" | "partial" | "disconnected" | "ready";
  title: string;
  detail: string;
  action?: ActivationAction;
};

const BUNDLE_ROLES: Record<string, readonly [string, string]> = {
  "@cosmatter/dsh-mission-plugin": ["任务建立", "Mission intake"],
  "@cosmatter/dsh-observability-plugin": ["状态观测", "Status observation"],
  "@cosmatter/dsh-policy-plugin": ["授权策略", "Authorization policy"],
  "@cosmatter/dsh-research-plugin": ["受控检索", "Controlled retrieval"],
  "@cosmatter/dsh-review-plugin": ["人工筛选", "Human screening"],
  "@cosmatter/dsh-document-plugin": ["私有全文", "Private full text"],
  "@cosmatter/dsh-graph-plugin": ["文献图谱", "Literature graph"],
};

const dependencyKindLabel = (locale: UiLocale, kind: DshProfileStatus["packages"][number]["dependency_kind"]) => {
  if (kind === "local_link") return t(locale, "本地链接", "Local link");
  if (kind === "registry_reference") return t(locale, "包引用", "Registry reference");
  if (kind === "remote_reference") return t(locale, "远程引用", "Remote reference");
  return t(locale, "未登记", "Absent");
};

const installStatusLabel = (locale: UiLocale, state: DshProfileStatus["packages"][number]["install_status"]) => {
  if (state === "verified") return t(locale, "已验证", "Verified");
  if (state === "missing_bundle") return t(locale, "文件缺失", "Files missing");
  if (state === "invalid_bundle") return t(locale, "包结构异常", "Invalid bundle");
  return t(locale, "未声明依赖", "Undeclared");
};

export function HarnessCapabilityDeck(props: {
  locale: UiLocale;
  health: HarnessCatalogueHealth;
  plugins: HarnessPluginDescriptor[] | null;
  authorization: HarnessAuthorization | null;
  profile: DshProfileStatus | null;
  profileHealth: DshProfileHealth;
  operationalTelemetry: OperationalTelemetry | null;
  operationPending?: boolean;
  currentStage?: WorkflowStageName | null;
  runId?: string | null;
  onRefresh?: () => void;
  onRefreshProfile?: () => void;
}) {
  const x = (zh: string, en: string) => t(props.locale, zh, en);
  const permitted = createMemo(() => props.authorization?.plugin_authorization_decisions.filter((item) => item.permitted) ?? []);
  const pluginById = createMemo(() => new Map((props.plugins ?? []).map((plugin) => [plugin.plugin_id, plugin])));
  const externalCount = createMemo(() => (props.plugins ?? []).filter((plugin) => plugin.automation_class === "external_authorized").length);
  const humanGateCount = createMemo(() => (props.plugins ?? []).filter((plugin) => plugin.requires_human_review || plugin.automation_class === "human_gate").length);
  const runtime = createMemo(() => harnessRuntimeSummary(props.operationalTelemetry));
  const workbenchLocation = localWorkbenchLocation();
  const loopbackPort = workbenchLocation ? Number(workbenchLocation.port || "80") : null;
  const checkCommand = dshProfileCheckCommand(loopbackPort);
  let verdictTitle!: HTMLElement;
  let packageProof: HTMLDetailsElement | undefined;
  let packageSummary: HTMLElement | undefined;
  let terminalCopy: HTMLButtonElement | undefined;
  const [copyFeedback, setCopyFeedback] = createSignal<{ command: string; copied: boolean } | null>(null);
  const copyCommand = async (command: string) => {
    try {
      await navigator.clipboard.writeText(command);
      setCopyFeedback({ command, copied: true });
    } catch {
      setCopyFeedback({ command, copied: false });
    }
  };
  const feedbackFor = (command: string) => {
    const feedback = copyFeedback();
    return feedback?.command === command ? feedback : null;
  };
  const copyStatus = (copied: boolean) => copied ? x("已复制。", "Copied.")
    : x("剪贴板不可用，请选中命令手动复制。", "Clipboard unavailable. Select the command and copy it manually.");
  const composition = () => props.profile?.composition_check;
  const bundleListIncomplete = () => composition()?.matches_local_files === true
    && (composition()?.bundles.length ?? 0) < (props.profile?.expected_bundle_count ?? 0);
  const registry = () => props.profileHealth === "ready" ? props.profile?.tool_registry_check : undefined;
  const loopbackLabel = createMemo(() => {
    const check = registry();
    if (!check?.loopback_check || check.loopback_check.port !== loopbackPort) {
      return { tone: "neutral" as const, text: x("当前端口未核验", "Port not checked") };
    }
    if (!check.matches_local_files) return { tone: "attention" as const, text: x("文件已变化，需重新核验", "Files changed; recheck needed") };
    switch (check.loopback_check.status) {
      case "verified": return { tone: "ready" as const, text: x("上次连通核验通过", "Last connection check passed") };
      case "tool_not_registered": return { tone: "attention" as const, text: x("目录工具未注册", "Catalogue tool unregistered") };
      case "unavailable": return { tone: "attention" as const, text: x("上次未能读取目录", "Last catalogue read failed") };
    }
  });
  const registryLabel = createMemo(() => {
    const check = registry();
    if (!check) return { tone: "neutral" as const, text: x("工具注册待核验", "Tool registration unchecked") };
    if (!check.matches_local_files) return { tone: "attention" as const, text: x("工具核验已过期", "Tool check out of date") };
    const count = check.registered_tools.length;
    return {
      tone: count === TOOL_COUNT ? "ready" as const : "attention" as const,
      text: x(`已注册 ${count}/${TOOL_COUNT}`, `Registered ${count}/${TOOL_COUNT}`),
    };
  });
  const compositionLabel = createMemo(() => {
    const check = composition();
    if (!check) return { tone: "neutral" as const, text: x("配置组合待核验", "Composition unchecked") };
    if (!check.matches_local_files) return { tone: "attention" as const, text: x("文件已变化，待复核", "Files changed; recheck needed") };
    const count = check.bundles.length;
    return {
      tone: count === props.profile?.expected_bundle_count ? "ready" as const : "attention" as const,
      text: x(`上次组合 ${count}/7`, `Last composed ${count}/7`),
    };
  });
  const profileBadge = createMemo(() => {
    const profile = props.profile;
    if (props.profileHealth === "loading") return { tone: "active" as const, copy: x("检查中", "Checking") };
    if (props.profileHealth === "disabled") return { tone: "neutral" as const, copy: x("只读预览未检查", "Not checked in preview") };
    if (!profile || profile.installation_state === "unavailable") return { tone: "attention" as const, copy: x("状态不可用", "Status unavailable") };
    const count = `${profile.installed_bundle_count}/${profile.expected_bundle_count}`;
    return { tone: profile.installation_state === "installed" ? "ready" as const : "attention" as const, copy: x(`已验证 ${count}`, `Verified ${count}`) };
  });
  const activation = createMemo<ActivationVerdict>(() => {
    const readiness = dshSessionReadiness(props.profile, props.profileHealth, props.health, loopbackPort);
    if (readiness === "checking") return {
      state: "checking",
      title: x("正在核验 DSH 启用条件", "Checking DSH enablement conditions"),
      detail: x("正在读取本机安装状态和插件契约。", "Reading the local installation status and plugin contracts."),
    };
    if (readiness === "repair-files") {
      const { installed_bundle_count: installed, expected_bundle_count: expected } = props.profile!;
      return {
        state: "partial", action: "bundles",
        title: x("插件安装未齐", "Bundle installation incomplete"),
        detail: x(`已验证 ${installed}/${expected} 个插件包。逐包检查会标出未声明或缺少有效文件的包。`,
          `${installed} of ${expected} bundles verified. The bundle list identifies undeclared or invalid installations.`),
      };
    }
    if (readiness === "profile-unavailable") return {
      state: "partial", action: props.onRefreshProfile ? "profile" : undefined,
      title: x("插件安装状态不可用", "Installation status unavailable"),
      detail: x("重新读取本机 tui 的插件安装和核验回执。", "Reload installed bundles and check receipts for the local TUI profile."),
    };
    if (readiness === "catalogue-unavailable") return {
      state: "partial", action: props.onRefresh ? "catalogue" : undefined,
      title: x("工作台未能读取插件目录", "Workbench catalogue read failed"),
      detail: x("重试工作台到本机目录的读取。", "Retry the workbench connection to the local catalogue."),
    };
    if (readiness === "disconnected") return {
      state: "disconnected",
      title: x("DSH 插件桥未启用", "DSH plugin bridge not enabled"),
      detail: x("可在启用本地 API 的工作台检查插件状态。", "Check plugin status in a workbench with the local API enabled."),
    };
    const terminal = props.onRefreshProfile ? "terminal" : undefined;
    if (readiness === "composition-unchecked") return {
      state: "partial", action: terminal,
      title: x("安装与契约已就绪，工具注册待核验", "Installation and contracts ready; tool registration unchecked"),
      detail: x("终端命令可一并核验配置组合和工具注册。", "The terminal command checks both composition and tool registration."),
    };
    if (readiness === "repair-composition" || readiness === "composition-check" || readiness === "registry-check") return {
      state: "partial", action: readiness === "repair-composition" ? "bundles" : terminal,
      title: readiness === "registry-check" ? registryLabel().text : compositionLabel().text,
      detail: readiness === "repair-composition" ? x("从插件清单检查缺少的 tui 组合条目。", "Inspect the bundle list for missing TUI composition entries.")
        : x("在终端核验当前 tui 组合和工具注册结果。", "Check the current TUI composition and registrations in the terminal."),
    };
    if (readiness === "loopback-check") return {
      state: "partial", action: terminal,
      title: loopbackLabel().text,
      detail: x(`工具已注册 ${TOOL_COUNT}/${TOOL_COUNT}。请核验 DSH 到工作台端口 ${loopbackPort} 的连通性。`,
        `All ${TOOL_COUNT} tools are registered. Check DSH access to workbench port ${loopbackPort}.`),
    };
    return {
      state: "ready",
      title: loopbackPort ? x("插件注册与本机连通已核验", "Registration and local access verified")
        : x("七个插件通过隔离注册核验", "All seven bundles passed isolated registration"),
      detail: x(`DSH 已注册全部 ${TOOL_COUNT} 个工具。任务派发结果见本次运行回执。`, `DSH registered all ${TOOL_COUNT} tools. See this mission’s receipts for dispatch results.`),
    };
  });
  const actionLabel = (action: ActivationAction) => ({
    bundles: bundleListIncomplete() ? x("查看插件清单", "Inspect bundles") : x("查看安装问题", "Inspect installation"),
    terminal: x("前往终端核验", "Go to terminal checks"),
    profile: x("重读安装状态", "Reload installation status"),
    catalogue: x("重试目录连接", "Retry catalogue connection"),
  })[action];
  const handleAction = (action: ActivationAction) => {
    if (action === "bundles" && packageProof) {
      packageProof.open = true;
      packageSummary?.focus();
    } else if (action === "terminal") {
      terminalCopy?.focus();
    } else {
      verdictTitle.focus();
      if (action === "profile") props.onRefreshProfile?.();
      if (action === "catalogue") props.onRefresh?.();
    }
  };
  const badge = () => props.health === "ready"
    ? permitted().length ? { tone: "active" as const, copy: x("任务授权已登记", "Mission authorization recorded") }
      : { tone: "ready" as const, copy: x("本机目录已连接", "Local catalogue connected") }
    : props.health === "loading" ? { tone: "neutral" as const, copy: x("正在读取目录", "Reading catalogue") }
      : props.health === "unavailable" ? { tone: "attention" as const, copy: x("目录不可用", "Catalogue unavailable") }
        : { tone: "neutral" as const, copy: x("当前未连接", "Not connected") };

  return <section class={`harness-capability-deck state-${props.health}`} aria-label={x("DSH 插件桥状态", "DSH plugin bridge status")} aria-live="polite">
    <header>
      <div><small>DSH / COSMATTER ADAPTER SURFACE</small><h2>{x("插件桥与当前任务授权", "Plugin bridge and mission authorization")}</h2></div>
      <StatusBadge tone={badge().tone} pulse={props.health === "loading" || Boolean(props.operationPending)}>{badge().copy}</StatusBadge>
    </header>
    <section class="harness-activation-track" aria-label={x("DSH 启用层次", "DSH activation layers")}>
      <div classList={{ ready: profileBadge().tone === "ready", attention: profileBadge().tone === "attention", active: profileBadge().tone === "active" }}>
        <small>{x("安装文件", "Installation")}</small>
        <strong>{profileBadge().copy}</strong>
      </div>
      <div classList={{ ready: compositionLabel().tone === "ready", attention: compositionLabel().tone === "attention" }}>
        <small>{x("配置组合", "Composition")}</small>
        <strong>{compositionLabel().text}</strong>
      </div>
      <div classList={{ ready: registryLabel().tone === "ready", attention: registryLabel().tone === "attention" }}>
        <small>{x("隔离注册", "Isolated registration")}</small>
        <strong>{registryLabel().text}</strong>
      </div>
      <div classList={{ ready: props.health === "ready", attention: props.health === "unavailable" }}>
        <small>{x("契约目录", "Contracts")}</small>
        <strong>{props.health === "ready" ? x("契约目录已连接", "Contract catalogue connected") : props.health === "loading" ? x("正在连接目录", "Connecting catalogue") : x("目录未连接", "Catalogue disconnected")}</strong>
      </div>
      <div classList={{ ready: runtime().state === "completed", attention: runtime().state === "unknown" || runtime().state === "incomplete", active: Boolean(props.operationPending) }}>
        <small>{x("派发回执", "Dispatch receipts")}</small>
        <strong>{props.operationPending
          ? x("受控操作进行中", "Controlled operation active")
          : runtime().dispatchCount ? x(`${runtime().completedCount}/${runtime().dispatchCount} 派发完成`, `${runtime().completedCount}/${runtime().dispatchCount} dispatches complete`)
            : x("尚无执行回执", "No execution receipt")}</strong>
      </div>
    </section>
    <section class={`harness-activation-verdict state-${activation().state}`} aria-label={x("DSH 启用结论", "DSH enablement verdict")}>
      <i aria-hidden="true" />
      <div><small>{x("启用结论", "ENABLEMENT VERDICT")}</small><strong ref={verdictTitle} tabIndex={-1}>{activation().title}</strong></div>
      <div class="harness-activation-next">
        <p>{activation().detail}</p>
        <Show when={activation().action}>{(action) =>
          <ActionButton size="sm" onClick={() => handleAction(action())}>{actionLabel(action())}</ActionButton>
        }</Show>
      </div>
      <Show when={activation().state === "ready" && loopbackPort}>{(port) =>
        <DshSessionLaunch locale={props.locale} port={port()} runId={props.runId} />
      }</Show>
    </section>
    <Show when={props.health === "ready"} fallback={<div class="harness-catalogue-message"><p>{props.health === "loading"
      ? x("正在读取固定的本机能力契约；这不会加载插件、调用工具或授予执行权限。", "Reading the fixed local capability contracts. This does not load a plugin, call a tool, or grant execution permission.")
      : props.health === "unavailable"
        ? x("未能验证本机插件目录，因此本页不显示任何可用能力。任务工件与门禁保持不变。", "The local plugin catalogue could not be verified, so no capability is shown as available. Mission artifacts and gates remain unchanged.")
        : x("只读预览或未启用本地 API 时，插件桥保持断开。", "The plugin bridge stays disconnected in read-only preview or when the local API is disabled.")}</p><Show when={props.health === "unavailable" && props.onRefresh && activation().action !== "catalogue"}><ActionButton size="sm" variant="secondary" onClick={() => props.onRefresh?.()}>{x("重试目录连接", "Retry catalogue connection")}</ActionButton></Show></div>}>
      <div class="harness-capability-metrics">
        <div><small>{x("已验证契约", "VERIFIED CONTRACTS")}</small><strong>{props.plugins?.length ?? 0}</strong><span>{x("静态描述符", "static descriptors")}</span></div>
        <div><small>{x("需外部授权", "EXTERNAL CONSENT")}</small><strong>{externalCount()}</strong><span>{x("逐任务批准", "mission-scoped")}</span></div>
        <div><small>{x("人工门禁", "HUMAN GATES")}</small><strong>{humanGateCount()}</strong><span>{x("不可自动接受", "never auto-accepted")}</span></div>
        <div classList={{ active: permitted().length > 0 }}><small>{x("本任务获准", "MISSION PERMITTED")}</small><strong>{permitted().length}</strong><span>{x("允许派发，非执行证明", "dispatch permission, not execution")}</span></div>
      </div>
    </Show>
    <div class="harness-state-ledger">
        <section class="harness-installation-card">
          <div>
            <small>{x("本机安装", "LOCAL INSTALLATION")}</small>
            <strong>DSH · {props.profile?.profile_name ?? "tui"}</strong>
          </div>
          <StatusBadge tone={profileBadge().tone} pulse={props.profileHealth === "loading"}>{profileBadge().copy}</StatusBadge>
          <div class="harness-installation-footer">
            <p><Show when={props.profileHealth !== "disabled" && props.profile?.installation_state !== "unavailable" && props.profile} fallback={props.profileHealth === "disabled"
              ? x("进入本机任务后可检查插件包。", "Open a local mission to check installed bundles.")
              : x("检查范围为 tui 的依赖声明和本机安装文件。", "This check covers TUI dependency declarations and local installation files.")}>
              {(profile) => x(`已声明 ${profile().declared_bundle_count} 个依赖。核对包清单，并确认入口与补丁文件存在。`, `${profile().declared_bundle_count} dependencies declared. Checks verify the manifest and the presence of the entry and patch files.`)}
            </Show></p>
          </div>
        </section>
        <section>
          <div><small>{x("执行证明 / 当前任务回执", "EXECUTION PROOF / CURRENT MISSION RECEIPTS")}</small><strong>{runtime().dispatchCount ? `${runtime().completedCount}/${runtime().dispatchCount}` : "—"}</strong></div>
          <StatusBadge tone={runtime().state === "completed" ? "ready" : runtime().state === "unknown" || runtime().state === "incomplete" ? "attention" : props.operationPending ? "active" : "neutral"} pulse={Boolean(props.operationPending)}>{props.operationPending
            ? x("操作进行中", "Operation in progress")
            : runtime().state === "completed" ? x("派发均已完成", "All dispatches completed")
              : runtime().state === "unknown" ? x("存在未知结果", "Unknown outcome present")
                : runtime().state === "incomplete" ? x("存在未完成派发", "Incomplete dispatch present")
                  : x("尚无派发回执", "No dispatch receipt")}</StatusBadge>
          <p>{runtime().dispatchCount
            ? x(`已登记 ${runtime().dispatchCount} 次派发：完成 ${runtime().completedCount}，未完成 ${runtime().incompleteCount}，结果未知 ${runtime().unknownCount}。`, `${runtime().dispatchCount} dispatch(es) recorded: ${runtime().completedCount} completed, ${runtime().incompleteCount} incomplete, ${runtime().unknownCount} unknown.`)
            : x("没有运行级派发记录；目录与安装状态不会被当作执行证明。", "No runtime dispatch is recorded. Catalogue and installation status are never treated as proof of execution.")}</p>
        </section>
        <Show when={props.profileHealth !== "disabled" && props.onRefreshProfile}>
          <section class="harness-composition-card" aria-label={x("DSH 终端核验", "DSH terminal checks")}>
            <div>
              <small>{x("终端核验", "TERMINAL CHECKS")}</small>
              <strong>{x("配置组合与工具注册", "Composition and tool registration")}</strong>
            </div>
            <StatusBadge tone={registryLabel().tone}>{registryLabel().text}</StatusBadge>
            <p>{loopbackPort
              ? x("在 CosMatter 终端运行命令，再刷新结果。隔离 DSH 进程会核验工具注册，并读取此端口的静态插件目录。", "Run the command in the CosMatter terminal, then refresh. An isolated DSH process checks registration and reads the static catalogue on this port.")
              : x("在 CosMatter 终端运行命令，再刷新结果。工具注册在独立 DSH 进程中核验。", "Run the command in the CosMatter terminal, then refresh. Tool registration is checked in an isolated DSH process.")}</p>
            <Show when={loopbackPort}><p class="harness-loopback-proof">
              <span>{x(`工作台端口 ${loopbackPort}`, `Workbench port ${loopbackPort}`)}</span>
              <StatusBadge tone={loopbackLabel().tone}>{loopbackLabel().text}</StatusBadge>
            </p></Show>
            <Show when={registry() ?? composition()}>{(check) => <p class="harness-composition-result">
              <time dateTime={check().checked_at}>{new Intl.DateTimeFormat(props.locale === "zh" ? "zh-CN" : "en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(check().checked_at))}</time>
              <span>DSH {check().dsh_version}</span>
            </p>}</Show>
            <div class="harness-installation-footer harness-copy-row">
              <code>{checkCommand}</code>
              <ActionButton ref={terminalCopy} size="sm" onClick={() => void copyCommand(checkCommand)}>{x("复制核验命令", "Copy check command")}</ActionButton>
              <ActionButton size="sm" busy={props.profileHealth === "loading"} busyLabel={x("正在读取…", "Reading…")} onClick={() => props.onRefreshProfile?.()}>
                {x("刷新核验结果", "Refresh check results")}
              </ActionButton>
            </div>
            <Show when={feedbackFor(checkCommand)}>{(feedback) => <p role="status">{copyStatus(feedback().copied)}</p>}</Show>
            <Show when={registry() && !registry()!.matches_local_files}><p>{x("本机配置或插件文件已变化，请在终端重新核验。", "Local configuration or bundle files changed. Run the terminal check again.")}</p></Show>
          </section>
        </Show>
    </div>
    <Show when={props.profile?.installation_state !== "unavailable" && props.profile}>{(profile) =>
      <details ref={packageProof} class="harness-disclosure harness-package-proof" aria-busy={props.profileHealth === "loading" || undefined}>
        <summary ref={packageSummary}>
          <span>{x("查看逐包检查结果", "Inspect bundle checks")}</span>
          <strong>{profile().installed_bundle_count}/{profile().expected_bundle_count}</strong>
        </summary>
        <ul>
          <For each={profile().packages}>{(packageStatus) => {
            const role = () => BUNDLE_ROLES[packageStatus.package] ?? [packageStatus.package, packageStatus.package] as const;
            const registration = () => {
              const check = registry();
              if (!check?.matches_local_files || !check.bundles.includes(packageStatus.package)) return null;
              const tools = packages.find(({ package: name }) => name === packageStatus.package)?.tools ?? [];
              return `${tools.filter((name) => check.registered_tools.includes(name)).length}/${tools.length}`;
            };
            const absentFromComposition = () => packageStatus.install_status === "verified"
              && composition()?.matches_local_files && !composition()?.bundles.includes(packageStatus.package);
            return <li classList={{ installed: packageStatus.install_status === "verified" }}>
              <i aria-hidden="true" />
              <div>
                <strong>{props.locale === "zh" ? role()[0] : role()[1]}</strong>
                <code>{packageStatus.package}</code>
              </div>
              <span class="harness-package-state"><b>{installStatusLabel(props.locale, packageStatus.install_status)}</b>
                <Show when={packageStatus.dependency_kind !== "absent"}><small>{dependencyKindLabel(props.locale, packageStatus.dependency_kind)}</small></Show>
                <Show when={absentFromComposition()}><small class="harness-package-composition-missing">{x("未进入配置组合", "Absent from composition")}</small></Show>
                <Show when={registration()}>{(count) => <small>{x(`注册 ${count()}`, `Registered ${count()}`)}</small>}</Show>
              </span>
            </li>;
          }}</For>
        </ul>
        <Show when={workbenchLocation && props.profileHealth === "ready"
          && (profile().installed_bundle_count < profile().expected_bundle_count || bundleListIncomplete())}>
          <section class="harness-bundle-repair" aria-label={x("补齐本机 DSH 插件", "Repair local DSH bundles")}>
            <p>{x("在 CosMatter 仓库根目录的终端运行。命令会补齐缺失或异常的本地链接，并将 CosMatter 插件加入 tui 启用清单。",
              "Run from the CosMatter repository root. The command repairs missing or invalid local links and enables the CosMatter bundles in TUI.")}</p>
            <div class="harness-copy-row">
              <code>{BUNDLE_REPAIR_COMMAND}</code>
              <ActionButton size="sm" onClick={() => void copyCommand(BUNDLE_REPAIR_COMMAND)}>{x("复制补齐命令", "Copy repair command")}</ActionButton>
              <Show when={props.onRefreshProfile}>
                <ActionButton size="sm" onClick={() => { packageSummary?.focus(); props.onRefreshProfile?.(); }}>
                  {x("刷新安装状态", "Refresh installation status")}
                </ActionButton>
              </Show>
            </div>
            <Show when={feedbackFor(BUNDLE_REPAIR_COMMAND)}>{(feedback) => <p role="status">{copyStatus(feedback().copied)}</p>}</Show>
          </section>
        </Show>
        <p>{x(
          "此处检查安装文件。配置组合、profile 启动和派发由各自的检查确认。",
          "These checks cover installed files. Profile composition, startup, and dispatch have separate checks.",
        )}</p>
      </details>
    }</Show>
    <Show when={!props.runId && (props.health !== "disabled" || props.profileHealth !== "disabled")}>
      <DshToolCatalogue locale={props.locale} plugins={props.health === "ready" ? props.plugins ?? [] : []} profile={props.profile} profileHealth={props.profileHealth}
        currentStage={props.currentStage} runId={props.runId} onRefreshProfile={props.onRefreshProfile} />
    </Show>
    <div class="harness-boundary-copy"><p>{props.health === "ready"
      ? x("目录已连接只证明 CosMatter 能读取本机静态契约；profile 依赖快照与运行回执分别证明不同层次，任何一层都不能代替工具结果。", "A connected catalogue proves only that CosMatter can read local static contracts. The profile dependency snapshot and runtime receipts prove separate layers; none can substitute for tool results.")
      : x("目录、profile 依赖快照与运行回执独立检查；其中一项不可用时，其余状态仍会如实显示，但不会据此开放执行权限。", "Catalogue, profile dependency snapshot, and runtime receipts are checked independently. When one is unavailable, the others remain visible without granting execution permission.")}</p><Show when={props.operationPending}><StatusBadge tone="active" pulse>{x("受控操作进行中", "Controlled operation in progress")}</StatusBadge></Show></div>
    <Show when={props.health === "ready" && permitted().length > 0}><div class="harness-permission-list"><small>{x("本任务授权判定", "MISSION AUTHORIZATION DECISIONS")}</small><div><For each={permitted()}>{(decision) => <span><i aria-hidden="true" /><strong>{pluginById().get(decision.plugin_id)?.title ?? decision.plugin_id}</strong><code>{decision.plugin_id}</code></span>}</For></div></div></Show>
  </section>;
}
