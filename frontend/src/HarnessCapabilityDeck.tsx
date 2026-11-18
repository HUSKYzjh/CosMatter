import { For, Show, createMemo, createSignal } from "solid-js";

import type { DshProfileHealth, DshProfileStatus, HarnessAuthorization, HarnessCatalogueHealth, HarnessPluginDescriptor, OperationalTelemetry } from "./localApi";
import { ActionButton, StatusBadge } from "./uiPrimitives";
import type { UiLocale } from "./fleetRegistry";
import { harnessRuntimeSummary } from "./harnessRuntimeSummary";

const t = (locale: UiLocale, zh: string, en: string) => locale === "zh" ? zh : en;
const PROFILE_CHECK_COMMAND = "cosmatter check-dsh-profile";

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
  onRefresh?: () => void;
  onRefreshProfile?: () => void;
}) {
  const x = (zh: string, en: string) => t(props.locale, zh, en);
  const permitted = createMemo(() => props.authorization?.plugin_authorization_decisions.filter((item) => item.permitted) ?? []);
  const pluginById = createMemo(() => new Map((props.plugins ?? []).map((plugin) => [plugin.plugin_id, plugin])));
  const externalCount = createMemo(() => (props.plugins ?? []).filter((plugin) => plugin.automation_class === "external_authorized").length);
  const humanGateCount = createMemo(() => (props.plugins ?? []).filter((plugin) => plugin.requires_human_review || plugin.automation_class === "human_gate").length);
  const runtime = createMemo(() => harnessRuntimeSummary(props.operationalTelemetry));
  const [copyFeedback, setCopyFeedback] = createSignal<"copied" | "manual" | null>(null);
  const copyCheckCommand = async () => {
    try {
      await navigator.clipboard.writeText(PROFILE_CHECK_COMMAND);
      setCopyFeedback("copied");
    } catch {
      setCopyFeedback("manual");
    }
  };
  const composition = () => props.profile?.composition_check;
  const compositionLabel = createMemo(() => {
    const check = composition();
    if (!check) return { tone: "neutral" as const, text: x("配置组合与启动未核验", "Composition and startup unverified") };
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
  const activation = createMemo(() => {
    if (props.profileHealth === "loading" || props.health === "loading") return {
      state: "checking",
      title: x("正在核验 DSH 启用条件", "Checking DSH enablement conditions"),
      detail: x("正在读取本机安装状态和插件契约。", "Reading the local installation status and plugin contracts."),
    };
    const profileReady = props.profileHealth === "ready" && props.profile?.installation_state === "installed";
    const adapterReady = props.health === "ready";
    if (profileReady && adapterReady && compositionLabel().tone === "ready") return {
      state: "partial",
      title: x("最近一次配置组合完整，等待启动核验", "Last composition complete; startup unverified"),
      detail: x("上次核验包含全部七个插件。当前任务派发状态见运行回执。", "The last check included all seven bundles. See the runtime receipts for this mission."),
    };
    if (profileReady && adapterReady && compositionLabel().tone === "attention") return {
      state: "partial",
      title: compositionLabel().text,
      detail: x("可在终端重新核验 tui 配置组合。", "Recheck the TUI composition in the terminal."),
    };
    if (profileReady && adapterReady) return {
      state: "partial",
      title: x("安装与契约已就绪，profile 启动未核验", "Installation and contracts ready; profile startup unverified"),
      detail: x("已核对七个本机插件包与契约目录。任务派发结果见本次运行回执。", "All seven local bundles and the contract catalogue have been checked. See this mission’s receipts for dispatch results."),
    };
    const profile = props.profileHealth === "ready" ? props.profile : null;
    if (profile && profile.declared_bundle_count > profile.installed_bundle_count) return {
      state: "partial",
      title: x("部分依赖缺少有效安装", "Some dependencies have no valid installation"),
      detail: x("展开逐包检查结果，定位缺失或异常的插件包。", "Open the bundle checks to find missing or invalid installations."),
    };
    if (profileReady || adapterReady) return {
      state: "partial",
      title: x("DSH 仅部分启用", "DSH enablement is partial"),
      detail: profileReady
        ? x("包已安装，但契约目录尚未连接；不会开放派发。", "Bundles are installed, but the contract catalogue is disconnected; dispatch remains closed.")
        : x("契约目录可读，但 profile 安装尚未核验；不会把目录发现当作插件已装载。", "The catalogue is readable, but profile installation is not verified; catalogue discovery is not treated as plugin loading."),
    };
    return {
      state: "disconnected",
      title: x("DSH 插件桥未启用", "DSH plugin bridge not enabled"),
      detail: x("当前只显示安全关闭状态；不会读取配置、凭据或隐式启动 profile。", "Only a safely closed state is shown; configuration, credentials, and profile startup remain untouched."),
    };
  });
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
        <small>01 / INSTALL</small>
        <strong>{profileBadge().copy}</strong>
      </div>
      <i aria-hidden="true">≠</i>
      <div classList={{ ready: compositionLabel().tone === "ready", attention: compositionLabel().tone === "attention" }}>
        <small>02 / COMPOSE</small>
        <strong>{compositionLabel().text}</strong>
      </div>
      <i aria-hidden="true">≠</i>
      <div classList={{ ready: props.health === "ready", attention: props.health === "unavailable" }}>
        <small>03 / CONTRACT</small>
        <strong>{props.health === "ready" ? x("契约目录已连接", "Contract catalogue connected") : props.health === "loading" ? x("正在连接目录", "Connecting catalogue") : x("目录未连接", "Catalogue disconnected")}</strong>
      </div>
      <i aria-hidden="true">≠</i>
      <div classList={{ ready: runtime().state === "completed", attention: runtime().state === "unknown" || runtime().state === "incomplete", active: Boolean(props.operationPending) }}>
        <small>04 / RUNTIME</small>
        <strong>{props.operationPending
          ? x("受控操作进行中", "Controlled operation active")
          : runtime().dispatchCount ? x(`${runtime().completedCount}/${runtime().dispatchCount} 派发完成`, `${runtime().completedCount}/${runtime().dispatchCount} dispatches complete`)
            : x("尚无执行回执", "No execution receipt")}</strong>
      </div>
    </section>
    <section class={`harness-activation-verdict state-${activation().state}`} aria-label={x("DSH 启用结论", "DSH enablement verdict")}>
      <i aria-hidden="true" />
      <div><small>{x("启用结论", "ENABLEMENT VERDICT")}</small><strong>{activation().title}</strong></div>
      <p>{activation().detail}</p>
    </section>
    <Show when={props.health === "ready"} fallback={<div class="harness-catalogue-message"><p>{props.health === "loading"
      ? x("正在读取固定的本机能力契约；这不会加载插件、调用工具或授予执行权限。", "Reading the fixed local capability contracts. This does not load a plugin, call a tool, or grant execution permission.")
      : props.health === "unavailable"
        ? x("未能验证本机插件目录，因此本页不显示任何可用能力。任务工件与门禁保持不变。", "The local plugin catalogue could not be verified, so no capability is shown as available. Mission artifacts and gates remain unchanged.")
        : x("只读预览或未启用本地 API 时，插件桥保持断开。", "The plugin bridge stays disconnected in read-only preview or when the local API is disabled.")}</p><Show when={props.health === "unavailable" && props.onRefresh}><ActionButton size="sm" variant="secondary" onClick={() => props.onRefresh?.()}>{x("重试目录连接", "Retry catalogue connection")}</ActionButton></Show></div>}>
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
            <Show when={props.profileHealth !== "disabled" && props.onRefreshProfile}>
              <ActionButton size="sm" busy={props.profileHealth === "loading"} busyLabel={x("正在检查…", "Checking…")} onClick={() => props.onRefreshProfile?.()}>
                {x("重新检查 profile", "Recheck profile")}
              </ActionButton>
            </Show>
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
          <section class="harness-composition-card" aria-label={x("配置组合核验", "Profile composition check")}>
            <div>
              <small>{x("配置组合核验", "PROFILE COMPOSITION CHECK")}</small>
              <strong>{x("终端检查 DSH · tui", "Terminal check · DSH tui")}</strong>
            </div>
            <StatusBadge tone={compositionLabel().tone}>{compositionLabel().text}</StatusBadge>
            <p>{x("在 CosMatter 环境运行命令，再点「重新检查 profile」查看结果。", "Run the command in the CosMatter environment, then select Recheck profile to see the result.")}</p>
            <Show when={composition()}>{(check) => <p class="harness-composition-result">
              <time dateTime={check().checked_at}>{new Intl.DateTimeFormat(props.locale === "zh" ? "zh-CN" : "en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(check().checked_at))}</time>
              <span>DSH {check().dsh_version}</span>
              <span>{x("启动未核验", "Startup unverified")}</span>
            </p>}</Show>
            <div class="harness-installation-footer harness-copy-row">
              <code>{PROFILE_CHECK_COMMAND}</code>
              <ActionButton size="sm" onClick={() => void copyCheckCommand()}>{x("复制核验命令", "Copy check command")}</ActionButton>
            </div>
            <Show when={copyFeedback()}>{(feedback) => <p role="status">{feedback() === "copied"
              ? x("已复制。", "Copied.")
              : x("剪贴板不可用，请选中命令手动复制。", "Clipboard unavailable. Select the command and copy it manually.")}</p>}</Show>
          </section>
        </Show>
    </div>
    <Show when={props.profile?.installation_state !== "unavailable" && props.profile}>{(profile) =>
      <details class="harness-package-proof" aria-busy={props.profileHealth === "loading" || undefined}>
        <summary>
          <span>{x("查看逐包检查结果", "Inspect bundle checks")}</span>
          <strong>{profile().installed_bundle_count}/{profile().expected_bundle_count}</strong>
        </summary>
        <ul>
          <For each={profile().packages}>{(packageStatus) => {
            const role = () => BUNDLE_ROLES[packageStatus.package] ?? [packageStatus.package, packageStatus.package] as const;
            return <li classList={{ installed: packageStatus.install_status === "verified" }}>
              <i aria-hidden="true" />
              <div>
                <strong>{props.locale === "zh" ? role()[0] : role()[1]}</strong>
                <code>{packageStatus.package}</code>
              </div>
              <span class="harness-package-state"><b>{installStatusLabel(props.locale, packageStatus.install_status)}</b>
                <Show when={packageStatus.dependency_kind !== "absent"}><small>{dependencyKindLabel(props.locale, packageStatus.dependency_kind)}</small></Show>
              </span>
            </li>;
          }}</For>
        </ul>
        <p>{x(
          "此处检查安装文件。配置组合、profile 启动和派发由各自的检查确认。",
          "These checks cover installed files. Profile composition, startup, and dispatch have separate checks.",
        )}</p>
      </details>
    }</Show>
    <div class="harness-boundary-copy"><p>{props.health === "ready"
      ? x("目录已连接只证明 CosMatter 能读取本机静态契约；profile 依赖快照与运行回执分别证明不同层次，任何一层都不能代替工具结果。", "A connected catalogue proves only that CosMatter can read local static contracts. The profile dependency snapshot and runtime receipts prove separate layers; none can substitute for tool results.")
      : x("目录、profile 依赖快照与运行回执独立检查；其中一项不可用时，其余状态仍会如实显示，但不会据此开放执行权限。", "Catalogue, profile dependency snapshot, and runtime receipts are checked independently. When one is unavailable, the others remain visible without granting execution permission.")}</p><Show when={props.operationPending}><StatusBadge tone="active" pulse>{x("受控操作进行中", "Controlled operation in progress")}</StatusBadge></Show></div>
    <Show when={props.health === "ready" && permitted().length > 0}><div class="harness-permission-list"><small>{x("本任务授权判定", "MISSION AUTHORIZATION DECISIONS")}</small><div><For each={permitted()}>{(decision) => <span><i aria-hidden="true" /><strong>{pluginById().get(decision.plugin_id)?.title ?? decision.plugin_id}</strong><code>{decision.plugin_id}</code></span>}</For></div></div></Show>
  </section>;
}
