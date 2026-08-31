# CosMatter research plugin for DeepSeek Harness

This independent DSH bundle exposes three loopback-only tools:

- `cosmatter_research_plan_draft` sends the bounded Mission Brief to DeepSeek only after the exact explicit authorizations `mission_scoped_egress_consent` and `deepseek_request_consent` are supplied. Its output remains `untrusted_draft`.
- `cosmatter_research_plan_approve` records a separately reviewed, bounded FlightPlan. It never consumes the model draft implicitly.
- `cosmatter_research_query_execute` sends only a selected approved query to Sciverse, OpenAlex, and/or Crossref after the exact explicit authorizations `mission_scoped_egress_consent` and `metadata_provider_consent` are supplied. It returns metadata candidates only.

The bundle hard-codes neither credentials nor provider URLs. It only connects to a bare `http://127.0.0.1:<port>` CosMatter backend. It cannot download full text, invoke MinerU, record candidate screening, accept evidence, launch a shell, or access the filesystem.
