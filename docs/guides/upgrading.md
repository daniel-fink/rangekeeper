# Upgrade older Rangekeeper consumers

This guide maps retired APIs to the maintained canonical operations.
The [dated retirement report](../history/FULL_MIGRATION_TURN4.md) and
[behaviour map](../research/full-migration/turn4/BEHAVIOUR.md) identify removed names.
Root numerical/presentation modules are removed without aliases. The old graph,
Measure and Speckle API group remains temporarily held for Windows acceptance
under `rangekeeper.legacy`. The old root and `graph` paths have no aliases; see
[legacy isolation](../contributing/legacy-retirement.md).
Do not build new consumers on that group or treat old Graph JSON as Model JSON.

**Package ownership, 2026-10-08:** root `Model`, `Specification` and `Run` imports
remain. Import Table/Row from `rangekeeper.shared.table`, Model graph operations
from `rangekeeper.model.system`, passive equations from
`rangekeeper.model.formulation`, captured futures from `rangekeeper.model.scenario`,
policy operations from `rangekeeper.specification.policy`, and the executor from
`rangekeeper.run.execution`. Source Evidence and invocation contracts live in
`rangekeeper.workflow.evidence` and `rangekeeper.workflow.operation`. Import Metadata
from `rangekeeper.schema` and boundary errors from `rangekeeper.shared.errors`.
The former paths have no aliases. Import deterministic kernel functions directly
from `rangekeeper.calculations.dynamics`; its old submodules are removed.
See the [package map](../concepts/architecture.md).

**Movement naming, 2026-10-06:** import `Movement` from `rangekeeper.model.flow`
and use `Flow.movements`. These replace `FlowSample` and `Flow.samples` in Python
and the `samples` field in JSON/YAML. Use `movement.coordinate` for alignment
identity and `movement.resolve(timing=...)` for an explicit date convention. There are no aliases.
Old draft documents must rename `samples` to `movements` explicitly, preserving
order, keys, dates/periods, magnitude presence and Claim references. Save changes
as a new Model revision; do not overwrite historical snapshots. Old and mixed
field names are rejected. See [the contract](../reference/calculations.md#movement-naming)
and [verification](../research/full-migration/movement-naming/README.md).

**Flow semantics, 2026-10-06:** Flows have no semantic kind or basis. The overall
model logic selects and interprets calculations. Units, coordinates, alignment,
missingness and operation-specific numerical requirements remain checked. This
removes the unreleased draft's `basis=` and `result_basis=` arguments. Saved draft
payloads must have their `basis` field removed explicitly as part of a new Model
revision; older snapshots remain historical. `Value.kind=ValueKind.FLOW` still identifies
the content shape. See the [contract](../reference/calculations.md#flow-semantics-and-explicit-operations)
and [verification](../research/full-migration/flow-semantics/README.md).

**Duration namespace:** use `rangekeeper.model.duration` for calendar operations
and Period/Span records. The former `rangekeeper.temporal` and `rangekeeper.duration`
paths are removed without aliases. Old `duration.Type/Sequence/Span` callers require
an explicit port. The private `_legacy_duration` module has also been removed.

## Current graph API changes

Import `reducers` from `rangekeeper.model.system` and use its qualified names:

| Retired API | Replacement |
| --- | --- |
| `reducers.sum_quantities` | `reducers.sum` |
| `reducers.mean_quantities` | `reducers.mean` |
| `reducers.min_quantity` | `reducers.min` |
| `reducers.max_quantity` | `reducers.max` |
| `graph.projection.to_tree_table(hierarchy)` | `model.system.projection.to_table(hierarchy)` |
| `aggregation.known_subtotal(id)` | `aggregation.available_value(id)` |

These names have no aliases. `to_table(view)` keeps flat View order;
`to_table(hierarchy)` uses preorder and adds `parent_id`. Rename an old `view=`
keyword to `source=`. `available_value()` returns the available result for every
reducer; `value()` still applies the requested completeness policy. Construct
`Aggregation` from `AggregateEntry(available, coverage)` entries, selected Value
IDs and `require_complete`, instead of parallel value/coverage maps. Closed Python
choices require enum members, including `EntityField`, `HierarchyKind` and
`CoverageStatus`; saved JSON/YAML strings retain their documented wire values.
See [graph contracts](../reference/system.md) for ownership and revision checks.

## Install and check the artifact

From a checkout containing this change, build/install the package from `src`.
See the [installation guide](installation.md) for supported Python versions
and the [verification guide](../contributing/verification.md) for current checks.
Install only the extras your consumer needs. Core records, units and JSON stores
need none; source builds use `[workflow,excel]`.

```sh
python -m pip install '.[calculations,tables,yaml,workflow,execution,plotting,visualization]'
python -c 'import rangekeeper; print(rangekeeper.__file__)'
```

Run notebooks from a fresh kernel using that environment. Execution dependencies
remain a separate `execution` extra. `financial` installs PyXIRR without the wider
calculation stack; `speckle` adds the SDK for explicit live receive. Notebook tools
are installed separately. The temporary `legacy` extra is only for the held old API. Do not copy a notebook's stored output and
call that an executed migration. Record the source revision and wheel hash; an
unreleased change can share a package version with an earlier artifact.

## Record methods and replacement

The [record boundary](../reference/records.md) defines the current method contracts.
Use `movement.number` for finite numerical access, `flow.check(resolved=True)` to
require complete numerical inputs, and `record.replace(...)` to create a validated
copy. Replacement preserves omitted, null and empty fields. Persist meaningful
changes through the document facade's `revise` method.

`clean` removes unresolved movements; it does not validate or impute them. Single
record operations now live on their owning classes. The old free-function names
and private Flow helpers have no compatibility aliases.

| Removed draft API | Current API |
| --- | --- |
| `magnitude(movement)` | `movement.number` |
| `validate_flow(flow)` / `require_resolved(flow)` | `flow.check()` / `flow.check(resolved=True)` |
| `movement_coordinate(movement)` / `resolve_date(movement, ...)` | `movement.coordinate` / `movement.resolve(...)` |
| `replace_movement` / `replace_movements` | Typed `movement.replace(...)` / `flow.replace(...).check()` |
| `AlignmentResult` / `AggregateResult` | `Alignment` / `Aggregation` |
| `AccountResult` / `calculate_account(...)` | `Account` / `Account.calculate(...)` |
| `calculate_cumulative_density` / `calculate_interval_mass` | `distribution.cdf(...)` / `distribution.mass(...)` |

## Author canonical content

Use the [Model authoring example](../reference/model.md#authoring-lookup-and-revisions).
Author measurements and Flow Values with an explicit Measure and an owner-local
key. `Stream` selects ordered Value UUIDs from one immutable Model revision; it is
not a mutable replacement for Model ownership. Two Values can use one Measure.
Names are search fields, while UUIDs establish identity.

Encode and decode properties through `model.content`. The [property contract](../reference/model.md#property-content)
owns supported types and exact preservation. Map Pint-bearing legacy Features
explicitly instead of silently converting their content into measurements.

## Time, units, and arithmetic

Flow coordinates have day resolution. Use Python `datetime.date` values; the wire
format uses `YYYY-MM-DD` strings. `Period(start_inclusive=..., end_exclusive=...)` is half-open. There is no
`TimePoint` record or intraday Flow support. Rich property content can still retain
source timestamps; those are not Flow coordinates. Generated Source date fields
now return Python dates; their timestamp alternatives still return strings. Both
keep the same wire format.

`Flow.from_periods` stores coverage only by default. Use its optional `dates=` argument
only for independently known payment or observation dates. These dates may be
outside the covered period. Resolve a missing date explicitly for a calculation
or display; the convention does not become stored content.

`PeriodTiming.FIRST` selects the first included day; `LAST` selects the final included day;
`END` selects the exclusive boundary. Recorded dates take precedence. Undated
periods require `timing=` in `calculate_xnpv`, `calculate_irr` and Polars `dates`.
`collapse` requires a chosen `on=` date or a timing convention unless the final
movement records a date. `calculate_pv` instead uses its explicit movement-index
convention. Trimming keeps whole covered periods and rejects partial overlap.
Resampling groups by coverage and produces period aggregates without payment dates;
keep the original Flow when individual payment facts are required.

| Old call or assumption | Replacement / deliberate change |
|---|---|
| `duration.Type` / pandas frequency inference | Explicit `frequency=Frequency.MONTH` etc.; ten calendar frequencies in `model.duration.calendar` |
| Inclusive `Span.end_date` | Half-open `[start,end)` Period/Span; add one calendar day when mapping an inclusive date-only end |
| `Flow.from_dict/from_sequence` | Explicit ordered dates/magnitudes in `Flow.from_events`; duplicate dates need keys |
| `Flow.from_projection` | `calculations.projection.project` or `allocate`, with Quantity and Periods |
| Mutating Flow/Stream / `duplicate` | Immutable records; new calculation result; new Model revision for persisted changes |
| `Stream.sum/min/max` | `series.aggregate(reducer=AggregationReducer.SUM)` (or `.MIN` / `.MAX`); exact alignment by default, explicit units/missing/join |
| `Stream.product` | `series.multiply`; dimensionless factors scale quantities; unit powers remain intact |
| Period rates treated as amounts | `series.integrate`, with explicit exposures or period day-count convention |
| `Flow.resample(frequency)` | Explicit complete target Period grid, reduction and missing policy; every mean requires weighting |
| `Flow.clean/trim/diff/collapse` | `flow.clean/trim/difference/collapse`; see docstrings for unresolved first differences and time bounds |
| Mutable pandas content | `adapters.polars.to_frame/from_frame`; `dates` is a detached presentation projection |
| Implicit global RNG | `distribution.sample(size=..., generator=...)` |
| `flow.pv` | `financial.calculate_pv(rate=..., first_period=1)`; rate is per observation period |
| `flow.npv/irr` | `calculate_xnpv(valuation_date=..., day_count=...)`; `calculate_irr(guess=...)` returns one root and residual; guess is optional; both require `timing=` for undated periods |
| Account constructor calculates silently | `Account.calculate(..., balance=..., current_interest=..., treatment=...)`; result has opening/closing/overdraft/interest Flows |

`Frequency`, `PeriodTiming`, `MonthRoll` and `DayCount` come from
`rangekeeper.model.duration`. Frequency text from external configuration must be converted
explicitly, for example `Frequency("month")`. Offsets and sequences default to
`MonthRoll.PRESERVE_END`; `CLAMP` keeps the original day where possible. A former
`month_end=True` call on a mid-month anchor needs explicit alignment first:
`align(day, frequency=Frequency.MONTH).last`. Retain that original anchor when
extending a sequence. Stored Period fields are `start_inclusive` and `end_exclusive`.

Import `Balance`, `CurrentInterest` and `InterestTreatment` from `rangekeeper.calculations.account`.
Simple, compound and capitalized calculations become EXCLUDED/SEPARATE,
EXCLUDED/FINANCED and INCLUDED/FINANCED, respectively. Advance uses CLOSING;
arrears uses OPENING. INCLUDED requires FINANCED. The default remains closing,
excluded and separate. The passive `model.formulation.account.schedule` supports the
nonnegative fixed-rate subset; signed overdrafts remain a known-data calculation.

Multiplying `AUD/year` by a dimensionless market factor leaves `AUD/year`.
Multiplying two rates retains both time dimensions. No operation strips time to
make a result appear valid. The model determines the meaning of the product.
A rate-to-amount conversion requires an exposure.

Use a `DayCount` member, not a string, with `series.integrate`, or supply explicit
exposure Quantities. The [calculation reference](../reference/calculations.md#timing-integration-and-valuation)
owns integration, resampling, timing and valuation contracts.

Dataframe round trips require `_present` metadata and explicit units. `polars.dates`
is a detached date/magnitude projection and is not lossless storage. Timestamps
are not implicitly converted to Flow dates. See [tables](../reference/tables.md).

Financial calculations now delegate to PyXIRR. Remove the draft `bracket=` and
solver `tolerance=` arguments; no bounded-solver fallback remains. `IrrResult`
reports one root, residual, guess and method, not uniqueness. See the current
[financial contract](../reference/calculations.md#timing-integration-and-valuation).

## Store and revise

Use `Model.revise(Update(...))` for a meaningful complete-section update. Use
`MemoryStore` or `DirectoryStore` to retain immutable snapshots. A Flow calculation
returns a detached result; author it as a Value in a new Model revision to retain
it. A new Model revision does not rewrite a Specification or historical Run.
See [Model revisions](../reference/model.md#authoring-lookup-and-revisions),
[storage](../reference/run-and-storage.md) and the explicit [wire migration order](#movement-roles-equations-and-draft-format-changes).

## Convert an old persisted Graph

```sh
python -m rangekeeper.migration old-graph.json converted-review
# Optional collision map: {"old-value-uuid": "reviewed-new-key"}
python -m rangekeeper.migration old-graph.json converted-with-keys --value-keys keys.json
```

Both destinations must be new directories. Review `report.json`, its source SHA256,
UUID map and issues. A successful conversion writes validated `model.json`.
Unsupported fields/types, missing/cyclic references, conflicting owner keys and
invalid units produce issues and **no Model**. Nothing overwrites the source.
Keep the source file with the report. The new converter imports no old Graph code.

The bounded reader supports `rk.graph` version 1, separate canonical Assembly
storage, classifications, Labels, Measurements, supported Features, Sources,
Claims, Facts and reconciliations. Measure quantity-kind/aggregation hints become
explicit legacy tags; they do not choose new reducers. Historical Claim payloads
retain their old inert wire encoding and referenced-object closure. They are
source evidence, not executable or governing mathematics. Other format versions
and executable objects are unsupported. Prefer rebuilding source workflows from
original inputs and reviewed mappings when these are available.

## Migrate source workflows separately

The mathematical `Specification` is not `WorkflowSpec`. Run source builds with
`python -m rangekeeper.workflow`, not `rangekeeper.graph.workflow`. Rebuild from
original inputs and reviewed mappings where possible; each property Value must
retain its source Claim/Fact lineage.

| Earlier source/API contract | Current contract |
| --- | --- |
| Outer Sources, Model, Decisions and Checks YAML version 1 | Version 2 for all four; no automatic version-1 conversion |
| Nested extraction policy | Retains its own version 1 contract |
| Measure `quantity_kind` or `aggregation` hints | Remove; declare the intended calculation explicitly |
| Measurement mapping | Supply owner-local `key`, canonical `measure` and source `binding` |
| `features` and `on_unavailable.feature` | `properties` and `on_unavailable.property`, with owner-local keys |
| `graph_*` check operands | `model_keys`, `model_count`, `model_total`, `model_value` |
| Measure-only Value selection | Explicit `value_key`; quantity operands also require units |
| Flattened `CheckResult` operands | Explicit `left` and `right`; serialized `checks.json` uses `rk.workflow-checks/v2` |
| Old Evidence imports | `rangekeeper.workflow.evidence` |
| `AdapterError`, `AdapterEncodingError` | `rangekeeper.shared.errors.BoundaryError`, `EncodingError` |
| `Table.from_view`, `Table.from_arborescence` | `model.system.projection.to_table(View or Hierarchy)` |
| Python string choices for closed categories | Enum members; serialized configuration retains wire strings |

Workflow semantics version 5 changes derived computation identity, not business
identifiers. Consult [workflow](../reference/workflow.md) and [evidence](../reference/evidence.md)
for current contracts. The synthetic [source examples](source-workflows.md)
retain zero, missing, conflict and source-note cases. They do not establish live
service or host acceptance.

## Corrections to retain during future ports

- The residual land-value expectation `241049.33` did not satisfy its stated
  finance equation. An independent cash/debt recurrence gives
  **239654.64260783806** and finance **10345.35739216196**. The former expected
  value leaves a residual of **1454.1535992423**. The migrated test asserts both
  the independent root and the rejected expectation's residual.
- The old test-only linear model restarted terminal discounting at period one.
  Its replacement discounts terminal proceeds across the full holding period.
  The basic DCF notebook's intended result remains **1000**, checked independently.
- Distribution bounds are checked element by element. Degenerate distributions
  return the requested sample count. Shock impact is applied once, explicitly.
- Numerical kernels do not establish acausal support. The executor supports finite Movement
  equations and exogenous policies; unknown rates, nonlinear/piecewise symbolic
  accounts and endogenous sequential decisions remain outside affine execution.

The historical financial migration snippet is preserved in
[`guide_example.py`](../research/full-migration/financial-library/guide_example.py).
The [dated financial verification](../research/full-migration/financial-library/README.md) records its
installed-wheel run and the notebook and regression evidence. The
[original Turn 1 report](../research/full-migration/turn1/README.md) remains historical evidence.

## Movement roles, equations and draft-format changes

Current Model/Specification documents use 0.7.0; Runs use 0.4.0.
References use `Reference(target=uuid)` in Python and `{target: UUID}` on the wire.
Every Movement requires its own UUID. The optional key remains an alignment label.
There is no `ScopedValueReference`; diagnostic participants use the owning Run's
input Model. See [references and identity](../reference/identity.md).

Use `upgrade_model` for Model 0.3.0/0.4.0/0.5.0/0.6.0 and `upgrade_specification` for
Specification 0.4.0/0.5.0/0.6.0. The converters derive Movement UUIDs from the former
Value UUID and key, then update references to the same UUIDs. Supply upgraded
external revision pins explicitly. Inputs and opaque Claim content remain unchanged.
Validate the upgraded Specification with its resolver before execution.

Construct `Reference(target=uuid)` directly for either a Value or a Movement.
`assign_flow(model, value, ids=...)` explicitly reuses resolved amounts;
`unknown_flow(model, value, ids=...)` declares them unknown. Omit `ids` for all entries.
Estimates do not fill missing assignments. A Measure is not a Value selector.

The converters create new document revisions and reject unsupported content.
They do not strip old `basis`/`samples` fields or convert old Graph JSON. Apply
those earlier draft corrections first. Historical Runs are never upgraded.

Install `./examples` with the matching library and use
`rangekeeper_examples.investment`. Its `author`, `formulate`, `specify` and `report`
operations separate declaration, investigation, execution and reporting. Execute
with `run.execution.Executor`; obtain the accepted Model through its returned
Run and revision store. The [examples guide](examples.md) owns runnable commands.

Use `model.formulation` builders for declarations and `calculations` for known-data
results. Fixed-rate growth and discounting can solve forward or inverse initial
amounts. General IRR and unknown discount/growth rates are not affine investigations.
Do not embed Python callbacks in policy records or perform calculations in a model
constructor. Keep source-building `WorkflowSpec` separate from mathematical
`Specification`.

## Captured scenarios and policy comparisons

Use `model.scenario.market.make_plan`, `generate` and `model.scenario.replay`.
See [scenarios](../reference/scenarios-and-policies.md) for captured provenance, current names
and composable authoring. Replay never redraws random inputs.

Choose `sample` to inspect draws before realization, or `capture` plus `realize`
for supplied innovations. `resolve_input` and `resolve_output` avoid collisions
between parameter and path names. Seed, key and component select a stream;
worker count does not. Parallel generation requires the usual guarded Python
script entry point when called outside notebooks.

Policies see only declared quantities available by each decision date and earlier
decisions. Forward-derived market ratios are unavailable before their inputs.
Exactly one threshold sale occurs: include that period's operations and sale,
then zero later investment cashflows. The full scenario remains intact. Compare
fixed and flexible investments using the same realization; label hindsight
horizon selection explicitly. Threshold policies do not guarantee a market peak.

The [walkthrough guide](walkthroughs.md) owns scenario-count settings and fresh-kernel
acceptance. Historical [Turn 2 evidence](../research/full-migration/turn2/README.md)
records that checkpoint, not verification of the current checkout.

## RK naming and existing scenario drafts

The [scenario reference](../reference/scenarios-and-policies.md#scenario-vocabulary) records the current vocabulary. `Market` is a
read-only view of canonical Values, not another persistent document. Use
`model.distribution.Distribution` and its `uniform`, `triangular`,
`pert`, or `symmetric` class methods. Instance calculation methods consume the
same generated record; numerical methods are no longer attached to a second
handwritten Distribution class.

`migration.upgrade_scenario_names(old_data)` explicitly converts the unreleased
old v1/v2 method labels into `market`, `market.estimates` and `market.independent`.
Pass detached Model 0.5.0 or 0.6.0 data; the function returns a new Model revision and
preserves Value UUIDs, quantities, Movement coordinates, claims and random stream
identifiers. Codecs do not upgrade automatically. Old Runs keep their original
Model pins and are not relabelled as new executions. Select the new Model revision
explicitly when authoring a later Specification.

## Workbench, design and external consumers

`workbench.inspect` reads without writing. `workbench.build` writes a new local
attempt bundle with `model.json`. Only `attempt.result` from that successful
attempt is current. Never substitute `attempt.previous` after failure. Use
`adapters.cytoscape.layout.review.build(model, bundle=..., profile=..., output_root=...)`
as a separate presentation step. Pass the Model and bundle from the successful
attempt explicitly. Upgrade v1/v2 profiles
explicitly with `migration.layout.upgrade_profile(profile, model=model)`; v3 uses
classification UUIDs, owner-local Value keys and explicit units.

Use `rangekeeper_examples.design.fixture()` with `adapters.speckle.encode_model`
and `decode_model` to test the local canonical envelope without a service SDK.
The [design transport reference](../reference/design-transport.md) owns that contract.

For service use, import `receive` from `adapters.speckle.transport` and supply an
already configured client plus exactly one version or object pin. An unavailable
historical version does not select latest. Legacy payloads require the explicit
`migration.speckle.convert_speckle` mapping and units. Check its issues before using
the Model. Names are search fields; UUIDs establish identity. Geometry associations
are external metadata, not domain membership.

For design financial work call `design.author`, `formulate`, `specify`, then
`Executor.execute`; retrieve the accepted output from the store and report it.
Keep the declared five-year expense schedule and next-income-period reversion
basis. Do not replace it with a conventional basis without a reviewed model change.

Grasshopper exports canonical JSON from LinkML-derived C# records. Python performs
full semantic validation. The [C# guide](grasshopper.md) explains identity,
revisions, host acceptance and the separate Windows connector gate. See the
[consumer register](../research/full-migration/turn3/CONSUMERS.md) for proved consumers
and the [retirement register](../research/full-migration/turn3/RETIREMENT.md) for holds.

## Dataframe migration

Install the `tables` extra, or `calculations`, for Polars. The `pandas` extra and
adapter are removed. Replace Table `to_dataframe` with `polars.to_frame`, and
`from_dataframe` with `polars.to_table`. Replace Flow `to_series` with `polars.dates`;
its date is an explicit column. Use canonical Flow records for arithmetic.
CSV now preserves `NA` as text and represents missing cells with None. Supply
`schema_overrides` when numeric-looking identifiers must remain text.

## Repository examples

Example builders now live in `examples/rangekeeper_examples`. Install `./examples`
with the matching library, then import `rangekeeper_examples.design` or
`rangekeeper_examples.investment`. The library no longer exports
`rangekeeper.examples`. See [the examples guide](examples.md).
