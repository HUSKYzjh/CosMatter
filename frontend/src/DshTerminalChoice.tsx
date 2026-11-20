import { Show, createSignal, createUniqueId } from "solid-js";
import { applyRepositoryDirectory, chooseDshTerminal, dshTerminal, repositoryDirectory, type DshTerminal, type RepositoryTerminal } from "./dshTerminalCommand";
import type { UiLocale } from "./fleetRegistry";
import { ActionButton } from "./uiPrimitives";

export function DshTerminalChoice(props: { locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const repositoryMode = () => {
    const mode = dshTerminal();
    return mode === "path" ? null : mode;
  };
  return <div class="dsh-command-environment">
    <label class="dsh-terminal-choice">
      <span>{x("命令运行环境", "Command environment")}</span>
      <select value={dshTerminal()} onChange={event => chooseDshTerminal(event.currentTarget.value as DshTerminal)}>
        <option value="path">{x("已激活环境或全局安装", "Activated environment or global install")}</option>
        <option value="windows-venv">{x("Windows · PowerShell · .venv", "Windows · PowerShell · .venv")}</option>
        <option value="posix-venv">macOS / Linux · .venv</option>
      </select>
    </label>
    <Show when={repositoryMode()} keyed>{mode => <RepositoryLocation mode={mode} locale={props.locale} />}</Show>
  </div>;
}

function RepositoryLocation(props: { mode: RepositoryTerminal; locale: UiLocale }) {
  const x = (zh: string, en: string) => props.locale === "zh" ? zh : en;
  const current = () => repositoryDirectory(props.mode);
  const [value, edit] = createSignal(current());
  const [invalid, setInvalid] = createSignal(false);
  const hintId = createUniqueId();
  let field!: HTMLInputElement;
  return <details class="harness-disclosure dsh-repository-location">
    <summary>{current() ? x("已指定仓库目录", "Repository directory set") : x("从其他目录运行", "Run from another directory")}</summary>
    <form onSubmit={event => {
      event.preventDefault();
      if (!applyRepositoryDirectory(props.mode, value())) {
        setInvalid(true);
        field.focus();
        return;
      }
      edit(current());
      setInvalid(false);
    }}>
      <label>{x("CosMatter 仓库目录", "CosMatter repository directory")}
        <input ref={field} value={value()} onInput={event => { edit(event.currentTarget.value); setInvalid(false); }}
          placeholder={props.mode === "windows-venv" ? "D:\\Projects\\CosMatter" : "/home/user/CosMatter"}
          aria-invalid={invalid()} aria-describedby={hintId} spellcheck={false} autocomplete="off" />
      </label>
      <ActionButton size="sm" type="submit">{x("应用目录", "Apply directory")}</ActionButton>
      <p id={hintId} role="status">{invalid()
        ? x("请输入该系统的绝对目录。", "Enter an absolute directory for this operating system.")
        : value() !== current() ? x("应用后将更新本页的终端命令。", "Apply to update the terminal commands on this page.")
        : current() ? x("可在新终端的任意目录运行下列命令。", "Run the following commands from any directory in a new terminal.")
        : x("留空时，请在 CosMatter 仓库根目录运行命令。", "With this field empty, run the commands from the CosMatter repository root.")}</p>
    </form>
  </details>;
}
