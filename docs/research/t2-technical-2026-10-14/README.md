# T2 selective Bundle reads — 14 October 2026

> Edited extract, 17 October 2026: external application references were removed.
> Retained RK results keep their original scope; this is not an unchanged capture.

RK 0.10.0.dev3 adds exact record-path filtering and reads the record index directly
with parameterised DuckDB predicates and LIMIT/OFFSET. It permits only the verified
index file, disables other external access, and limits DuckDB to 128 MB/one thread.
Canonical schemas, Bundle identity, reconstruction and Parquet mapping are unchanged.
Cold opening still reconstructs/validates the retained documents.

The two Bundle suites passed **19 tests**, including a 1,000-Entity test that
forbids Arrow table reads after mounting, checks non-overlapping pages and exact
UUID/path filtering, and treats SQL-shaped text as inert data. The primary consumer verifies the
clean wheel against an exact source inventory. Current checkout remains `develop`
in the single Rangekeeper folder; no branch or worktree was created or removed.

The primary consumer's coordinated evidence (external link omitted)
owns query/process/cache/client measurements and consumer checks. That link names
the intended delivery path; this working-tree candidate is not yet committed or
published. T3 integration/recovery and stable release remain separate gates.
