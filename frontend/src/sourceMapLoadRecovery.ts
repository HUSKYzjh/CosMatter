/**
 * A recorded Source Map is read once automatically for a private PDF task.
 * On failure the component must wait for an explicit human retry rather than
 * retrying in a render loop or exposing downstream review forms.
 */
export function shouldAutoLoadRecordedSourceMap(input: {
  taskKey: string | null;
  hasLoader: boolean;
  ready: boolean;
  sourceMapRecorded: boolean;
  hasRecordedSegments: boolean;
  loading: boolean;
  attemptedFor: string | null;
}): boolean {
  return Boolean(
    input.taskKey
    && input.hasLoader
    && input.ready
    && input.sourceMapRecorded
    && !input.hasRecordedSegments
    && !input.loading
    && input.attemptedFor !== input.taskKey,
  );
}
