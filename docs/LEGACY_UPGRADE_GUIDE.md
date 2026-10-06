# Upgrade older Rangekeeper consumers

This guide maps retired APIs to the maintained canonical operations.
The [current retirement report](history/FULL_MIGRATION_TURN4.md) and
[behaviour map](research/full-migration/turn4/BEHAVIOUR.md) identify removed names.
Root numerical/presentation modules are removed without aliases. The old graph,
Measure and Speckle API group remains temporarily held for Windows acceptance
under `rangekeeper.legacy`. The old root and `graph` paths have no aliases; see
[legacy isolation](LEGACY_ISOLATION.md).
Do not build new consumers on that group or treat old Graph JSON as Model JSON.

**Movement naming, 2026-10-06:** import `Movement` from `rangekeeper.model.flow`
and use `Flow.movements`. These replace `FlowSample` and `Flow.samples` in Python
and the `samples` field in JSON/YAML. Use `movement.coordinate` for alignment
identity and `movement.resolve(timing=...)` for an explicit date convention. There are no aliases.
Old draft documents must rename `samples` to `movements` explicitly, preserving
order, keys, dates/periods, magnitude presence and Claim references. Save changes
as a new Model revision; do not overwrite historical snapshots. Old and mixed
field names are rejected. See [the contract](CALCULATIONS.md#movement-naming)
and [verification](research/full-migration/movement-naming/README.md).

**Flow semantics, 2026-10-06:** Flows have no semantic kind or basis. The overall
model logic selects and interprets calculations. Units, coordinates, alignment,
missingness and operation-specific numerical requirements remain checked. This
removes the unreleased draft's `basis=` and `result_basis=` arguments. Saved draft
payloads must have their `basis` field removed explicitly as part of a new Model
revision; older snapshots remain historical. `Value.kind="flow"` still identifies
the content shape. See the [contract](CALCULATIONS.md#flow-semantics-and-explicit-operations)
and [verification](research/full-migration/flow-semantics/README.md).

**Duration namespace, 2026-10-06:** use `rangekeeper.duration` for calendar
operations. `rangekeeper.temporal` is removed without an alias. The records remain
in `rangekeeper.model.duration`. Old `duration.Type/Sequence/Span` callers require
an explicit port. The private `_legacy_duration` module has also been removed.

## Install and check the artifact

From a checkout containing this change, build/install the package from `src`.
Python 3.10–3.13 is supported by the package metadata. Current checks use Python
3.10.19 and 3.13.11; see the [environment and evidence](research/full-migration/turn4/BASELINE.md).
Install only the extras your consumer needs. Core records, units and JSON stores
need none; source builds use `[workflow,excel]`.

```sh
python -m pip install './src[calculations,tables,yaml,workflow,execution,plotting,visualization]'
python -c 'import rangekeeper; print(rangekeeper.__file__)'
```

Run notebooks from a fresh kernel using that environment. Execution dependencies
remain a separate `execution` extra. `financial` installs PyXIRR without the wider
calculation stack; `speckle` adds the SDK for explicit live receive. Notebook tools
are installed separately. The temporary `legacy` extra is only for the held old API. Do not copy a notebook's stored output and
call that an executed migration. Package version 0.8.71 is unchanged by this
unreleased work; use the source revision/wheel hash, not that version alone.

## Record methods and replacement

The [record boundary](RECORD_BOUNDARY.md) defines the current method contracts.
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

```python
from rangekeeper.model.flow import Flow
from datetime import date
from uuid import uuid4
from rangekeeper import Model
from rangekeeper.model import (
    Metadata, Definitions, Measure, System, Entity, Characteristics, Value,
)
from rangekeeper.model.content import encode, decode
from rangekeeper.model.flow import Stream
from rangekeeper.duration import make_periods
from rangekeeper.calculations import series

periods = make_periods(date(2026, 1, 1), frequency="month", count=3)
flow = Flow.from_periods(periods, (10, 0, None), units='meter')
measure = Measure(id=uuid4(), code="length", name="Length", units="meter")
reading = Value(id=uuid4(), key="delivered", kind="flow", measure=measure.id, flow=flow)
note = Value(id=uuid4(), key="source", kind="property", content=encode({"checked": False}))
owner = Entity(id=uuid4(), code="A", characteristics=Characteristics(values=(reading, note)))
model = Model.create(
    metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
    definitions=Definitions(measures=(measure,)), system=System(entities=(owner,)),
)
stream = Stream.from_values(model, (reading.id,))
assert decode(model.value(note.id).content) == {"checked": False}
assert stream.flows[0].total(missing='skip').magnitude == 10
```

`Model` owns the Value. `Stream` selects ordered Value UUIDs in that revision.
Two Values may use one Measure and still have different keys and content. A name
is not an identifier. Use Model UUID lookup and explicit `find`/selection APIs.
An unresolved movement is not zero. `skip` is a deliberate incomplete aggregation;
`aggregate` and `resample` additionally return coverage. `total` returns a Quantity,
not a new persistent Value or a Run.

`PropertyContent` supports null, bool, int, finite float, str, UUID, date, datetime,
time, timedelta, list, tuple, set, frozenset, dict, and MappingProxyType, recursively.
Lists, tuples, mapping order, timezone/fold and negative zero retain their meaning.
`decode` returns detached data. Arbitrary classes, callbacks, cyclic objects and
nonfinite numbers fail. Pint objects in a legacy Feature require an explicit
consumer mapping to a Measure/Value; the converter reports them as unsupported
instead of changing their type. Pint quantities in Measurements remain supported.

## Time, units, and arithmetic

Flow coordinates have day resolution. Use Python `datetime.date` values; the wire
format uses `YYYY-MM-DD` strings. `Period(start, end)` is half-open. There is no
`TimePoint` record or intraday Flow support. Rich property content can still retain
source timestamps; those are not Flow coordinates. Generated Source date fields
now return Python dates; their timestamp alternatives still return strings. Both
keep the same wire format.

`Flow.from_periods` stores coverage only by default. Use its optional `dates=` argument
only for independently known payment or observation dates. These dates may be
outside the covered period. Resolve a missing date explicitly for a calculation
or display; the convention does not become stored content:

```python
from rangekeeper.model.flow import Flow

from rangekeeper.calculations.financial import calculate_xnpv
assert flow.movements[0].date is None
assert flow.movements[0].resolve(timing='last_day') == date(2026, 1, 31)
paid = Flow.from_periods(periods[:1], (100,), units='AUD', dates=(date(2026, 2, 5),))
assert paid.movements[0].resolve(timing='start') == date(2026, 2, 5)
pv = calculate_xnpv(paid, rate=0.1, valuation_date=date(2026, 1, 1))
```

`start` selects the first included day; `last_day` selects the final included day;
`end` selects the exclusive boundary. Recorded dates take precedence. Undated
periods require `timing=` in `calculate_xnpv`, `calculate_irr` and Polars `dates`.
`collapse` requires a chosen `on=` date or a timing convention unless the final
movement records a date. `calculate_pv` instead uses its explicit movement-index
convention. Trimming keeps whole covered periods and rejects partial overlap.
Resampling groups by coverage and produces period aggregates without payment dates;
keep the original Flow when individual payment facts are required.

| Old call or assumption | Replacement / deliberate change |
|---|---|
| `duration.Type` / pandas frequency inference | Explicit `frequency="month"` etc.; ten calendar frequencies in `duration.calendar` |
| Inclusive `Span.end_date` | Half-open `[start,end)` Period/Span; add one calendar day when mapping an inclusive date-only end |
| `Flow.from_dict/from_sequence` | Explicit ordered dates/magnitudes in `Flow.from_events`; duplicate dates need keys |
| `Flow.from_projection` | `calculations.projection.project` or `allocate`, with Quantity and Periods |
| Mutating Flow/Stream / `duplicate` | Immutable records; new calculation result; new Model revision for persisted changes |
| `Stream.sum/min/max` | `series.aggregate(reducer="sum" | "min" | "max")`; exact alignment by default, explicit units/missing/join |
| `Stream.product` | `series.multiply`; dimensionless factors scale quantities; unit powers remain intact |
| Period rates treated as amounts | `series.integrate`, with explicit exposures or period day-count convention |
| `Flow.resample(frequency)` | Explicit complete target Period grid, reduction and missing policy; every mean requires weighting |
| `Flow.clean/trim/diff/collapse` | `flow.clean/trim/difference/collapse`; see docstrings for unresolved first differences and time bounds |
| Mutable pandas content | `adapters.polars.to_frame/from_frame`; `dates` is a detached presentation projection |
| Implicit global RNG | `distribution.sample(size=..., generator=...)` |
| `flow.pv` | `financial.calculate_pv(rate=..., first_period=1)`; rate is per observation period |
| `flow.npv/irr` | `calculate_xnpv(valuation_date=..., day_count=...)`; `calculate_irr(guess=...)` returns one root and residual; guess is optional; both require `timing=` for undated periods |
| Account constructor calculates silently | `Account.calculate(..., method=..., timing=...)`; result has opening/closing/overdraft/interest Flows |

Multiplying `AUD/year` by a dimensionless market factor leaves `AUD/year`.
Multiplying two rates retains both time dimensions. No operation strips time to
make a result appear valid. The model determines the meaning of the product.
A rate-to-amount conversion requires an exposure:

```python
from rangekeeper.model.flow import Flow
from rangekeeper.model.measure import Quantity
rates = Flow.from_periods(periods, (120, 120, 120), units='AUD/year')
amounts = series.integrate(rates, day_count="actual/365", units="AUD")
assert abs(amounts.total().magnitude - 120 * 90 / 365) < 1e-9
```

Calendar-month accrual can instead supply explicit exposure Quantities. The model
selects the resampling operation: for example, last for a closing balance, sum for
receipts, or mean with a specified weighting. These choices are not inferred or
restricted by a stored Flow kind. Bounded movements that cross target Periods fail;
allocate them explicitly first. `missing="zero"` fills absent rows/empty target
groups only; it does not turn an explicitly unresolved observation into zero.
Fractional resampling coverage counts known observations, not continuous time coverage.

Dataframe roundtrips require the adapter's `_present` metadata plus explicit units.
This metadata preserves absent versus explicit-null movement fields.
`polars.dates` omits Periods and Claims and is not a lossless storage format.
`adapters.polars.dates` projects native calendar dates and magnitudes. Use
`Flow.from_events` with native dates to author observations. Timestamps are not
accepted as implicit dates.

Financial calculations delegate to PyXIRR. The earlier draft `bracket=` and
solver `tolerance=` arguments are removed; no bounded-solver fallback is retained.
`IrrResult` contains `rate`, `residual`, `guess`, and `method="pyxirr.xirr"`.
A guess is an initial estimate, not a bound or a guarantee of a particular root.
No result establishes that an IRR is unique. Failed/nonfinite library results
raise `ValueError`; an IRR residual larger than 1e-8 of gross movements (with a
one-unit floor) also fails. Empty Flows have zero XNPV but no IRR.

```python
from rangekeeper.model.flow import Flow

from rangekeeper.calculations.financial import calculate_irr
investment = Flow.from_events([date(2026, 1, 1), date(2027, 1, 1)], (-100, 110), units='AUD')
result = calculate_irr(investment)  # optional guess=0.1
assert abs(result.rate - 0.1) < 1e-9
assert result.method == "pyxirr.xirr"
```

## Store and revise

```python
from rangekeeper.io import MemoryStore, json
from rangekeeper.model import Update
store = MemoryStore()
store.put(model)
loaded = json.loads(json.dumps(model), kind=Model)
assert loaded.to_data() == model.to_data()
reviewed_owner = Entity.from_data({**owner.to_data(), "name": "Reviewed delivery"})
revised = model.revise(Update(system=System(entities=(reviewed_owner,))))
assert revised.id != model.id and revised.metadata.previous == model.id
store.put(revised)
```

Use `DirectoryStore` for filesystem persistence. Writes are append-only by revision
UUID; conflicting content fails. A Flow calculation returns a detached result;
author its result as a Value in a new Model revision when it must be retained.
Changing a revision does not silently rewrite a Specification or historical Run.
Model 0.3.0/0.4.0 upgrades use `migration.upgrade_model`; it creates a new UUID and
`metadata.previous`. `migration.upgrade_specification` upgrades a 0.4.0 Specification,
requiring the new Model UUID and explicit mappings for included/case revisions.
Retain historical Runs with their original pinned documents and reader environment.

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

The mathematical `Specification` is not `WorkflowSpec`. The synthetic
`src/examples/workflow/{accommodation,equipment}` examples now use workflow version
2, explicit measurement keys, canonical Measure declarations and `properties`.
Each property Value retains source Claim/Fact lineage. Use
`python -m rangekeeper.workflow`, not `rangekeeper.graph.workflow`.
The original zero/missing/conflict/source-note examples remain covered.

External Projects, workbench/layout review, service adapters and host integrations
require their own acceptance checks. A passing synthetic example does not certify them.

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

The complete worked snippet is executable in
[`guide_example.py`](research/full-migration/financial-library/guide_example.py).
The [current financial verification](research/full-migration/financial-library/README.md) records its
installed-wheel run and the notebook and regression evidence. The
[original Turn 1 report](research/full-migration/turn1/README.md) remains historical evidence.

## Movement roles, equations and draft-format changes

Current Model/Specification documents use 0.5.0; Runs use 0.2.0. Replace scalar
expression `target: UUID` with `target: {value: UUID}`. Replace assignment `value`
with `target: {value: UUID}` and wrap scalar unknowns in the same reference shape.
A Flow role adds `movement: KEY`. Use `specification.targets.scalar` and `movement`
for typed references. `assign_flow(model, value)` explicitly reuses resolved amounts;
`unknown_flow(model, value)` declares them unknown even if recorded amounts exist.
Estimates do not fill missing assignments. A Measure is not a Value selector.

The upgrade functions preserve identity, order and provenance, create new revisions
and reject unsupported content. They do not silently strip old `basis`/`samples`
fields or convert old Graph JSON. Apply the documented earlier draft corrections
explicitly before upgrading. There is no automatic historical Run upgrade.

The installed example has separate authoring, formulation, investigation, execution
and reporting operations. This complete example is checked outside the checkout:

```python
from rangekeeper.examples import investment
from rangekeeper.execution import Executor
from rangekeeper.io import MemoryStore
from rangekeeper.run import validate as validate_run

investment_model = investment.formulate(investment.author({"num_periods": 3}))
resale_policy = investment.build_stop_gain_resale_policy(investment_model, minimum_holding_periods=1)
question = investment.specify(investment_model, policy=resale_policy)
investment_store = MemoryStore()
investment_store.put(investment_model)
execution = Executor(investment_store).execute(question)
assert execution.report.status.solution == "feasible"
validate_run(execution, resolver=investment_store).raise_if_invalid()
accepted = investment_store.load_model(execution.record.outputs[0])
report = investment.report(accepted)
assert len(execution.report.decisions) >= 1
assert accepted.metadata.previous == investment_model.id
```

Use `formulations` builders for declarations and `calculations` for known-data
results. Fixed-rate growth and discounting can solve forward or inverse initial
amounts. General IRR and unknown discount/growth rates are not affine investigations.
Do not embed Python callbacks in policy records or perform calculations in a model
constructor. Keep source-building `WorkflowSpec` separate from mathematical
`Specification`.

## Captured scenarios and policy comparisons

```python
from rangekeeper.scenarios import market, replay
from rangekeeper.duration import make_periods

scenario_base = Model.create(metadata=Metadata(id=uuid4(), schema_version="0.5.0"))
scenario_plan = market.make_plan(
    periods=make_periods(date(2027, 1, 1), frequency="year", count=4), seed=23,
)
scenario = market.generate(scenario_base, scenario_plan, scenario_keys=("example",))[0]
assert replay(scenario.model).model is scenario.model
market_path = scenario.space_market_price_factors
assert len(market_path.flow.movements) == 4
```

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

The [Turn 2 evidence](research/full-migration/turn2/README.md) supersedes earlier
counts for the current working tree. The full 2,000-scenario notebook setting is
available but routine acceptance uses four visible scenarios.

## RK naming and existing scenario drafts

The [naming guide](RK_NAMING.md) records the current vocabulary. `Market` is a
read-only view of canonical Values, not another persistent document. Use
`model.distribution.Distribution` and its `uniform`, `triangular`,
`pert`, or `symmetric` class methods. Instance calculation methods consume the
same generated record; numerical methods are no longer attached to a second
handwritten Distribution class.

`migration.upgrade_scenario_names(old_data)` explicitly converts the unreleased
`market.v1`, `market.estimates.v1` and `independent.v1` labels into their v2 methods.
Pass detached Model 0.5.0 data; the function returns a new Model revision and
preserves Value UUIDs, quantities, Movement coordinates, claims and random stream
identifiers. Codecs do not upgrade automatically. Old Runs keep their original
Model pins and are not relabelled as new executions. Select the new Model revision
explicitly when authoring a later Specification.

## Workbench, design and external consumers

Use `rangekeeper.workflow`, not `rangekeeper.graph.workflow`. Outer Sources,
Model, Decisions and Checks documents use version 2; nested extraction policies
keep their own versions. Replace Features with property Values and give each
measurement an explicit owner-local key. Preserve descriptive missing data and
its finding alongside an unresolved quantity. Workflow checks use Model operands.

`workbench.inspect` reads without writing. `workbench.build` writes a new local
attempt bundle with `model.json`. Only `attempt.result` from that successful
attempt is current. Never substitute `attempt.previous` after failure. Use
`layout_review.build` as a separate presentation step. Upgrade v1/v2 profiles
explicitly with `migration.layout.upgrade_profile(profile, model=model)`; v3 uses
classification UUIDs, owner-local Value keys and explicit units.

The transport boundary can be exercised without an SDK or service:

```python
from rangekeeper.examples import design
from rangekeeper.adapters.speckle import encode_model, decode_model

source_design = design.fixture()
envelope = encode_model(source_design)
restored_design = decode_model(envelope)
assert restored_design.to_data() == source_design.to_data()
envelope["rk_model"] = "changed caller-owned data"
assert restored_design.to_data() == source_design.to_data()
```

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
full semantic validation. The [C# guide](../grasshopper/README.md) explains identity,
revisions, host acceptance and the separate Windows connector gate. See the
[consumer register](research/full-migration/turn3/CONSUMERS.md) for proved consumers
and the [retirement register](research/full-migration/turn3/RETIREMENT.md) for holds.

## Dataframe migration

Install the `tables` extra, or `calculations`, for Polars. The `pandas` extra and
adapter are removed. Replace Table `to_dataframe` with `polars.to_frame`, and
`from_dataframe` with `polars.to_table`. Replace Flow `to_series` with `polars.dates`;
its date is an explicit column. Use canonical Flow records for arithmetic.
CSV now preserves `NA` as text and represents missing cells with None. Supply
`schema_overrides` when numeric-looking identifiers must remain text.
