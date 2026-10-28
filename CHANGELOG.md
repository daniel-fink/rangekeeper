# Changelog

This file records the changes in each 1.x release. towncrier writes each section
from the fragments in [`changelog.d/`](changelog.d/README.md). Do not edit the
sections by hand. The 0.8 line keeps its changelog on `support/0.8`.

<!-- towncrier release notes start -->

## 1.0.0a2 (2026-10-28)

### Breaking changes

- Move the packages into the 1.0 layers (ADR-010, ADR-012). `rangekeeper.calculations` becomes
  `rangekeeper.finance`. `model.duration` becomes `duration`, and `run.execution` becomes `execution`.
  `model.flux` becomes the `flow` package, with `flow._mapping`, `flow._batch` and the interim
  `flow.series`. `shared.units` becomes `quantity`, and `rangekeeper.Quantity` is at the root.
  `model.system.projection` becomes `model.system.table`. The ADR-012 renames apply:
  `Specification.lock` and `unlock` become `fix` and `free`, the `calculations.series.Aggregation`
  result becomes `FlowAggregate`, the `model.system.reduction.Aggregation` result becomes
  `RollupResult`, `duration.calendar.measure` becomes `count_steps`, and `duration.period.align`
  becomes `containing_period`. `Stream.labels` becomes `Stream.names`, with the `names` parameter of
  `Stream.select` and `Stream.from_values`. The test suite moves from `src/tests` to `tests`. The compiler,
  evaluator and scenario-calculation fingerprints change once, because the module paths change:
  `replay` raises `ReplayUnavailableError` for a scenario realization saved before; generate it again. The upgrade
  guide lists every move; run `tools/codemod` to apply them to other code. ([#95](https://github.com/daniel-fink/rangekeeper/issues/95))
- The `RecordStore` protocol moves to the internal `shared` layer, so `execution` no longer imports
  `io` (ADR-010). The `rangekeeper.io.store` module is removed: import `RecordStore` and `Document`
  from `rangekeeper.io`. The consumer codemod rewrites these imports. ([#98](https://github.com/daniel-fink/rangekeeper/issues/98))
- Each public package declares its public names in `__all__` (ADR-017): `rangekeeper.finance` lists its
  submodules and loads them on first access, and `rangekeeper.quantity` lists `Quantity`, `UnitSystem`,
  `default_units` and `minor_unit`. `rangekeeper.__all__` no longer lists the internal packages `schema`
  and `shared`; they still load on access. One shared helper, `shared.exports.lazy`, gives the lazy
  exports of every package. The `model.scenario.replay` submodule becomes private, so
  `rangekeeper.model.scenario.replay` is always the function.
  Each public name has one canonical import path, plus the root re-exports `Model`, `Specification`,
  `Run` and `Quantity`. `rangekeeper.model` is the path for `System`, `Entity`, `Assembly`,
  `Relationship`, `Expression`, `Reference`, `Function`, `Domain`, `Constraint`, `Formulation`,
  `Binding` and `Distribution`; `model.system`, `model.expression`, `model.formulation` and
  `model.scenario` no longer export them. `Quantity` is in `rangekeeper.quantity` and at the root, not in
  `rangekeeper.model`. The consumer codemod rewrites these imports. ([#99](https://github.com/daniel-fink/rangekeeper/issues/99))
- Rule evaluation moves from `rangekeeper.specification.rule` to the new `rangekeeper.execution.rule`. Import `evaluate`, `observe`, `Observation`, `RuleResult` and `RuleCapabilityError` from `rangekeeper.execution.rule`. `rangekeeper.specification.rule` keeps only the rule declarations (`RuleSet`, `Decision`, `Rule`, `Action`, `ActionKind`, `ObservationBinding`, `ObservedQuantity` and `RuleEvidence`) and their validation. The codemod rewrites these imports. ([#102](https://github.com/daniel-fink/rangekeeper/issues/102))
- Remove `flow.series` (formerly `calculations.series`): Flow and Stream methods are the only API for
  series operations (ADR-010). `align` becomes `Stream.align()`, and `Alignment.reduce` becomes
  `Stream.aggregate` on the aligned Stream. `aggregate` becomes `Stream.aggregate`, `sum`, `min` and
  `max`. `resample` becomes `Flow.resample(periods, *, method, weighting, missing)`, with the same
  arguments as `Stream.resample`; it returns a Flow, and `Stream.resample` also gives coverage.
  `multiply` becomes `Flow.multiply(*others)`, and `integrate` becomes `Flow.integrate`.
  `Flow.trim(start=, end=)` becomes `Flow.trim(span)`, as `Stream.trim(span)`. `AlignmentJoin`,
  `AggregationMethod`, `ResamplingMethod`, `MeanWeighting` and `FlowAggregate` are in `rangekeeper.flow`. ([#103](https://github.com/daniel-fink/rangekeeper/issues/103))
- Remove the shim modules `model.measure` and `model.distribution`. Import `Measure`, `Distribution`
  and `DistributionFamily` from `rangekeeper.model`, and `Quantity` from `rangekeeper` or
  `rangekeeper.quantity`. Import `Characteristics`, `Label`, `Value` and `ValueKind` from
  `rangekeeper.model`. ([#104](https://github.com/daniel-fink/rangekeeper/issues/104))
- Generated records contain data only. `rangekeeper.schema.behaviors` is removed: `Flow` and `Movement` are owner subclasses in `rangekeeper.flow`, `Period` and `Span` in `rangekeeper.duration`, and `Distribution` (still public as `rangekeeper.model.Distribution`) in `rangekeeper.profile`. Construction of a generated record, `from_data` and nested decoding return the owner class, so existing code keeps its methods. Import `MissingValueHandling` from `rangekeeper.flow`. `replace` returns `Self`. ([#106](https://github.com/daniel-fink/rangekeeper/issues/106))
- Value types keep their local rules from construction: a Period starts before it ends; a Movement has a date or a period; a Flow has unique Movement IDs and ordered, unmixed, non-overlapping coordinates; a Distribution has valid parameters. Construction, `replace` and `from_data` raise `ValidationError` (code `invariant.<kind>`) when a rule fails, so an invalid value can no longer exist until a later `.check()`. `Period.check()` and `Span.check()` are removed. `Flow.check()` now checks only the units and, with `resolved=True`, the numbers; `Distribution.check()` checks only the units. ([#109](https://github.com/daniel-fink/rangekeeper/issues/109))
- Validation runs in tiers (ADR-011). Typed record constructors and `replace` run generated node checks of the one record, not jsonschema; jsonschema runs for untrusted input only: `from_data`, `from_json`, the JSON and YAML codecs and `DirectoryStore` reads. Semantic validation stays at Model, Specification and Run construction and before execution. A typed constructor that rejects a field now reports `structure.value`, `structure.required` or `structure.rule` with the field path, instead of the jsonschema keyword code. Building a Flow is about 5 times faster. ([#110](https://github.com/daniel-fink/rangekeeper/issues/110))
- `io.polars.to_frame(flow)` and `from_frame` are now a lossless round trip: integer magnitudes stay integers. The `magnitude` column is `Int64` when all values are integers, `Float64` when all are floats, and an `Object` column when they mix or exceed `Int64`; before, a mixed Flow became `Float64`. The Movement columns, the Model sections of `Update`, the closed Specification fields and the lineage slots of Metadata now come from the schema slots. The new `lineage` slot annotation marks `Metadata.id` and `Metadata.previous`; `slots.json` carries it for every slot. ([#113](https://github.com/daniel-fink/rangekeeper/issues/113))
- Currency amounts are now exact decimals (ADR-023). A magnitude in ISO 4217 units, such as `AUD`, is a `Decimal` with at most 15 significant digits, and JSON, YAML and Bundle data store it as canonical decimal text: `"magnitude": "1250000.5"`. The JSON reader rejects a number or non-canonical text for an amount; the YAML reader also accepts a plain numeral. Use `.number` for float arithmetic: `Decimal` does not mix with `float`. `Settings.relative_tolerance` and `time_limit` are now `double`, `ImplementationKind` has the new value `convention`, and `minor_unit` moved from `rangekeeper.quantity` to `rangekeeper.money`. Documents written by 1.0.0a1 or earlier with numeric currency magnitudes must be converted. ([#117](https://github.com/daniel-fink/rangekeeper/issues/117))
- Reset the Model, Specification and Run formats, and every schema module, to 1.0.0 (ADR-017). A
  reader reads every format with its major version, up to its own version; `supports_version` in
  `schema.validation` applies this rule with the versions from the schema manifest. The reader does
  not read 0.x documents: Model 0.7.0 and 0.8.0, Specification 0.7.0 and Run 0.4.0 raise
  `UnsupportedVersionError`. `rangekeeper.io.migration` and `model_07_to_08` are removed. Rebuild
  stored 0.x documents and Bundles from their source pipelines, or convert them with the one-off
  conversion tool, `python -m tools.upgrade` (#120). Model revision identities change, because they include the
  format version. ([#118](https://github.com/daniel-fink/rangekeeper/issues/118))
- Period and Span fields become `start` and `end` (ADR-012, ADR-017). The interval stays half-open:
  it includes `start` and excludes `end`. The fields, the `start` and `end` parameters of
  `make_period` and the other calendar functions, the generated C# properties `Start` and `End`, and
  the wire keys change. `Period.end` is now the stored field, with the same value as the earlier
  derived property. `first` and `last` stay derived. ([#119](https://github.com/daniel-fink/rangekeeper/issues/119))
- `Executor(backend=)` defaults to `"pyomo-highs"` and no longer accepts `None`; omit the argument for the
  default backend. ([#131](https://github.com/daniel-fink/rangekeeper/issues/131))
- Compiler, evaluator and scenario-calculation fingerprints now hash the static import closure of each computation, not a hand-written file list. The old lists missed modules that the computations run. All fingerprints change once: a scenario realization saved with an earlier version stays readable, but `replay` raises `ReplayUnavailableError` for it. Generate the realization again to replay it. ([#133](https://github.com/daniel-fink/rangekeeper/issues/133))
- The unit registry is curated. It contains only ISO 4217 currencies, length, area and volume with SI prefixes, time without prefixes, count, dwelling, percent and ratio, and the aliases `sqm`, `sqft` and `pa` (per annum: `"AUD pa"` is AUD per year). Other Pint units, such as `kg`, `kWh`, `kelvin`, `degC` and prefixed time units, now raise `UnitError` with suggestions in `UnitError.suggestions`; `m2` and `ft2` are no longer aliases, so use `sqm` and `sqft`. `UnitSystem` adds `parse_quantity`, `minor_unit`, `register` and `alias`. ([#149](https://github.com/daniel-fink/rangekeeper/issues/149))
- `Issue.code` is a `rangekeeper.errors.Code` member, and an `Issue` with an unknown code raises `ValueError`. A missing solve role has the code `semantic.role`, not `semantic.contract`. A Run that exceeds its symbol or constraint limit records a `symbol_limit` or `constraint_limit` diagnostic instead of `unsupported_capability`. ([#154](https://github.com/daniel-fink/rangekeeper/issues/154))
- Execution errors are renamed so that each name ends in `Error`: `UnsupportedProblem` and `UnsupportedExpression` are now `UnsupportedError`, `BackendUnavailable` is `BackendUnavailableError` and `AttemptDeadline` is `AttemptDeadlineError`. `HierarchyError.code` is a `hierarchy.*` code, for example `hierarchy.multiple_parents`, and its message no longer starts with the code. `BoundaryError` and `ValueEncodingError` are removed; catch `RangekeeperError` or `EncodingError` instead. ([#155](https://github.com/daniel-fink/rangekeeper/issues/155))
- The message of `MissingReferenceError` now names the kind of item and where it was searched, for example `Entity 8f0c… not found in Model 2b1d…`, not the bare UUID or path. Read `error.requested` instead of `str(error)`. ([#156](https://github.com/daniel-fink/rangekeeper/issues/156))
- The internal module `rangekeeper.model.scope` is split. The typed lookups `target_value`, `target_units` and `recorded_scalar` move to `rangekeeper.model.targets`; the checks over raw mappings move to the private `rangekeeper.model._scope`. The codemod rewrites these imports. ([#161](https://github.com/daniel-fink/rangekeeper/issues/161))
- The module `rangekeeper.model.characteristics` and its functions `value()` and `label()` are removed. Use `model.value(owner=entity.id, key=)` and the new `model.label(owner=entity.id, key=)`; `Model.label(id)` also looks up a Label by UUID. A missing key now raises `MissingReferenceError`, with the owner and the nearest keys, instead of returning `None`. ([#271](https://github.com/daniel-fink/rangekeeper/issues/271))
- Profiles, market paths and rules move into their 1.0 packages (#201, decisions D2, D12, D29 and D41):

  - `rangekeeper.finance.projection` is `rangekeeper.profile`. `ProjectionMethod` is `GrowthMethod` and `project_values` is `grow_values`.
  - `rangekeeper.finance.dynamics` is `rangekeeper.market.dynamics`, and `rangekeeper.model.scenario` is `rangekeeper.market`. Its `market` module is `rangekeeper.market.generation`.
  - `rangekeeper.finance.account` and `rangekeeper.model.formulation.account.schedule` are removed: compose funding with `cumulative()` and Model equations. `account.interest` is `rangekeeper.model.formulation.financial.interest`.
  - "Policy" becomes "rule". `rangekeeper.specification.policy` is `rangekeeper.specification.rule`. The `Policy` record is `RuleSet`, `DecisionOutcome` is `RuleEvidence`, `PolicyResult` is `RuleResult` (with `evidence`) and `PolicyCapabilityError` is `RuleCapabilityError`. In the 1.0.0 formats, the Specification field `policy` is `rules`, the Run report field `outcomes` is `rule_evidence`, and the schema module `policy` is `rule`.

  Run the consumer codemod to change imports and names. Rebuild stored Specifications and Runs that use the old fields.

  ([#311](https://github.com/daniel-fink/rangekeeper/issues/311))
- A Run `Diagnostic` has an optional `values` field: one JSON object of the named inputs and evidence of the finding. A `settings_adjusted` diagnostic must name its settings in `values.settings`; Run validation no longer searches the message for them. The `solver_termination` and `solver_scaling` diagnostics record their solver evidence in `values`, not as JSON text in `message`. Read `values`; a reader older than this release rejects a Run that has the field. A backend `Result.evidence` must be JSON. ([#312](https://github.com/daniel-fink/rangekeeper/issues/312))

### Removals

- Removed code with no users: `model.definitions.find_taxonomies` and `find_functions`, the `calculations.interval` module and its `Interval` class, `io.atomic.replace` and `replace_json`, and the `Measurement` record (`model.measure.Measurement`, `schema.records.Measurement` and the C# `Measurement`). No Model holds a `Measurement`, so a Fact could not target one; use a measurement `Value`. Schema modules `measure` 0.3.0 and `provenance` 0.5.0 record the change; valid documents do not change. ([#166](https://github.com/daniel-fink/rangekeeper/issues/166))

### Features

- Publish the consumer codemod for 1.0.0a2. The repository includes the index of the 1.0.0a1 package
  (`tools/codemod/indexes/rangekeeper-1.0.0a1.json`), and the upgrade guide gives the commands that
  apply the rename map to code that uses Rangekeeper. ([#96](https://github.com/daniel-fink/rangekeeper/issues/96))
- Generated records encode and decode each field with code that the generator selects, and keep decoded child records, so a repeated read such as `flow.movements` returns the same tuple. The runtime no longer reads `slots.json`. `tools/performance/records.py` measures the record costs; see the record runtime research page. ([#107](https://github.com/daniel-fink/rangekeeper/issues/107))
- `replace` checks only the record that changes: its changed fields and its class rules, with checks generated from the JSON Schema. It no longer validates or copies the child records, so `flow.replace(units=...)` costs microseconds for any number of Movements. `rangekeeper.OMIT` removes an optional field. `repr` of a record is one short line; use `to_data` for the complete content. ([#108](https://github.com/daniel-fink/rangekeeper/issues/108))
- Every document has the same two validation methods. `Model.validate()`, `Specification.validate()` and `Run.validate()` return a `ValidationReport` of coded issues and raise nothing for content problems; `check()` returns the document or raises `ValidationError` with that report. Both take `resolver=` and `units=`: with a resolver, a Specification composes and checks each concrete case, and a Run checks its tree and outputs. ([#111](https://github.com/daniel-fink/rangekeeper/issues/111))
- Stores and codecs trust validated documents: `put`, `dumps` and `write` no longer validate an exact `Model`, `Specification` or `Run` again, and a `MemoryStore` returns the stored instance. Data input (`loads`, `read`, store reads) is always validated. A Model validated with its own unit system can now be stored without a second validation against the default units. ([#112](https://github.com/daniel-fink/rangekeeper/issues/112))
- Added `rangekeeper.money` with `is_currency`, `minor_unit`, `to_number`, `to_amount` and `round`, plus `Quantity.number` and `Quantity.round`. Construction converts a float in currency units at 15 significant digits, half even, and the library rounds to minor units only on request. The C# example reads and writes amounts as `System.Decimal` with `Amounts`. ([#117](https://github.com/daniel-fink/rangekeeper/issues/117))
- Added `Flow.round`, which rounds each currency amount to its minor unit or to `places`. Each Run now records the currency-amount convention as `Implementation(kind=convention, name="rangekeeper.money", version="1")`. Building a currency Flow from floats is now within 10 % of the time for the same Flow in other units. ([#117](https://github.com/daniel-fink/rangekeeper/issues/117))
- Added a one-off conversion tool, `python -m tools.upgrade`, in the repository (not in the wheel). It converts stored 0.x documents (Model 0.7.0 and 0.8.0, Specification 0.7.0, Run 0.4.0) and Bundles to the 1.0.0 formats: the version reset, Period and Span `start` and `end`, `policy` to `rules`, `outcomes` to `rule_evidence`, and currency magnitudes as decimal text. Documents keep their UUIDs. The upgrade guide explains when to rebuild and when to convert. ([#120](https://github.com/daniel-fink/rangekeeper/issues/120))
- Every extension point uses one registry pattern (ADR-013): a Protocol, `register(name, implementation)`
  and an optional `rangekeeper.<point>` entry point group, with a fingerprint for each implementation.
  The registries are `rangekeeper.execution.backends.registry` (built-in `pyomo-highs`),
  `rangekeeper.quantity.unit_systems` (built-in `default`) and `rangekeeper.io.geometry_providers`.
  `Executor(backend=)` takes a backend or a registered name. Each Run records the backend and the unit
  system with their fingerprints, and `UnitSystem.fingerprint` is new. See the extension points reference. Unknown names raise
  `rangekeeper.errors.UnknownExtensionError` (`extension.unknown`) and name conflicts raise
  `ExtensionConflictError` (`extension.conflict`). ([#131](https://github.com/daniel-fink/rangekeeper/issues/131))
- `Model.unit_system` is public. Views, tables, reductions, Specification validation and locking, policy evaluation, execution and Run validation use the Model's unit system when no `units` argument is given. ([#150](https://github.com/daniel-fink/rangekeeper/issues/150))
- `rangekeeper.errors.Code` lists the code of each diagnostic. A validation `Issue` and a `ContractError` now carry `targets`, `values` and `evidence` fields; read these and the code, not the message. An underdetermined solve's diagnostic references the unknowns that no equation constrains, and a missing solve role names each Value by key and UUID. ([#154](https://github.com/daniel-fink/rangekeeper/issues/154))
- Every error that Rangekeeper raises subclasses `rangekeeper.errors.RangekeeperError` and has a `code` from `rangekeeper.errors.Code`. Each keeps the built-in base that callers catch today, for example `ValueError`. `rangekeeper.errors` exports the base and the errors that several packages raise, such as `ValidationError`, `MissingReferenceError`, `UnitError` and `UnsupportedError`; an error of one package, such as `HierarchyError`, stays in that package. ([#155](https://github.com/daniel-fink/rangekeeper/issues/155))
- `Model.entity(code=)` and `Model.entity(name=)` return one Entity or Assembly. No match raises `MissingReferenceError`; several matches raise the new `rangekeeper.errors.AmbiguousReferenceError` (code `reference.ambiguous`). Both errors have the fields `requested`, `by`, `kind`, `where` and `candidates`, which say what was requested, where, and the nearest or matching codes. ([#156](https://github.com/daniel-fink/rangekeeper/issues/156))

### Fixes

- `calculate_irr` now checks the IRR residual at the earliest payment. A distant `valuation_date` no longer rejects a valid root, and a valuation date far before the payments no longer accepts an inaccurate root. `IrrResult.residual` still reports the residual at `valuation_date`. ([#164](https://github.com/daniel-fink/rangekeeper/issues/164))
- Stream sums repair a group with `math.fsum` only when cancellation makes the native sum's error bound more than `1e-8`. Groups with no cancellation and more than 45 rows no longer take the slow path; a wide all-positive Stream sum is about 8 to 10 times faster. ([#165](https://github.com/daniel-fink/rangekeeper/issues/165))

### Documentation

- The 1.0.0a2 rename map in the upgrade guide is final. It gives the 1.0 name of every moved, renamed and removed public name, with the walkthrough decisions of #255: `rangekeeper.profile`, `rangekeeper.market`, rules instead of policies, no account, and `pv`, `npv` and `irr`. The glossary's current names match the code. ([#93](https://github.com/daniel-fink/rangekeeper/issues/93))
- Every generated record field now has a real docstring, taken from its LinkML description; placeholders such as `Kind.` are gone. The schema generator stops when a class or slot has no description. ([#115](https://github.com/daniel-fink/rangekeeper/issues/115))
- Added ADR-023, the design for currency amounts in 1.0: Decimal in records, JSON, YAML and Parquet, float64 inside calculations with explicit conversions, and rounding to currency minor units on request. The library does not change yet. The record lists the breaking format changes planned for 1.0.0. ([#117](https://github.com/daniel-fink/rangekeeper/issues/117))
- The contributor guide has a new page, "Make a change", with the steps for one pull request: the branch,
  the hooks, the layer rules, tests, the API snapshot, the changelog fragment, documentation and release. ([#199](https://github.com/daniel-fink/rangekeeper/issues/199))
- The walkthrough proposed cells in `examples/walkthrough/proposed` give the code that a reader types in each of the seven lessons, written against the 1.0 API. They record the decisions on cases, funding, rollups, non-affine results, policies, growth profiles (a new `rk.profile` namespace), `rk.Quantity`, equations as text and as `rangekeeper.expressions`, and queries, and the API gap list. ADR-024 designs search as a query over a range of cases. ([#201](https://github.com/daniel-fink/rangekeeper/issues/201))
- Add ADR-021, the design for rules that decide one value over market paths: availability, evaluation order, staged solves for each path, decision traces, replay and paired comparison. It amends ADR-013 and ADR-014 and replaces the current `specification.policy` API when #215 lands. ([#213](https://github.com/daniel-fink/rangekeeper/issues/213))
- Add ADR-022, the design for choosing between design alternatives: Model revisions as alternatives, choice keys, the realised structure of each path, strategy comparison and the premium question. It amends ADR-001 so that a Specification can pin several Model revisions. ([#214](https://github.com/daniel-fink/rangekeeper/issues/214))
- The upgrade guide has a section for 1.0.0a1 to 1.0.0a2: the consumer codemod, the changes it does not
  make, the 1.0.0 document formats, and the breaking surface for 1.x consumers with its routes
  (codemod, deterministic builds, and rebuild or convert for stored Bundles). ([#217](https://github.com/daniel-fink/rangekeeper/issues/217))

### Engineering

- Add the rename-pass codemod in `tools/codemod` and a draft rename map for 1.0.0a2. The upgrade guide shows the draft map. The package does not change yet. ([#94](https://github.com/daniel-fink/rangekeeper/issues/94))
- An import-linter contract enforces the 12 layers of ADR-010; the new `layers` CI job and a pre-commit
  hook run `lint-imports`. Stream table display and Stream export move into `rangekeeper.flow`, and
  execution builds its candidate revision without `rangekeeper.io`, so no layer imports a higher one. The
  candidate revision keeps the unit system of its input Model. ([#97](https://github.com/daniel-fink/rangekeeper/issues/97))
- Add an API snapshot test (ADR-017). `tests/contracts/api.json` records each public name, its kind,
  its defining module and its signature; the test fails on an unreviewed change. ([#100](https://github.com/daniel-fink/rangekeeper/issues/100))
- The schema generator is split into small functions. It now stops when a slot name is a Python keyword or shadows a record method, or when a slot has more than one record type. `tools/schema/check_generator.py` tests these checks. ([#114](https://github.com/daniel-fink/rangekeeper/issues/114))
- Readers share one JSON policy (`rangekeeper.shared.encoding.parse_json`), one YAML policy (`rangekeeper.shared.yaml.decode`), one JSON Pointer helper and one duplicate-identity check. `Record.from_json` now raises `DecodeError`, a `ValueError`, for duplicate keys, and duplicate identities in a Model scope report the code `semantic.identity`. ([#116](https://github.com/daniel-fink/rangekeeper/issues/116))
- The test suite mirrors the packages (ADR-018): `tests/<package>`, `tests/contracts`, `tests/integration`
  and `tests/walkthrough`. Suites named after reviews and refactoring take behaviour names in their owner
  folders. The Model validation suite no longer compares with a frozen copy of the old orchestration.
  `tests/contracts` holds the jsonschema conformance of structural validation and the golden account
  results. ([#177](https://github.com/daniel-fink/rangekeeper/issues/177))


## 1.0.0a1 (2026-10-27)

### Breaking changes

- `rangekeeper.visualisation.table` moves to `rangekeeper.model.display`. `Flow.display()`, `Stream.display()`, `Pivot.display()` and their notebook HTML need only the `calculations` extra, not `visualisation`. ([#89](https://github.com/daniel-fink/rangekeeper/issues/89))
- Rangekeeper requires Python 3.12 or later and supports 3.12 and 3.13. The distribution name is lowercase: `rangekeeper`. ([#172](https://github.com/daniel-fink/rangekeeper/issues/172))

### Removals

- `rangekeeper.visualisation` (charts, PyVis graph display and `LocalDisplay`) and the `visualisation` extra are removed. The charts and graph display are walkthrough helpers in `examples/walkthrough/helpers`. Use `Stream.display()` for tables. ([#87](https://github.com/daniel-fink/rangekeeper/issues/87))
- `rangekeeper.io.speckle`, its contract and the geometry viewer are removed from the package; the wheel no longer ships the viewer. They are walkthrough helpers in `examples/walkthrough/helpers`, and the viewer build is in `examples/walkthrough/viewer`. ([#88](https://github.com/daniel-fink/rangekeeper/issues/88))
- The package no longer contains `rangekeeper.schema.native`, the stock LinkML module, which could not be imported without LinkML. The conformance tools generate it when they need it. ([#105](https://github.com/daniel-fink/rangekeeper/issues/105))

### Features

- A feature that needs a missing optional extra raises an `ImportError` that names the extra, for example `pip install 'rangekeeper[bundle]'`. Core modules need no extra: `year_fraction` no longer uses PyXIRR. ([#173](https://github.com/daniel-fink/rangekeeper/issues/173))
- `rangekeeper.__version__` gives the installed version. Versions come from git tags. ([#174](https://github.com/daniel-fink/rangekeeper/issues/174))

### Fixes

- Windows: the directory store, the file codecs and Bundle writing no longer fail on durability syncs.

### Packaging

- The source distribution contains only the package, its metadata and the licence. ([#80](https://github.com/daniel-fink/rangekeeper/issues/80))
- Dependencies use compatible version ranges instead of exact pins; `uv.lock` keeps the exact versions for development. The execution worker accepts any Pyomo and HiGHS version in range and records the versions it found in the Run evidence. ([#170](https://github.com/daniel-fink/rangekeeper/issues/170))
- `ipykernel` is no longer a runtime dependency. Install it with your notebook environment. ([#171](https://github.com/daniel-fink/rangekeeper/issues/171))
- On Windows, Rangekeeper depends on `tzdata`, so that time zone keys in Content values decode without a system time zone database.

### Documentation

- The design transport reference moves to the walkthrough helpers' README and the Grasshopper guide to the example's README. The Windows connector acceptance procedure moves to history: it is no longer a library gate. The architecture page lists the folders outside the package. ([#92](https://github.com/daniel-fink/rangekeeper/issues/92))
- Walkthrough plan v2 (ADR-020) defines the seven 1.0 lessons, their readers, developer-experience rules and source rights. It supersedes the ADR-006 curriculum. ([#200](https://github.com/daniel-fink/rangekeeper/issues/200))
- The mixed-use property data in `examples/data/mixed_use_property` is licensed under CC BY 4.0. Its manifest gives the origin, description and licence of each file, and `origins.json` gives the origin of each teaching assumption. ([#210](https://github.com/daniel-fink/rangekeeper/issues/210))

### Engineering

- The walkthrough uses four figures from de Neufville and Geltner (2018) with the publisher's permission and with attribution. ADR-020 records this. ([#76](https://github.com/daniel-fink/rangekeeper/issues/76))
- The C# Model library and Grasshopper components move from `src/grasshopper` to `examples/grasshopper`, as an unsupported example. The C# generator writes there, and a `dotnet` CI job builds the Model library and fixture runner and round-trips the cross-language fixtures. ([#90](https://github.com/daniel-fink/rangekeeper/issues/90))
- The chart, graph, local display, Speckle envelope and geometry tests move to the walkthrough CI job. The core test suite installs no chart, graph or Matplotlib dependency. ([#91](https://github.com/daniel-fink/rangekeeper/issues/91))
- pre-commit runs ruff, mypy, nbstripout and the changelog check. ([#182](https://github.com/daniel-fink/rangekeeper/issues/182))
- CI tests Linux and macOS on Python 3.12 and 3.13 and Windows on Python 3.13, each optional extra alone, and the built wheel. It also runs ruff, mypy, the generated-file checks, the documentation check and the changelog check (#180, #181, #184, #185, #186, #188). ([#183](https://github.com/daniel-fink/rangekeeper/issues/183))
- A `walkthrough` CI job runs the helper tests and each lesson from a fresh kernel in the locked walkthrough environment, then converts each lesson for the docs site. ([#187](https://github.com/daniel-fink/rangekeeper/issues/187))
- A pushed version tag publishes the release to PyPI by trusted publishing, after maintainer approval, and creates a GitHub Release with build provenance attestations. `SECURITY.md` lists the supported versions (#70, #71). ([#189](https://github.com/daniel-fink/rangekeeper/issues/189))
- The walkthrough moves onto `develop` under `examples/walkthrough`: seven lesson skeletons named `NN_slug.ipynb`, the presentation helpers with tests, a locked environment and the book resources. `tools/docs/notebooks.py` converts executed lessons to Markdown for the Zensical docs site. The Jupyter Book configuration and environment in `walkthrough/` are removed. ([#202](https://github.com/daniel-fink/rangekeeper/issues/202))
