# Evidence provenance audit

Run after evidence review and source-map recording:

```powershell
python -m cosmatter audit-evidence-provenance --run-id bfo_live_001
```

The command writes `evidence_provenance_audit.json`. For each accepted
EvidenceCard it records only ID, document ID, locator, and provenance status.
If a reviewed source map exists for that document, the card quote hash and
locator must match a selected segment exactly. A document without a source map
is labelled `manual_locator_only_requires_source_review`; it is never treated
as a parser-verified quotation.

The audit does not prove publisher authenticity or scientific correctness. It
is an integrity check over locally reviewed provenance artifacts.
