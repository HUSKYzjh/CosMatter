import { createSignal } from "solid-js";

export type DshTerminal = "path" | "windows-venv" | "posix-venv";
export type RepositoryTerminal = Exclude<DshTerminal, "path">;
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

// Directory choices are private to the open page and are never requested from the server.
const [roots, setRoots] = createSignal<Record<RepositoryTerminal, string>>({ "windows-venv": "", "posix-venv": "" });
export const repositoryDirectory = (mode: RepositoryTerminal) => roots()[mode];

export function applyRepositoryDirectory(mode: RepositoryTerminal, value: string): boolean {
  if (/[\x00-\x1f\x7f]/u.test(value)) return false;
  let path = value.trim() ? value.replace(/^(["'])(.*)\1$/u, "$2") : "";
  if (path && mode === "windows-venv") {
    path = path.replaceAll("/", "\\");
    if (!/^(?:[A-Za-z]:\\|\\\\[^\\]+\\[^\\]+)/u.test(path) || /[<>"|?*:]/u.test(path.replace(/^[A-Za-z]:/, ""))) return false;
  } else if (path && !path.startsWith("/")) return false;
  setRoots(previous => ({ ...previous, [mode]: path }));
  return true;
}

export function chooseDshTerminal(value: DshTerminal) {
  setTerminal(value);
  try { window.sessionStorage.setItem(storageKey, value); } catch { /* Keep the in-memory selection. */ }
}

export function formatDshCommand(command: string): string {
  if (!command.startsWith("cosmatter ")) return command;
  const mode = terminal();
  if (mode === "path") return command;
  const root = repositoryDirectory(mode);
  let executable: string;
  if (mode === "windows-venv") {
    // PowerShell treats typographic apostrophes as single-quote delimiters too.
    const quotedRoot = root.replace(/\\+$/, "").replace(/['\u2018-\u201b]/gu, quote => quote + quote);
    executable = root ? "& '" + quotedRoot + "\\.venv\\Scripts\\cosmatter.exe'" : ".\\.venv\\Scripts\\cosmatter.exe";
  } else {
    const quotedRoot = root.replace(/\/+$/, "").replaceAll("'", "'\\''");
    executable = root ? "'" + quotedRoot + "/.venv/bin/cosmatter'" : "./.venv/bin/cosmatter";
  }
  return executable + command.slice("cosmatter".length);
}
