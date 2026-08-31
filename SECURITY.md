# Security Policy

Keep provider credentials only in a local `.env` file or managed secret store; `.env.example` is the public template. Never commit or report API keys, session cookies, authorization headers, institutional credentials, restricted full text, private source maps, or raw provider responses.

CosMatter's public projections and submission artifacts are designed to carry status, counts, identifiers and redacted audit metadata only. They are not a safe place for PDF files, parsed Markdown, prompts, local paths or private run logs. The full data classification and release boundary is in [docs/data-governance.md](docs/data-governance.md).

Before opening an issue or pull request, inspect every attachment and generated artifact. If a secret may have been exposed, stop sharing it, revoke or rotate the affected credential, remove the exposed copy where possible, and report the incident privately to the maintainers. Do not post the secret itself in the report.
