import { Show, splitProps, type JSX } from "solid-js";

export type ActionButtonVariant = "primary" | "secondary" | "quiet" | "danger";
export type ActionButtonSize = "sm" | "md" | "lg" | "icon";

export function actionButtonClass(variant: ActionButtonVariant, size: ActionButtonSize, extra?: string): string {
  return ["cm-action", `cm-action--${variant}`, `cm-action--${size}`, extra].filter(Boolean).join(" ");
}

export interface ActionButtonProps extends JSX.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ActionButtonVariant;
  size?: ActionButtonSize;
  busy?: boolean;
  busyLabel?: JSX.Element;
}

/** Shared action primitive: one focus, disabled and progress language across the workbench. */
export function ActionButton(props: ActionButtonProps) {
  const [local, rest] = splitProps(props, ["variant", "size", "busy", "busyLabel", "class", "children", "disabled", "type"]);
  return <button
    {...rest}
    type={local.type ?? "button"}
    class={actionButtonClass(local.variant ?? "secondary", local.size ?? "md", local.class)}
    disabled={Boolean(local.disabled || local.busy)}
    aria-busy={local.busy ? "true" : undefined}
  >
    <Show when={local.busy}><span class="cm-action__spinner" aria-hidden="true" /></Show>
    <span>{local.busy && local.busyLabel ? local.busyLabel : local.children}</span>
  </button>;
}

export interface ActionLinkProps extends JSX.AnchorHTMLAttributes<HTMLAnchorElement> {
  variant?: Exclude<ActionButtonVariant, "danger">;
  size?: ActionButtonSize;
}

/** Link counterpart to ActionButton: shared hierarchy without changing navigation semantics. */
export function ActionLink(props: ActionLinkProps) {
  const [local, rest] = splitProps(props, ["variant", "size", "class", "children"]);
  return <a
    {...rest}
    class={actionButtonClass(local.variant ?? "secondary", local.size ?? "md", local.class)}
  >
    <span>{local.children}</span>
  </a>;
}

export type StatusBadgeTone = "ready" | "active" | "attention" | "neutral";

export function StatusBadge(props: { tone: StatusBadgeTone; children: JSX.Element; pulse?: boolean }) {
  return <span class={`cm-status-badge cm-status-badge--${props.tone}`}><i classList={{ pulse: props.pulse }} aria-hidden="true" />{props.children}</span>;
}
