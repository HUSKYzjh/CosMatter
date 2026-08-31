/**
 * Prevents one user-initiated async submission from being sent twice while
 * the first request is still reading a local file or waiting on loopback.
 */
export function createExclusiveSubmissionGate() {
  let active = false;
  return {
    tryStart() {
      if (active) return false;
      active = true;
      return true;
    },
    finish() { active = false; },
  };
}
