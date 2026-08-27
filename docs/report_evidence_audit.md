# Report evidence audit

Run the audit after `build-report` and before sharing a local report:

```powershell
python -m cosmatter audit-report-evidence --run-id bfo_live_001
```

The command writes `report_evidence_audit.json` only when the manifest contains
every and only accepted EvidenceCard ID, every current Research Gap candidate
is still bound to accepted evidence, and the local Markdown report contains its
declared evidence and Gap identifiers, and that every accepted EvidenceCard has
its corresponding document ID and source locator rendered in the report. When reviewed material facts or a
cross-document fusion artifact exist, it additionally checks that every fact
identifier and source locator is rendered, and that every comparison record
still lists its source-map fact observations. For every Research Gap candidate, it
also requires an executed counterevidence boundary (all approved queries
recorded) and verifies that both its boundary status and retrieval-history SHA-256
fingerprint are rendered in the report. The fingerprint records only normalized
query and candidate-document-ID structure; it does not expose private full text.

The audit is deliberately limited to artifact-level identifier integrity. It
does not establish scientific validity, assess free-form prose, validate an
LLM interpretation, or replace a human's source-locator review. Comparison
records remain condition-aware groupings, and Research Gap entries remain
review-required candidates rather than findings.
