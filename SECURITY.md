# Security Policy

Do not report or commit secrets. Keep provider keys only in a local `.env` file; use `.env.example` as the public template.

Before opening an issue or pull request, remove API keys, authorization headers, full restricted documents, and private run logs. The project records status and redacted audit metadata only.

For a suspected secret exposure, revoke the affected key first and report the issue privately to the maintainers rather than opening a public issue.
