import { createSignal } from "solid-js";

export type DshTerminal = "path" | "windows-venv" | "posix-venv";
const storageKey = "cosmatter.dsh-terminal";

function savedTerminal(): DshTerminal {
  try {
    const saved = window.sessionStorage.getItem(storageKey);
    if (saved === "windows-venv" || saved === "posix-venv") return saved;
  } catch { /* Storage can be unavailable in a restricted browser. */ }
  return "path";
}

const [terminal, setTerminal] = createSignal<DshTerminal>(savedTerminal());
export { terminal as dshTerminal };

export function chooseDshTerminal(value: DshTerminal) {
  setTerminal(value);
  try { window.sessionStorage.setItem(storageKey, value); } catch { /* Keep the in-memory selection. */ }
}

export function formatDshCommand(command: string): string {
  if (!command.startsWith("cosmatter ")) return command;
  const executable = terminal() === "windows-venv" ? ".\\.venv\\Scripts\\cosmatter.exe"
    : terminal() === "posix-venv" ? "./.venv/bin/cosmatter" : "cosmatter";
  return executable + command.slice("cosmatter".length);
}
