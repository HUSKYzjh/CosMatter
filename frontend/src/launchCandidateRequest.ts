/** Guard an asynchronous candidate response against a newer question draft. */
export function isCurrentCandidateResponse(requestId: number, latestRequestId: number, requestedQuestion: string, currentQuestion: string): boolean {
  return requestId === latestRequestId && requestedQuestion.trim() === currentQuestion.trim();
}
