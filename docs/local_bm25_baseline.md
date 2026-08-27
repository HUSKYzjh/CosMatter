# Local parsed-corpus BM25 baseline

`local-parsed-corpus-search` now uses deterministic, field-weighted BM25 over
the reviewed Markdown files named by a private one-run index. Title terms have
a fixed weight of 3, while document length normalization reduces the effect of
repeated terms in a long source.

The index path and Markdown text remain process-local. The persisted candidate
artifact contains bibliographic metadata and a score only; it never stores the
index path, raw Markdown, parsed PDF output, abstract, or full text. This is a
reproducible local baseline for the authorized corpus, not a claim of Sci-Base
coverage or a semantic-retrieval result.
