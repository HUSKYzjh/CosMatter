export interface StatusRecoveryState<Recovery> {
  message: string;
  recovery: Recovery | null;
}

/** A normal status observation supersedes any earlier recovery instruction. */
export function ordinaryStatus<Recovery>(message: string): StatusRecoveryState<Recovery> {
  return { message, recovery: null };
}

/** Unknown write outcomes retain their paired, review-only recovery route. */
export function recoverableStatus<Recovery>(message: string, recovery: Recovery): StatusRecoveryState<Recovery> {
  return { message, recovery };
}
