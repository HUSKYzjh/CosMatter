# Contributing to CosMatter

CosMatter accepts contributions that improve reproducibility, evidence traceability, and safe materials-literature workflows.

Before opening a change:

1. Do not commit `.env` files, API credentials, institutional PDFs, full MinerU Markdown, private paths, or provider response payloads.
2. Keep scientific assertions separated from untrusted model suggestions. An `EvidenceCard` must retain a source locator and human-review state.
3. Add or update a regression test for behavior changes, then run the Python and frontend checks documented in `docs/competition_submission_2026_08.zh-CN.md`.
4. Record third-party datasets, APIs, models, parsers, and software in a disclosure artifact; do not infer licenses or redistribution rights.

The repository is MIT-licensed, but that license does not grant rights to redistribute third-party scholarly content or external API outputs.
