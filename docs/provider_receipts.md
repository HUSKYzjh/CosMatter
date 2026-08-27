# External retrieval receipts

Every successful Sciverse `agentic_search` made through the CLI or loopback
workbench now appends a record to `provider_receipts.jsonl` in the run folder.
Each record includes the provider, operation, upstream request ID, HTTP status,
candidate count, requested `top_k`, timestamp, and SHA-256 digest of the query.

It intentionally excludes the raw query, authorization header, credentials,
request body, raw response, abstract, and full text. The related flight event
stores the receipt ID rather than the query. A receipt proves that a bounded
provider call occurred; it does not make a candidate a verified evidence claim.

## Candidate-origin link audit

After one or more retrieval calls, run:

```powershell
python -m cosmatter audit-candidate-receipts --run-id bfo_live_001
```

The audit writes `candidate_receipt_audit.json`. It verifies that every
provider-linked origin preserved in `retrieval_candidates.json` refers to an
existing receipt with matching provider, operation, and query digest. The
artifact contains only counts and a coverage flag; it does not copy query
strings, candidate titles, provider payloads, abstracts, or full text.

## Screened full-text context

`sciverse-read-context` is deliberately not a corpus-ingestion command. It
requires a candidate that has passed the human full-text screening gate and
then reads one 200--4,000-character Sciverse context window. The raw context
is written only to a new `.txt` or `.md` path supplied by the reviewer outside
the run directory; it is never written to run artifacts, events, or receipts.

```powershell
python -m cosmatter sciverse-read-context --run-id bfo_live_001 --document-id <screened-doc-id> --offset 0 --limit 2000 --output D:\review\screened_context.txt
```

The run records a hash-only `content` receipt: document-ID digest, requested
window, content digest, character count, continuation metadata, provider
request ID, status, and timestamp. This proves the bounded retrieval without
retaining copyrighted context or passing it directly to a report-generation
step. A reviewer must choose and map any usable excerpt into the existing
source-map/evidence-review workflow.

## MinerU source-parse task receipts

mineru-submit-url and mineru-poll now append a hash-only receipt for each
authorized parser operation. A MinerU receipt retains the document-ID digest,
source-URL digest, task-ID digest, task state, configured model label, upstream
request ID, HTTP status, and timestamp. It never retains the source URL, task
ID, parser result URL, parsed document body, or selected source-map quote.

Use the following read-only audit after one or more submit/poll operations:

    python -m cosmatter audit-source-parse-receipts --run-id bfo_live_001

The audit writes source_parse_receipt_audit.json and reports linked, unlinked,
and stale task-state counts. It proves only that the local parse-task ledger and
recorded MinerU calls agree; it does not assess parser quality, copyright
permissions, or scientific evidence validity.
