# Bundle T1 evidence — 14 October 2026

> Edited extract, 17 October 2026: external application references were removed.
> Retained RK results keep their original scope; this is not an unchanged capture.

This development checkpoint is retained on `codex/core-lifecycle-bundles`, based on develop
`3d70ece757a2ce7ff6a329b7b3cfcb6ef0835363`. It is in the isolated checkout
`[external application omitted]/.worktrees/rk-core-lifecycle`. The preserved walkthrough is included in the base. This record captures the
candidate before consolidation into the newer develop branch. Integration does
not approve Bundle release or adoption in Projects.

## Observed verification

- Full RK suite: **858 passed**, Python 3.13.11, `python -m pytest -q src/tests`.
  A pre-existing naive-sum comparison needed an explicit left fold because
  Python 3.13's built-in sum uses compensation; the intended accuracy test remains.
- Nine schema/generation checks passed: Python and C# generation, validation,
  native roundtrip, expressions, formulations, Models, Specifications and Runs.
  See [captured checks](schema-checks.json).
- C# build passed with zero warnings/errors. The .NET 8 test target ran on the
  installed .NET 10.0.12 runtime using explicit `DOTNET_ROLL_FORWARD=Major`.
  Python–C#–Python preserves rich content, presence, references and Geometry.
  This does not establish execution on an installed .NET 8 runtime or Rhino host.
- Three complete canonical YAML Models reconstruct from schema-derived Parquet;
  Model-only migration, invalid paths/formats, bounds and collection identity pass.
  Core's paired tests add native inventory/decoder/selector checks, explicit source
  evidence, reverse mapping and failure-before-publication checks.

The library wheel was built from this isolated source and pinned by SHA-256 in
Core's vendor manifest/lock. The [canonical contract](../../reference/bundle.md)
is authoritative here. Core owns its exact native profile, synthetic proof
artifacts, local registration tests and measured record-query results.

## Gate boundary

This is a concrete format candidate, not a declaration that every P1–P5 case or
PA0 envelope is accepted. Broad native primitives/assets, all source/provenance
cases, exhaustive scalar/presence permutations, query projections, scale bounds
and P7/P8 rendering/host evidence remain open. No project data, existing notebook,
Rhino host, remote service or stable public format was migrated or accepted.

## Checkpoint verification

Before the recovery commit, the full library suite passed again: 858 tests in
90.76 seconds on Python 3.13.11. The pinned mypy 1.18.2 check found one migration
typing error. The fix uses the public Metadata export to construct the new
metadata mapping. The six Bundle/migration tests then passed. All 145 selected
source files pass typing, and all deliberate rejection fixtures retain their
expected errors. The 16 shared native fixture round trips pass.

`tools/schema/verify_install.py` passed from a fresh build with the runtime,
financial, execution and table interpreter options. This checks minimal imports,
JSON/YAML and stores, real process-isolated forward/inverse solves, PyXIRR and
Polars without pandas. The local documentation check and `git diff --check` pass.
Generated artifacts retain the preceding nine-check evidence above. Black was
applied only to the changed handwritten files.

These checks used local macOS environments. Missing mypy and pip initially
prevented their checks from running; both tools were installed before the passing
runs. No remote harness, Windows, Rhino or Projects acceptance is claimed. The
subsequent consolidation record must identify the merged revision and the exact
wheel used for combined and notebook validation.

## Combined draft validation

The draft branch merged develop through `6837b9a` after the candidate merge
`3b59671`. The walkthrough lock now selects local RK `0.10.0.dev1`. Fresh kernels
used Python 3.12.12 and the clean candidate wheel built from `3b59671`, SHA-256
`534ca425f25cbeb5e6c2c6530b94516091e1811aada0d788939153c9cfe03467`.

All 81 code cells passed: 26 in `basic_dcf`, 28 in `design_to_value`, and 27 in
`development_feasibility`. The independent Notebook 03 audit passed and retained
its prior numerical results. Three walkthrough helper tests passed. Jupyter Book
2.1.7 built the introduction and three chapters with `--strict`. Browser review
confirmed local navigation, cash-flow tables, rendered source geometry and object
selection, and the development cash-flow chart. No browser console errors were
observed in those checks. This does not establish every chart interaction or host.

Authored notebooks and shared source data were not changed. Executed copies,
the financial audit, wheel, source archive and local HTML are retained under
`[external identifier omitted]/.runtime/rk-consolidation-20261014/`. This ignored evidence must be
backed up separately from Git. The local preview does not publish the book.
Its repository edit links and other public publication details remain deferred.

The combined check also found the historical SQLite experiment reading the new
live slot schema. Its internal path column collided with GeometryFile.path.
Commit `6837b9a` pins the experiment to its exact original Model 0.7 slot metadata
and rejects newer Models before writing. All 27 SQLite checks pass, and a prior
retained database reopens with network and original source access blocked.
The library's 858 tests and the installed-wheel slices also pass.
