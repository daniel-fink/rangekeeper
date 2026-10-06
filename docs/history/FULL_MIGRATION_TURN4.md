# Turn 4 — Numerical retirement and dependency separation

> Historical design or implementation record. Names, commands and status below describe that checkpoint. Use the [current documentation](../README.md) for supported APIs.

**Legacy isolation, 2026-10-06:** held Python code is now in `rangekeeper.legacy`,
predecessor tests in `src/tests/legacy`, and excluded C# code in `grasshopper/legacy`.
Old public paths have no aliases. See [the boundary and current checks](../LEGACY_ISOLATION.md).
The Windows gate remains open; earlier Turn 4 results below describe the preceding wheel.

The permitted retirement slice is implemented and locally accepted. **Full legacy
retirement remains open** because the official Windows connector gate still holds
the old graph/Measure/Speckle API and excluded C# dependency group.

The accepted Turn 3 checkpoint was committed and pushed: RK `305f3ff` on
`acausal-modelling`, Projects `6146ad2` on `feature/mandarin-assembly-layout`.
The Turn 4 changes are a new, uncommitted working-tree change. No package release
or external publication occurred.

## What changed

- Removed 18 superseded numerical, temporal, policy and presentation Python files,
  their old root exports, `update_class`, and `rgba_from_cmap`. Removed the
  commented-only linear graph test model and 11 obsolete walkthrough cache files.
  [The exact inventory](../research/full-migration/turn4/removed-files.json) records
  their previous hashes. No compatibility aliases were added.
- Converted remaining numerical API tests into canonical assertions. Preserved
  18 account cases and three cycle paths as a synthetic, hashed reference fixture
  before deletion. Independent arithmetic checks remain alongside that fixture.
- Kept `model.duration`, public `duration/`, `model.flow`, `calculations`,
  `formulations`, `scenarios` and `policies` as the separated implementation.
  The canonical schemas and mathematical behaviour are unchanged.
- Fixed two remaining executable documentation examples to use canonical Evidence
  imports and the public `operation` export. Rebuilt the walkthrough site from
  fresh installed-wheel notebook outputs, without execution caches.
- Reduced base dependencies to JSON validation and Pint. Financial, numerical,
  dataframe, plotting, viewer, service and execution capabilities have explicit
  extras. A temporary `legacy` extra serves the held predecessor group.
  The source and both Projects locks were updated; reviewed project YAML was not changed.

## Dependency and API boundaries

```text
rangekeeper
  model / specification / run       generated immutable content + behaviour
  duration / units                  date and unit operations
  io                                explicit codecs and revision stores
  graph                             Model-backed queries/reductions/projections
  calculations                      known-data numerical algorithms
  formulations                      declarations only
  scenarios / policies              captured scenarios and finite decisions
  execution                         optional Pyomo/HiGHS investigations
  adapters / workflow               detached presentation, transport, source builds
  migration                         explicit historical-format conversion

  api / measure / old graph files   temporary Windows-gated predecessor group
```

Normal core installation now resolves 13 packages including RK and imports no
numerical, dataframe, plotting, service or solver implementation. `[workflow,excel]`
runs the real source builds with no NumPy, pandas, Polars, networkx, Speckle, Pyomo
or Plotly installed. Numerical helpers do not represent persistent content or
infer Flow semantics. Removed names fail rather than dispatch to a second API.
Use [the upgrade guide](../LEGACY_UPGRADE_GUIDE.md) for construction, migration and
explicit calculation examples. [Behaviour mapping](../research/full-migration/turn4/BEHAVIOUR.md)
explains each retired responsibility and the deliberate changes.

## Acceptance

One wheel, SHA-256 `027a4cd6727a43f30de7b0ddf0cd6adf06355c73e91da5f866157d2c1dcfac14`,
was used for current installed consumer checks. It remains version 0.8.71 because
this work is unreleased; identify it by its hash and source state.

- **1,058 local tests passed; 24 optional MiniZinc checks skipped.** Three named
  live predecessor tests were excluded. The count changed from Turn 3 because
  old display/container tests were replaced; the per-suite change is retained.
- Seven schema suites, Python/C# generation freshness, 168 typed sources and
  intended negative calls passed.
- Core installation, optional financial/execution checks, scalar forward/inverse,
  output reuse, temporal/scenario/policy regressions and seven fresh walkthroughs passed.
- All three real project builds, strict comparisons, project tests/lint/typing,
  separate Mandarin SOM comparison and fresh Mandarin notebook passed on Python 3.13.
- Cross-language serialization passed; the captured Mac Rhino export was accepted
  by the new wheel. C# code is unchanged; no fresh Mac UI or Windows acceptance is claimed.
- The AST audit assigns all 671 frozen symbols and 95 consumers. Remaining old
  runtime imports occur only inside the held predecessor group and its tests.

See [baseline, exact results and limits](../research/full-migration/turn4/BASELINE.md),
[commands](../research/full-migration/turn4/COMMANDS.md), and
[the ledger](../research/full-migration/turn4/ledger.json). Original workbooks,
archives, unrelated ignore edits, conflict copy, Rhino/GHX sources and the layout
reference worktree are preserved.

## Remaining work

[The remaining retirement register](../research/full-migration/turn4/RETIREMENT.md)
is the next work queue. Provide the Windows host and approved publication destination,
complete its connector roundtrip, then remove the held dependency group in one
verified slice. This work does not create publication authority or claim that
Mac/offline tests close that gate. Hypar is retired; Browser/outliner remains on hold.
The earlier profiled native runtime crash remains an open diagnostic event, with
successful unprofiled Turn 3 runs retained as separate evidence.
