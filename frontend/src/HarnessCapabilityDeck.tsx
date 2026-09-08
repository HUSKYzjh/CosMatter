import { For, Show, createMemo } from "solid-js";

import type { DshProfileHealth, DshProfileStatus, HarnessAuthorization, HarnessCatalogueHealth, HarnessPluginDescriptor, OperationalTelemetry } from "./localApi";
import { ActionButton, StatusBadge } from "./uiPrimitives";
import type { UiLocale } from "./fleetRegistry";
import { harnessRuntimeSummary } from "./harnessRuntimeSummary";

const t = (locale: UiLocale, zh: string, en: string) => locale === "zh" ? zh : en;

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
        <section>
          <div><small>{x("DSH PROFILE / 依赖快照", "DSH PROFILE / DEPENDENCY SNAPSHOT")}</small><strong>{props.profile?.profile_name ?? "tui"}</strong></div>
          <StatusBadge tone={props.profile?.installation_state === "installed" ? "ready" : props.profileHealth === "unavailable" || props.profile?.installation_state === "partial" ? "attention" : "neutral"} pulse={props.profileHealth === "loading"}>{props.profileHealth === "loading"
            ? x("检查中", "Checking")
            : props.profileHealth === "disabled" ? x("只读预览未检查", "Not checked in preview")
            : props.profileHealth === "unavailable" ? x("状态不可用", "Status unavailable")
              : props.profile?.installation_state === "installed" ? x(`依赖已安装 ${props.profile.installed_bundle_count}/${props.profile.expected_bundle_count}`, `Dependencies installed ${props.profile.installed_bundle_count}/${props.profile.expected_bundle_count}`)
                : props.profile?.installation_state === "partial" ? x(`部分安装 ${props.profile.installed_bundle_count}/${props.profile.expected_bundle_count}`, `Partially installed ${props.profile.installed_bundle_count}/${props.profile.expected_bundle_count}`)
                  : x("未安装", "Not installed")}</StatusBadge>
          <p>{props.profileHealth === "disabled"
            ? x("只读预览不会读取本机 DSH profile；进入真实本地任务后才显示脱敏依赖快照。", "Read-only preview does not inspect the local DSH profile. A redacted dependency snapshot appears only in a live local mission.")
            : x("该状态只来自固定 tui profile 的脱敏依赖名称；HTTP API 不启动 profile，也不读取插件配置或凭据。", "This status comes only from redacted dependency names in the fixed TUI profile. The HTTP API neither boots the profile nor reads plugin configuration or credentials.")}</p>
          <Show when={props.profileHealth !== "disabled" && props.profileHealth !== "loading" && (props.profileHealth === "unavailable" || props.profile?.installation_state !== "installed") && props.onRefreshProfile}><ActionButton size="sm" variant="secondary" onClick={() => props.onRefreshProfile?.()}>{x("重新检查 profile", "Recheck profile")}</ActionButton></Show>
        </section>
        <section>
          <div><small>{x("运行回执 / 当前任务", "RUNTIME RECEIPTS / CURRENT MISSION")}</small><strong>{runtime().dispatchCount ? `${runtime().completedCount}/${runtime().dispatchCount}` : "—"}</strong></div>
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
    </div>
    <Show when={props.profileHealth === "ready" && props.profile}>{(profile) =>
      <details class="harness-package-proof">
        <summary>
          <span>{x("查看逐包依赖证明", "Inspect bundle dependency proof")}</span>
          <strong>{profile().installed_bundle_count}/{profile().expected_bundle_count}</strong>
        </summary>
        <ul>
          <For each={profile().packages}>{(packageStatus) => {
            const role = () => BUNDLE_ROLES[packageStatus.package] ?? [packageStatus.package, packageStatus.package] as const;
            return <li classList={{ installed: packageStatus.installed }}>
              <i aria-hidden="true" />
              <div>
                <strong>{props.locale === "zh" ? role()[0] : role()[1]}</strong>
                <code>{packageStatus.package}</code>
              </div>
              <span>{dependencyKindLabel(props.locale, packageStatus.dependency_kind)}</span>
            </li>;
          }}</For>
        </ul>
        <p>{x(
          "清单只显示固定包名、职责与依赖类型；不返回依赖值、本机路径、配置或凭据。",
          "The list exposes only fixed package names, roles, and dependency kinds. It never returns dependency values, local paths, configuration, or credentials.",
        )}</p>
      </details>
    }</Show>
    <div class="harness-boundary-copy"><p>{props.health === "ready"
      ? x("目录已连接只证明 CosMatter 能读取本机静态契约；profile 依赖快照与运行回执分别证明不同层次，任何一层都不能代替工具结果。", "A connected catalogue proves only that CosMatter can read local static contracts. The profile dependency snapshot and runtime receipts prove separate layers; none can substitute for tool results.")
      : x("目录、profile 依赖快照与运行回执独立检查；其中一项不可用时，其余状态仍会如实显示，但不会据此开放执行权限。", "Catalogue, profile dependency snapshot, and runtime receipts are checked independently. When one is unavailable, the others remain visible without granting execution permission.")}</p><Show when={props.operationPending}><StatusBadge tone="active" pulse>{x("受控操作进行中", "Controlled operation in progress")}</StatusBadge></Show></div>
    <Show when={props.health === "ready" && permitted().length > 0}><div class="harness-permission-list"><small>{x("本任务授权判定", "MISSION AUTHORIZATION DECISIONS")}</small><div><For each={permitted()}>{(decision) => <span><i aria-hidden="true" /><strong>{pluginById().get(decision.plugin_id)?.title ?? decision.plugin_id}</strong><code>{decision.plugin_id}</code></span>}</For></div></div></Show>
  </section>;
}
