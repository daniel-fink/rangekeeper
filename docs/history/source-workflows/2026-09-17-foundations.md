# Source-workflow foundation results — 17 September 2026

Status: historical validation record. Extracted on 2026-10-08 from the former
`ingestion-evidence.md` and `excel-ingestion.md` pages. The counts, environment
limits and migration state below describe those original runs. They do not prove
acceptance of the current checkout or current external projects. Later refinement
notes did not state a separate date; their original sequence is retained.

Current contracts: [Evidence](../../reference/evidence.md),
[Excel](../../reference/excel.md) and [source workflows](../../reference/workflow.md).
Current procedures: [verification](../../contributing/verification.md).

## Foundation validation — 17 September 2026

- 151 RK tests passed across ingestion evidence, adapters, immutable graph and
  Cytoscape adapter suites. Ruff and ty checks passed for the changed foundation.
- The worked example produced identical output and fingerprints in two separate
  Python processes. New package files also passed Python 3.10 syntax parsing;
  runtime tests used Python 3.13.
- 76 Mandarin tests passed in a temporary compatibility copy using current project
  code and specifications, with only its viewer module replaced by the committed
  version. The actual workspace suite could not collect because a pre-existing
  local graph_viewer.py edit has an indentation error. That edit was preserved.

This validates the foundation and compatibility, not a completed reader,
operation catalogue or Mandarin ingestion migration.

### Bundled-row refinement

Row now owns its optional ID alongside values; Table has no parallel row_ids
field. Ordinary Tables can mix identified and unidentified rows. Evidence
requires every row to be identified, with empty Tables valid by default.

The combined RK foundation/adapter/graph/viewer and actual Mandarin workspace
suites passed 226 tests after this refinement. The worked example retained its
previous fingerprint. The earlier Mandarin viewer syntax error has been fixed
in a separate user-authorized repair, so the compatibility copy is no longer
needed. Readers, transformation execution and YAML migration remain deferred.

### Validation and encoding separation

The profile abstraction has been removed in favor of explicit Table validation.
Contracts, validation and artifact fingerprinting now have separate modules;
primitive encoding is in shared/encoding.py, and identity lookup is Table.row(UUID).

Validation: 234 tests passed across ingestion evidence, adapters, immutable graph,
Cytoscape and Mandarin. Captured pre-refactor available/missing fingerprints and
an issue ID match exactly; the executable example also retains its fingerprint.
Fresh-process imports and constructor validation pass. Ruff and focused ty checks
pass. No project artifacts were regenerated.

## Validation — 17 September 2026

- 211 RK tests passed: the 48 new operation/document/Excel tests plus ingestion
  Evidence, adapters, immutable graph, Cytoscape adapter and shared validation.
- 81 Mandarin tests and 27 Cytoscape JavaScript tests passed. Mandarin source
  parsing and viewer behavior were not migrated or redesigned.
- Ruff lint/format checks passed on the changed Python files. Focused ty checks
  passed for the new adapter code and executable example. Mandarin Ruff checks
  and focused source-reader/viewer type checks also passed.
- The synthetic demo passed, including repeated extraction with identical Evidence
  fingerprints and Issue IDs. Fresh-process identity and optional-import isolation
  tests passed.
- The checksum-bound local JLL demo passed. All previously retained cells matched
  Mandarin's current reader across raw/formula/cache/type/format/XML fields. The
  new snapshot additionally retains explicit unpopulated cell observations. Source
  checksums before and after matched; no project artifact was regenerated.
- The original Evidence example retained its baseline fingerprint:
  `sha256:e2d03a8472a7db27cae45f5c9388bd93d5673106056d444eb22a6d99c33260e9`.
- Runtime: Python 3.13.15, openpyxl 3.1.5, PyYAML 6.0.3, pytest 9.1.1,
  Ruff 0.16.6 and ty 0.0.79. Ten new adapter/example files also passed Python
  3.10 syntax parsing. Python 3.10–3.12 runtime execution was not performed.

Validation corrected typing at the immutable-container and optional-row-ID
boundaries, made the YAML resolver import explicit, aligned import/export ordering,
and updated the existing adapter export-list regression for the three new modules.
No source interpretation or graph model was changed.

This validates the first reader/extraction slice, not full declarative graph
execution. Those first-slice results preceded the later Mandarin migration, which
now uses the existing RK APIs for all three workbooks. See the project
`docs/source-adapters.md` for its separate compatibility checks and ownership review.
Other document adapters remain deferred.
