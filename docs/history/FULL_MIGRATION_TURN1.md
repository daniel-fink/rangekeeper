# Full migration: Turn 1 foundations

> Historical design or implementation record. Names, commands and status below describe that checkpoint. Use the [current documentation](../README.md) for supported APIs.

Current intrinsic method ownership is defined in the [record boundary](../RECORD_BOUNDARY.md).

**Turn 2 update, 2026-10-06:** [Temporal equations, scenarios and policies](FULL_MIGRATION_TURN2.md)
now use Model/Specification 0.5.0 and Run 0.2.0. `ValueReference` addresses scalar
Values or owner-local Movement keys. The canonical calendar package is `duration/`;
`temporal` has no public alias. Finite Flow formulations, captured scenario replay,
exogenous declarative policies and the four numerical walkthroughs are implemented.
See [verification](../research/full-migration/turn2/README.md) and the
[upgrade guide](../LEGACY_UPGRADE_GUIDE.md). Turn 3 completes remaining consumers and
integrations; Turn 4 retires obsolete code after their acceptance gates.
The dated checkpoint descriptions below remain historical context.

Implemented 2026-10-04 on `acausal-modelling`, starting at `90c2e00`.
This is the first of **four implementation turns**. It extends the completed
scalar/domain work. It does not complete consumer migration or retire old APIs.
The user selected `calculations`, `model.duration`, and `formulations/flow.py`.
LinkML remains authoritative. Implementation and verification were completed
before the separately requested interim commit and push on 2026-10-06. The
checkpoint includes the date-only contract, PyXIRR integration, removal of Flow
semantic kinds, and Movement naming. No release is included. The latest
[verification](../research/full-migration/movement-naming/README.md) records 946 local
tests passing, all seven schema suites, typing and installed-package acceptance.

**Flow semantics correction, 2026-10-06:** semantic Flow kinds are removed.
The overall model logic owns quantity interpretation and operation selection.
See [Flow semantics and explicit operations](#flow-semantics-and-explicit-operations)
and the [verification report](../research/full-migration/flow-semantics/README.md).

## Delivered contract

Model schema **0.4.0** adds three exclusive Value kinds:

- `measurement`: a Measure reference and optional scalar Quantity.
- `flow`: a Measure reference and optional Flow. Its ordered movements carry stable
  local keys, dates or half-open Periods, optional numeric
  magnitudes, and Claim references. Missing content and missing movements remain
  unresolved; zero is known. There is no Flow basis or kind field.
- `property`: optional tagged `PropertyContent`, without a Measure. It preserves
  supported inert Python scalar/container types. Encoded null differs from missing
  content. Properties are not implicitly scalar mathematical operands.

Flow units must agree with its Measure. A Flow
uses calendar dates at day resolution and one event/period movement mode.
Period movements cannot overlap. Repeated event dates need distinct keys.
Claim references resolve within the
Model. All nested records remain generated, typed, immutable, and detached on export.

`Period`, `Span`, `Flow`, `Movement`, `PropertyContent`, and
`ContentEntry` come from LinkML. Handwritten modules implement behavior; they do
not repeat a field schema. Calendar months are calendar operations, not fixed
physical durations. `Period.start` and `Period.end` expose `datetime.date` and
serialize as ISO date strings. `TimePoint` was removed from this unreleased draft.

Each movement has a date, a Period, or both. A Period supplies coverage without a
redundant boundary date. Its optional `date` is an independently known payment or
observation date and may lie outside the Period. Valuation/display operations that
need a date require `timing="start"`, `"last_day"`, or `"end"` for undated Periods.
Recorded dates take precedence. Resolving a date does not change stored content.
Trimming and resampling select by coverage; aggregated periods do not invent a
payment date. Datetimes and timezone-bearing Flow coordinates are rejected.
Rich PropertyContent and provenance timestamps retain their separate contracts.

## Flow semantics and explicit operations

The user's 2026-10-06 decision restores the original RK principle: a Flow carries
ordered numerical quantities and their coordinates; the overall model logic
defines what they mean. Remove the draft `Flow.basis`, `FlowBasis`, constructor
`basis=` arguments and product `result_basis=` argument. Do not replace them with
`Flow.kind` or infer semantic kinds from units. `Value.kind="flow"` remains: it
selects the Value's content shape, not the interpretation of its numbers.

Units, alignment, date/period coverage, stable keys, missingness and immutable
records remain checked. The calculation chosen by the caller supplies the rule:

- `total` sums entries with unchanged units. `series.aggregate` adds aligned, compatible
  Flows. Neither claims that a numerical sum is meaningful for every model.
- `series.multiply` multiplies aligned magnitudes and units. Dimensionless scales
  such as percent convert to ratios. Physical dimensions, including time, remain.
  No result-kind declaration is required.
- `integrate` requires explicit exposure Quantities or a period day-count rule.
  It multiplies entries by those exposures and checks output-unit compatibility.
- `resample` requires a target grid and selected sum/first/last/min/max/mean
  reduction. Every mean requires an explicit observations/elapsed weighting
  choice. Empty target groups may be filled through `missing="zero"`; present
  unresolved entries remain unresolved. Partial period allocation stays explicit.
- Financial functions interpret their supplied entries as amounts to discount or
  value. Account argument names distinguish transactions, starting balance and
  per-period interest rates. Rates supplied as Flows must convert to dimensionless
  ratios. These are operation contracts, not stored Flow classifications.

The model author must select the correct operations for balances, receipts,
rates, price indices and growth factors. A successful unit check establishes
dimensional compatibility, not the meaning of the equation. Future formulations
must declare that logic; they must not reintroduce a hidden Flow classification.

This corrects the unreleased Model **0.4.0** draft. Its version remains unchanged.
Previously saved draft Flow payloads with `basis` fail the closed schema: update
them explicitly and preserve the revision history; no compatibility alias or
silent field removal is provided. The earlier reports describe their own inputs
and results. The subsequent [Movement naming change](#movement-naming) applies
the agreed vocabulary. The separately planned `duration` namespace move is pending.

## Movement naming

**Implemented 2026-10-06:** `model.flow.Movement` replaces `FlowSample`, and
`Flow.movements` replaces `Flow.samples`. A Movement is one numerical entry in
a Flow, associated with a date or period, with a stable local key and optional
evidence references. The overall model logic determines its meaning.

The LinkML class, generated records, Python property/constructor argument and
JSON/YAML field all use the new names. `movement_coordinate` replaces
`sample_coordinate`; private calculation helpers use `replace_movement` and
`Flow.replace(movements=...).check()`. Resolve a date with `movement.resolve(timing=...)`.
The fields `key`, `date`, `period`, `magnitude` and `claims`, their validation,
and the arithmetic remain unchanged. Movement does not add a semantic kind.
Statistical sampling remains distinct from Movements. The later [naming update](../RK_NAMING.md) places this operation at `distribution.sample(...)`, using the shared generated Distribution record.

This is a breaking correction to the unreleased Model 0.4.0 draft, with no
compatibility aliases or silent loader conversion. Old `samples` payloads fail,
including payloads which also contain `movements`. Rename the field explicitly
when upgrading a saved draft, preserve entry order and all entry fields, and
retain revision history. See the [upgrade guide](../LEGACY_UPGRADE_GUIDE.md) and
[verification](../research/full-migration/movement-naming/README.md).

## Ownership and interfaces

This tree records the delivered Turn 1 paths. The planned `temporal` → `duration`
rename is specified in [Duration namespace migration](#duration-namespace-migration).

```text
rangekeeper/
  model/
    duration.py       Period, Span                 [generated re-exports]
    content.py        encode(value) -> PropertyContent
                      decode(content) -> object              [detached copy]
                      validate_content(content) -> None
    flow.py           Flow, Movement
                      Flow.from_events(dates, magnitudes, *, units, keys=None) -> Flow
                      Flow.from_periods(periods, magnitudes, *, units, dates=None) -> Flow
                      Movement.resolve(*, timing=None) -> date
                      Flow.check(*, resolved=False, units=None) -> Flow
                      Stream(model, value_ids)
                        from_values(model, value_ids) -> Stream
                        values -> tuple[Value, ...]
                        flows -> tuple[Flow, ...]
                        select(*, value_ids) / merge(other) -> Stream
  duration/
    calendar.py       offset(value, *, frequency, count, month_end)
                      elapsed_days(start, end) -> int
                      year_fraction(start, end, *, convention) -> float
    period.py         Period.resolve / Period.check
                      make_period / make_periods / periods_between / cover
  calculations/
    series.py         align -> Alignment; Alignment.reduce -> Aggregation
                      aggregate / multiply / integrate / resample
  _behaviors/         field-free methods inherited by generated records
    flow.py           Flow.convert / scale / negate / total / trim / clean
                      difference / collapse / extent / trim_empty
                      Movement.number / coordinate / resolve
    distribution.py   Distribution.uniform / triangular / pert / symmetric
                      check / sample / cdf / mass
  calculations/
    projection.py     project_values / pad / project / allocate
    financial.py      calculate_pv(flow, *, rate, first_period=1) -> Flow
                      calculate_xnpv(flow, *, rate, valuation_date, day_count, timing) -> Quantity
                      calculate_irr(flow, *, guess=None, valuation_date=None,
                                    day_count, timing) -> IrrResult
    account.py        Account.calculate -> Account; Account.difference
    interval.py       Interval.length / split / subdivide
    dynamics/         calculate_trend / calculate_cycle / calculate_autoregression
                      accumulate_volatility / sample_noise / calculate_shock
  adapters/
    pandas.py         Flow to_frame/from_frame; to_series/from_series
                      existing Table to_dataframe/from_dataframe retained
    polars.py         Flow to_frame/from_frame
  migration/
    graph.py          convert_graph(text, *, revision_id, value_keys) -> ConversionResult
                      upgrade_model(data, *, revision_id) -> Model
    __main__.py       offline converter with fresh-directory report and Model output
```

Public methods return new values and do not mutate inputs. Model/record structural
failures use `ValidationError`; temporal, unit, alignment, and unsupported-content
checks raise `ValueError`/`TypeError` (unit parsing retains the domain unit error).
Stream lookup retains Model lookup errors. `convert_graph` reports supported
conversion failures in `issues` with `model=None`. CLI and codec filesystem errors
propagate. Only explicit random sampling advances the supplied Generator; only
codecs, stores, and the CLI write files. Calculation modules never publish Runs.

Dependency direction is records → domain/calendar/units → calculations → consumer.
Model validation may call calendar and unit checks. It imports no dataframe,
SciPy, solver, plotting, or service module. Polars is used inside key alignment
and grouped resampling. pandas is an explicit detached adapter. Base root imports
stay light. Existing broad distribution dependencies are removed only in Turn 4.

Financial arithmetic delegates to **PyXIRR**, including PV, XNPV, XIRR and day
counts. RK resolves dates, checks inputs/results, retains units and constructs
immutable results. `IrrResult` reports rate, NPV residual, supplied guess and
`method="pyxirr.xirr"`. The draft mandatory bracket and solver tolerance are
removed: no discovered consumer required bounded root selection. A guess is a
starting point, not a bound or proof of root uniqueness. The library may select
different roots for different guesses. Missing/nonfinite results and material
residuals fail explicitly. See [financial-library verification](../research/full-migration/financial-library/README.md).

PyXIRR anchors XNPV at the earliest payment. The wrapper uses PyXIRR PV to move
that value to the requested valuation date under the same convention. The four
supported day counts retain their meanings: Actual/365 Fixed, Actual/360,
Actual/Actual ISDA and European 30E/360. Empty Flow XNPV returns zero before
entering the library, whose 0.10.7 empty-date path panics. No new schema is involved.

The declaration/callable inventory is also retained in the source docstrings and
[API catalog](../research/full-migration/movement-naming/api.json). Each catalog entry identifies
its module, signature, return annotation, and docstring. The module tree above
identifies ownership; the [upgrade guide](../LEGACY_UPGRADE_GUIDE.md) supplies examples.

## Duration namespace migration

**Decision recorded 2026-10-05; implementation pending.** Use `duration` for calendar
operations as well as `model.duration` for records. The responsibility boundary
remains clear without a second name:

```text
rangekeeper/
  model/
    duration.py          # generated Period and Span records
  duration/
    __init__.py          # public calendar and period operations
    calendar.py          # date offsets, elapsed days and day-count fractions
    period.py            # period construction, coverage and boundary dates
```

**Implement this as the opening slice of Turn 2**, before adding formulations,
scenario composition or further canonical calendar consumers. It can be done now
as a separate code change, but it needs the same caller migration and verification.
Keeping it within Turn 2 avoids an extra turn. Waiting until Turn 4 would spread
the temporary `temporal` import through more new code. This documentation update
does not rename runtime files.

The current import name is occupied by the old `rangekeeper/duration.py`.
Both `duration` and `temporal` are lazy root exports. A folder rename alone would
redirect `rk.duration` to incompatible operations: old callers use pandas-backed
`Type`, `Period`, `Sequence` and `Span`, including inclusive date conventions.
The new records use date-only, half-open intervals. These APIs must not be mixed.

The 2026-10-05 source inspection found the following transition work. These are
static caller findings, not new execution results or a complete downstream audit.

| Current dependency | Migration placement |
| --- | --- |
| Eight runtime files: `flux.py`, `projection.py`, `formula/financial.py`, and `dynamics/{black_swan,cyclicality,market,noise,volatility}.py` call `rk.duration` | Redirect any retained old implementation to the private duration module during the opening slice; migrate behavior with its Turn 2 consumer work. |
| Old duration tests and `tests/models/{deterministic,probabilistic,flexible}.py` | Keep explicit access for old/new comparisons; move supported model behavior to canonical APIs during Turn 2. |
| Five source notebooks: `deterministic_scenarios`, `flexibility_intro`, `flexibility_under_uncertainty`, `market_dynamics`, and `drive_model_from_design` | Migrate numerical notebooks in Turn 2. Give any retained old caller an explicit private import until its migration; the design/service notebook retains its Turn 3 environment acceptance gate. |
| `model/flow.py`, `calculations/{series,financial}.py`, `adapters/pandas.py`, new tests/test models and `basic_dcf.ipynb` use `temporal` | Switch imports in the opening slice; update `model/duration.py` documentation and current upgrade examples with them. |
| Root exports, `tools/schema/typecheck.py`, `tools/schema/verify_install.py`, and the DCF notebook's import assertion | Update package paths and exports. The existing assertion that forbids `rangekeeper.duration` must instead detect the retained private legacy module. |

Perform the opening slice in this order:

1. Move the old implementation to `rangekeeper/_legacy_duration.py` and redirect
   retained internal/test/notebook callers explicitly. This is temporary private
   code for existing behavior and comparison tests, not a new supported consumer
   API. Record each remaining dependency in the retirement ledger.
2. Move `temporal/` to `duration/` and update canonical imports, lazy exports,
   type-check inputs, installed-artifact checks, docstrings and runnable examples
   together. Keep calendar signatures and semantics unchanged in this slice.
   Remove the public `temporal` export; do not add an alias or combine old and new
   classes under `duration`. `model.duration` and wire formats remain unchanged.
3. Verify the namespace change before building further Turn 2 features. Then
   migrate old behavior with its assigned consumers. Remove `_legacy_duration.py`
   as soon as its last retained caller and comparison requirement are resolved;
   Turn 4's retirement gate requires its removal. A missing host/service acceptance
   remains an explicit consumer gap, not permission to delete required behavior.

Acceptance for the opening slice:

- Run calendar/date, Flow, calculation and old/new equivalence tests. Check leap
  dates, month ends, half-open coverage, day counts and unchanged financial results.
- Run static type checks and the installed-wheel checks in fresh interpreters.
  Import `model.duration` and `duration` in both orders; confirm canonical use does
  not load `_legacy_duration`, pandas, plotting or solvers. Retain the existing
  financial-only dependency check with its corrected legacy-module assertion.
- Execute the DCF notebook and upgrade examples against that wheel. Scan active
  source for old public duration calls and `temporal` imports. Scan notebook code
  cells, not saved outputs. Historical reports and generated walkthrough copies
  remain historical; the full walkthrough rebuild is still Turn 4 work.
- Keep remaining legacy dependencies and unexecuted service consumers visible.
  A private import adjustment does not prove their semantic migration is complete.

No schema regeneration or new domain decision is required by the namespace move.
This date records planning only; earlier test totals remain evidence for their
original code and commands, not evidence that this move has passed verification.

## Behavior ledger and retirement gates

The [ledger](../research/full-migration/turn1/ledger.json) assigns **all 671 discovered
symbols across 41 modules** to the rows below. It includes private helpers and
fields, not 671 separate public promises. Each of 95 discovered consumer files has
a turn and source evidence. Parallel branch features remain in the ledger. Static
coverage is not proof of runtime equivalence; each row has an explicit acceptance
route. Empty/comment-only modules also have dispositions.

| ID / old responsibility | Destination and disposition | Evidence now / acceptance still required | Removal condition |
|---|---|---|---|
| D01 Graph, entity/relationship/assembly, catalog, errors, exports | Replace with `model`, `references`, `graph.View`, domain errors | Existing canonical graph/domain suites pass; migrate remaining Graph callers in Turn 3 | No supported caller needs old owners or mutation |
| D02 Characteristics, Measurement, Feature, Label | Replace with owner-local Values and rich properties | New Model/content/Flow tests, workflow evidence, converter; remaining Feature consumers Turn 3 | Persisted content and callers migrated |
| D03 definitions, classification, taxonomy | Retain useful semantics in schema `Definitions`, `Measure`, taxonomies | UUID identity and conversion tests; external mapping review Turn 3 | Definition consumers use canonical records |
| D04 provenance, state snapshots, Claims/reconciliation | Adapt to canonical provenance; retain inert historical claim content | Converter retains UUIDs, selection, source links and self-contained old wire payloads | All evidence remains readable without old classes |
| D05 revision/update | Replace by immutable Model revisions, Update, diff, stores | Existing atomic/revision conflict suites; external revision workflows Turn 3 | No old mutable update/revision calls remain |
| D06 Graph JSON | Explicit `migration.convert_graph`; canonical JSON/YAML codecs | Roundtrip and malformed conversion tests; CLI refuses overwrite | Supported stored documents converted or explicit historical reader retained |
| D07 View membership/traversal | Retain selection/composition through Model graph APIs | Existing hierarchy/view tests; graph notebooks Turn 3 | Same query/membership results accepted |
| D08 reduction/aggregation | Retain separated selection, reducer, aggregation, coverage | Canonical reduction tests; notebook/project totals Turn 3 | Equivalent contributor sets and quantities |
| D09 tables and dataframe conversion | Adapt to `graph.projection`, `table`, detached adapters | Existing Table APIs retained; Flow presence roundtrips; remaining presentation ports Turn 3 | No old table/series persistence dependency |
| C01 root Measure/unit registry | Replace domain Measures; retain useful algebra in `units` | Compatible conversion and product tests; currency explicit | All numerical/service callers stop using old registry |
| C02 duration/Period/Sequence/Span | Remodel as `model.duration` records + pure `duration` operations (currently `temporal`); explicit ordered tuples | Ten frequencies, leap dates, month ends, half-open spans, date-only rejection, day counts; namespace move opens Turn 2, remaining constructor convenience callers follow | Each old date convention mapped explicitly; no retained `_legacy_duration` caller or comparison dependency |
| C03 Flow/Stream ownership/construction | Remodel as immutable Flow Values; Stream pins Model revision | Multiple Values per Measure, nested immutability, selection/store tests | All consumers use canonical ownership; no mutable Stream storage |
| C04 arithmetic/alignment/reduction/cleaning | Rehouse in `calculations.series`; explicit missing and unit rules | Units/factor/rate integration, partial coverage, weighted resampling, trim/extrema tests | Old/new consumer results accepted; implicit time stripping removed |
| C05 extrapolation/projection/padding/allocation | Rehouse in `calculations.projection`; symbolic builders Turn 2 | Known-path and mass conservation tests, DCF notebook | Dynamic/financial consumers use explicit origin/support/timing |
| C06 distribution evaluation/sampling | Rehouse in immutable calculation Distribution | Explicit Generator, point-mass shape, parameter and boundary tests | Scenario consumers carry realized inputs and random lineage in Turn 2 |
| C07 PV/NPV/IRR/accounts | Rehouse in `calculations.financial/account`; governing builders Turn 2 | Migrated finance tests; independent residual oracle; 18 account parity cases | Known/symbolic consumer acceptance and documented corrections |
| C08 trend/cycles/volatility/noise/shock | Pure kernels delivered; composition moves to `scenarios` in Turn 2 | Kernel tests and 3 legacy cycle comparisons; full stochastic notebooks pending | Reproducible realized paths and metrics accepted |
| C09 intervals/segmentation/type hierarchy | Interval arithmetic delivered; persistent Segment/Type semantics move to canonical graph/taxonomy in Turn 3 | Interval conservation tests; segmentation consumer examples pending | No segment/hierarchy capability silently dropped |
| F01 market composition/policy callbacks | Remodel as scenarios/policies and explicit investigation/execution in Turn 2 | Pending; no claim that numerical kernels solve policy questions | Callback consumers replaced, information timing and hindsight tested |
| F02 Speckle/host API | Rehouse under adapters in Turn 3 | Live services excluded; Rhino/Grasshopper environment acceptance pending | Actual transport and host acceptance, not import-only proof |
| F03 formatting/plotting/reprs | Rehouse under presentation adapters in Turn 3 | DCF table outputs retained; general plot/format methods pending | All supported notebook/project presentations migrated |
| F04 root helpers/update_class/commented space | Retire after notebook refactor and final exports scan in Turn 4 | DCF no longer patches classes; other sources pending | No remaining consumer or capability depends on helpers |

## Four-turn sequence and review

1. **Foundations, numerical kernels, first consumers** — this turn. The evidence
   below covers records, arithmetic, storage, a built-wheel DCF notebook, synthetic
   workflows, format conversion, and the behavior ledger. This is a reviewable
   checkpoint, not a mandatory new approval gate.
2. **Temporal governing mathematics and scenario/policy consumers** — first complete
   the [duration namespace migration](#duration-namespace-migration), then extend
   explicit expression/reference contracts, implement `formulations/{flow,growth,
   financial,account}`, capability checks and independent result acceptance; compose
   seeded scenarios and explicit policy information/action rules. Migrate the
   remaining numerical/temporal notebooks and deterministic/probabilistic/flexible
   test models. A calculation function is not automatically a solver operator.
3. **Remaining graph/source/service/host consumers** — migrate graph notebooks,
   segmentation, Projects YAML/notebooks and required workbench/layout features.
   Rehouse service and presentation code. Execute each supported consumer in its
   actual environment. Absent credentials/hosts remain named acceptance gaps.
4. **Retirement and delivery verification** — remove superseded modules/exports
   after their ledger gates pass; narrow dependencies; rebuild documentation;
   rerun all acceptance from installed artifacts and test the upgrade guide.

Ask for review only when an actual example exposes an unresolved domain choice,
material capability loss, or unavailable external acceptance. Routine factoring,
validation, and test corrections supported by independent evidence need no new
blanket permission. There are no unresolved Turn 1 domain decisions.

## Limits

Temporal Flow unknowns, indexed equations, scenario records, policy execution,
segment records, remaining notebooks, Projects, layout ports, and service/host
integration are **not delivered by Turn 1**. Scalar Specification roles remain
measurement-only. The new core coexists with old runtime modules until their
consumers move. Tracked old walkthrough build outputs remain historical until the
whole walkthrough is rebuilt in Turn 4. See the [date-only verification](../research/full-migration/date-only/README.md)
and [original Turn 1 report](../research/full-migration/turn1/README.md) for exact results and the HTML preview limitation.
