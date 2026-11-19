export function DshCommandText(props: { command: string }) {
  return <code class="dsh-command-text">{props.command.split(/(\s+)/).map((part) =>
    part.startsWith("--") ? <span>{part}</span> : part
  )}</code>;
}
