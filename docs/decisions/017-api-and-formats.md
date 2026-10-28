# ADR-017: Public API, stability and data formats

Status: accepted for 1.0; 1.0.0 format reset and Decimal money implemented in 1.0.0a2 (#118, #117); format freeze and Bundle format 1 pending. Recorded: 2026-10-26.

## Problem

Version 1.0 promises stability, but four things are not decided:

- **The public API.** Only some modules define `__all__`. Most records have
  several import paths. Downstream code imports internal modules.
- **Document formats.** They have their own version numbers: Model 0.8.0,
  Specification 0.7.0 and Run 0.4.0. These look like package versions. The
  library also keeps a reader for Model 0.7.
- **The Bundle format.** Its identifiers end in `-proposal`, and the format is
  not frozen.
- **Money.** It is float64 everywhere, with no rounding rule.

## Choice

### Public API and stability

- **What is public.** The public API is the names in the `__all__` of the root
  package and of each public package ([ADR-010](010-layers-and-packages.md)).
  Other names have a leading underscore or belong to an internal package.
- **Snapshot test.** An API snapshot test fails on any unreviewed change to
  public names or signatures.
- **Semantic versioning from 1.0.0.** A breaking change to a public name or
  format needs a new major version.
- **Deprecation.** In 1.x, a deprecated public name keeps working, with a
  warning, for at least one minor release. It is removed only in the next
  major version.
- **Internal routes used by consumers.** Some internal modules have downstream
  users, for example the validation, encoding, structured-data and table
  helpers. These get a public route or a replacement before 1.0.0b1.

### Document formats

- **Reset.** All document formats reset to 1.0.0: Model, Specification, Run and
  MarketPaths ([ADR-014](014-market-paths.md)).
- **Compatibility.** A 1.x reader accepts every 1.x document format. A change
  that older 1.x readers cannot read needs a new major format version.
- **Removed:** the Model 0.7 reader and `io.migration`.
- **Conversion.** A one-off script in `tools/` (not shipped) converts 0.10.x
  documents and Bundles to 1.0.0. A downstream user chooses one route: rebuild
  from its source pipelines, or run the conversion script.

### Format changes before the freeze

These changes land before milestone 1.0.0b1:

- Decimal at the boundaries (below).
- Period and Span `start` and `end` ([ADR-012](012-naming-and-glossary.md)).
- The MarketPaths document kind ([ADR-014](014-market-paths.md)).
- A declarative query `Filter`, as data and not code, with:
  - label tests that include sub-types by default, with an `exclusive` option,
    which matches `View.filter`;
  - number comparisons on a measurement key, converted by the unit system:
    equal, not equal, less, less or equal, greater, greater or equal, and between;
  - tests for a present or missing value;
  - missing-value handling as in [ADR-016](016-safety-defaults.md).

Raw-text properties are out of scope. An API addition, not a format change,
lets a Pivot use a label key for its columns.

### Bundle format 1

- The identifiers become `rangekeeper.bundle/1` and `rangekeeper.parquet/1`.
- Every 1.x reader opens every 1.x Bundle.
- The format freezes at milestone 1.0.0b1, after all format changes above.
- Golden fixtures in `tests/contracts` protect it.
- The reader keeps the `check_index=False` reopen option.

This record approves the stable release of Bundle format 1, which ADR-008 left open.

### Money

- Currency amounts are Decimal in records and in their serialised forms.
- Calculations use float64 inside, with compensated summation.
- Conversion between the two happens only at explicit calculation boundaries.
- Rounding follows explicit rules, with currency minor units.

The implementation design chooses the JSON and Parquet encodings. They must
round-trip exactly. [ADR-023](023-decimal-money.md) gives the design.

## Alternatives and consequences

- **Every documented module is public.** The surface to keep stable would be
  much larger.
- **Keep the independent document version numbers.** The confusion with package
  versions would stay.
- **Mark Bundle as provisional in 1.0.** Its consumers would get a weaker contract.
- **Decimal everywhere.** This is incompatible with the solver and with the
  fast Polars paths.

The tracking project contains a migration issue for downstream users. It lists
the public names that change.

## Sources and related decisions

- [ADR-008: Bundle contract](008-rangekeeper-bundle-contract.md), amended by this record.
- [ADR-009: classification sub-types](009-classification-sub-types.md).
- [ADR-012](012-naming-and-glossary.md), [ADR-014](014-market-paths.md) and
  [ADR-016](016-safety-defaults.md).

Supersedes: none. Amends: ADR-008. Superseded by: none.
