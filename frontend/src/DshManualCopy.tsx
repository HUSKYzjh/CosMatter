import { createEffect, createSignal, createUniqueId, onCleanup, onMount } from "solid-js";
import type { UiLocale } from "./fleetRegistry";

type CopyAttempt<T> = {
  target: T;
  value: string;
  readValue: () => string | null;
  source: HTMLButtonElement;
  copied?: boolean;
};

export function createDshClipboard<T>(successDuration?: number) {
  const [attempt, setAttempt] = createSignal<CopyAttempt<T> | null>(null);
  let reset: ReturnType<typeof setTimeout> | undefined;
  createEffect(() => {
    const state = attempt();
    if (state && state.readValue() !== state.value) setAttempt(null);
  });
  onCleanup(() => { clearTimeout(reset); setAttempt(null); });

  async function copy(target: T, readValue: () => string | null, source: HTMLButtonElement) {
    const value = readValue();
    if (!value) return;
    clearTimeout(reset);
    const pending = { target, value, readValue, source };
    setAttempt(pending);
    let copied = false;
    try {
      await navigator.clipboard.writeText(value);
      copied = true;
    } catch {
      // The browser may still allow its native keyboard or text-selection copy action.
    }
    if (attempt() !== pending || readValue() !== value || !source.isConnected) return;
    setAttempt({ ...pending, copied });
    if (copied && successDuration) reset = setTimeout(() => setAttempt(null), successDuration);
    return copied;
  }
  const feedback = () => {
    const state = attempt();
    return state?.copied !== undefined ? state : null;
  };
  return { copy, feedback };
}

export function DshManualCopy(props: { locale: UiLocale; label: string; value: string; source: HTMLButtonElement }) {
  const hint = createUniqueId();
  let field!: HTMLTextAreaElement;
  onMount(() => {
    if (document.hasFocus() && document.activeElement === props.source) field.focus();
  });
  return <div class="dsh-manual-copy">
    <p id={hint} role="status">{props.locale === "zh"
      ? "剪贴板不可用。可在下方用 Ctrl+C 或 ⌘C 手动复制。"
      : "Clipboard unavailable. Use Ctrl+C or ⌘C to copy the text below."}</p>
    <textarea ref={field} aria-label={props.label} aria-describedby={hint} rows={2} readOnly spellcheck={false}
      value={props.value} onFocus={(event) => event.currentTarget.select()} />
  </div>;
}
