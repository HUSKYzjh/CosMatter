/**
 * Lets an async consumer accept only its newest response.  This is separate
 * from run identity: the same run can have several overlapping status reads.
 */
export function createLatestRequestGate() {
  let version = 0;
  return {
    begin() {
      const requestVersion = ++version;
      return () => requestVersion === version;
    },
    invalidate() { version += 1; },
  };
}
