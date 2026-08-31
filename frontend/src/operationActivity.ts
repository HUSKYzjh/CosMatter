export type OperationActivity = { id: number; label: string; detail: string };

/** Keeps the newest visible local operation until that exact operation ends. */
export function createOperationActivity() {
  let sequence = 0;
  let active: OperationActivity | null = null;
  return {
    start(label: string, detail: string) {
      active = { id: ++sequence, label, detail };
      return active;
    },
    finish(id: number) {
      if (active?.id === id) active = null;
      return active;
    },
    current() { return active; },
  };
}
