# Full library and consumer migration: review proposal

**Turn 3 update, 2026-10-06:** [Remaining consumers and design integrations](FULL_MIGRATION_TURN3.md)
implements the canonical workbench/layout port, all three Projects source builds,
Speckle mapping, both design walkthroughs and generated C# Rhino 8 authoring.
See [current acceptance](research/full-migration/turn3/BASELINE.md),
[consumer register](research/full-migration/turn3/CONSUMERS.md), and
[Turn 4 retirement gates](research/full-migration/turn3/RETIREMENT.md).
The Windows official connector gate remains open. Hypar support is retired;
the future Browser/outliner importer remains on hold. Dated checkpoints below
remain historical evidence and do not override this current scope.


**Turn 2 update, 2026-10-06:** [Temporal equations, scenarios and policies](FULL_MIGRATION_TURN2.md)
now use Model/Specification 0.5.0 and Run 0.2.0. `ValueReference` addresses scalar
Values or owner-local Movement keys. The canonical calendar package is `duration/`;
`temporal` has no public alias. Finite Flow formulations, captured scenario replay,
exogenous declarative policies and the four numerical walkthroughs are implemented.
See [verification](research/full-migration/turn2/README.md) and the
[upgrade guide](LEGACY_UPGRADE_GUIDE.md). Turn 3 completes remaining consumers and
integrations; Turn 4 retires obsolete code after their acceptance gates.
The dated checkpoint descriptions below remain historical context.

Prepared 2026-10-03 against RK `90c2e00ba7b942a8830960e3df3f3ff616f30fa1`.

The goal is now to account for **all remaining older functionality**, migrate
every supported consumer, and remove the old architecture. Moving files or
passing the current scalar tests is not sufficient. Each behavior needs a
destination, a stated contract, consumer evidence, and an acceptance check.

**Status, 2026-10-04:** the approved four-turn migration is under implementation.
[Turn 1 foundations](FULL_MIGRATION_TURN1.md) now delivers schema duration/Flow/rich
content, calendar and calculation kernels, adapters, explicit conversion, a migrated
DCF notebook and synthetic workflows. `calculations`, `model.duration`, and
`formulations/flow.py` are selected names. The sections below retain the original
full scope; implemented signatures and evidence in Turn 1 supersede proposals.
Scenario/policy, remaining consumer and retirement work remains in Turns 2–4.

**Namespace decision, 2026-10-05:** the target calendar package is `duration`,
alongside records in `model.duration`. Current code still uses `temporal`.
The [migration sequence](FULL_MIGRATION_TURN1.md#duration-namespace-migration)
opens Turn 2, before new formulations and scenario consumers. The target paths
below reflect this decision; they do not claim the rename is implemented.

Steps 1–5 and 6A–D remain delivered. The earlier plan deferred numerical and
temporal integration; the requested full refactor brings it into the migration
programme. 6E consumer acceptance and 6F retirement now depend on the applicable
work below. A supported consumer awaiting a capability is incomplete, not an
acceptable permanent exception to full completion.

## Engineering review and when Daniel's input is needed

**Flow decision, 2026-10-06:** the overall model logic owns numerical meaning.
Flows carry no semantic kind/basis. The former classification proposal is replaced
by [explicit operations](FULL_MIGRATION_TURN1.md#flow-semantics-and-explicit-operations).
The updated boundaries below reflect that decision.

**Naming, 2026-10-06:** a Flow contains `Movement` records through `movements`.
This replaces the draft `FlowSample`/`samples` names in the schema and Python API.
The [naming contract](FULL_MIGRATION_TURN1.md#movement-naming) records migration
and verification. Statistical sampling retains its separate terminology.

The R1–R6 items below are engineering work and review material, not a queue of
mandatory user approvals. No unanswered user question currently blocks the next
design work. The implementer must inspect callers, specify semantics, run probes,
select supported implementations and propose coherent APIs. An incomplete design
is not itself a reason to ask Daniel to decide it.

Ask for input only when evidence leaves a concrete domain ambiguity or a material
scope tradeoff: for example, a source value could mean a period amount or a rate,
two active consumers require incompatible defaults, or a capability cannot be
preserved without a substantive change. Show the exact example, alternatives,
result difference and a recommendation. Mechanical moves, dataframe-engine
evaluation, ordinary naming/factoring and test execution need no separate gate.

| Review | Concrete material to review | Recommendation / open decision |
| --- | --- | --- |
| R1 — coverage | Every legacy behavior and active consumer, including parallel branches, with examples | Preserve useful behavior by default. Correct defects explicitly. Do not drop supported behavior merely because tests are absent; a proposed loss of capability requires a concrete user decision. |
| R2 — temporal meaning | Small dated-movement, period-rate and balance examples, including missing and zero values | Distinguish movements, rates and point-in-time balances. Use explicit calendar and sampling rules. Review the exact record shape and unresolved-element semantics before schema changes. |
| R3 — ownership and API | Proposed package tree, dependency rules and before/after examples | Canonical content in `model`; equation builders in `formulations`; concrete calculations in `calculations`; pure calendar operations in `duration` (currently `temporal`); external representations in adapters. The names listed here are selected. |
| R4 — mathematical capability | One table separating known-data calculation, symbolic construction, solver support and independent acceptance for each operation | Do not promise that moving a numerical method makes it acausal. Preserve a numerical path where appropriate; add supported symbolic paths explicitly. Reject unsupported unknown-dependent operations. |
| R5 — scenarios and policies | Seeded scenario example; a decision made from available observations; comparison with a hindsight policy | Separate exogenous sampling from solving, persist realized inputs, make observation time and action effects explicit. Select the policy contract before replacing arbitrary callbacks. |
| R6 — migration proof and retirement | Old/new result comparisons, explained differences, installed notebook/project runs, upgrade guide and removal list | Require semantic equivalence or an accepted correction, not byte-identical files. Missing service/host checks remain open acceptance gates. |

Develop these items in order, with R2/R3 considered together. R6 is verification
per consumer and again at final retirement. Package names alone do not settle
schema/API details, but the implementer should complete those details from the
stated requirements rather than wait for blanket approval. Daniel can review and
steer the concrete design as it develops.

## Evidence and scope that the older tables missed

The [static inventory](research/full-migration/inventory.json) records source
hashes, symbols, consumer reference locations and checkout states. The
[symbol list](research/full-migration/SYMBOLS.md) includes private methods and
fields as well as public operations. These are discovery evidence, not proof
that every listed method works. The script reads code without importing it.

In addition to the old Graph and numerical modules:

- `src/examples/workflow/accommodation` and `equipment` were version-1 examples
  at discovery. Turn 1 migrated and executed both using canonical property Values
  and source evidence. 6C/6D alone had not certified them.
- The seven source notebooks are directly under `walkthrough/`. The tracked
  `_build/html/_sources` and `_build/jupyter_execute` copies are generated output,
  not another fourteen source notebooks. Rebuild or deliberately remove stale
  generated copies when their sources migrate; do not edit them as sources.
- `src/tests/models/{linear,linear_graph,deterministic,probabilistic,flexible}.py`
  also contains consumer implementations. Passing a top-level import scan does
  not establish that their instance-method use has migrated.
- The Projects checkout is `feature/mandarin-assembly-layout` at
  `5725cc02748ace15e390c8dcea2c5d69185d67c9`. Both projects are environment-only
  YAML consumers, not project runtime packages. Their current tests and YAML
  still use old Graph/workflow contracts and Features.
- Mandarin's current notebook calls `graph.workflow.workbench` and
  `layout_review`. Those capabilities live in the separate RK worktree at
  `4e5aec42f16a18c4d715f5a2a1b879d98e0f71e3`, branch
  `feature/assembly-layout-constraints`. That branch also contains checked layout,
  editable presentation, solver adapters and layout tests. Port the required
  behavior explicitly; do not merge the old domain wholesale or assume the
  acausal checkout already contains these features.
- Grasshopper C# source exists. No tracked Hypar source was found. Speckle and
  Rhino/Grasshopper acceptance needs the corresponding service/host environment.

This is a bounded inventory of available repositories. An upgrade guide can
support undiscovered downstream callers; it cannot certify code that was never
available or executed. Add any additional supported consumer to the register
before declaring full completion. Preserve archived project code and recovery
snapshots; use pinned historical environments if comparison requires execution.

## Proposed responsibility boundaries

| Responsibility | Content / operation | Proposed owner | Must not own |
| --- | --- | --- | --- |
| Persistent temporal content | Dates/periods, values, units, missingness and provenance references; no Flow semantic kind | LinkML records, generated immutable access, public re-exports in `model/duration.py` and `model/flow.py` | dataframe objects, mutable random generators, plotting objects or executable callbacks |
| Calendar operations | Build periods, offset dates, measure spans, align boundaries and compute declared day-count fractions | `duration/calendar.py`, `duration/period.py` after the opening Turn 2 rename | Solver state, Model revision storage or implicit monetary conventions |
| Governing mathematics | Expressions, Constraints, indexed references and Formulation-local/shared Values | Existing `model/expression.py`, `model/formulation.py`, plus reviewed schema extensions | Calculations hidden inside record constructors |
| Equation construction | General flow, growth, discounting and account equations with explicit bindings | `formulations/{flow,growth,financial,account}.py` | Automatic solve, filesystem writes or hidden assumptions about known/unknown roles |
| Numerical calculation | Arithmetic, resampling, distribution evaluation, financial metrics and recurrences on known inputs | `calculations/{series,distribution,projection,financial,account,interval}.py` | New authoritative record shapes, source interpretation or solver publication |
| Scenario generation | Compose trend/cycles/noise/shocks and sample reproducible realizations | Proposed `scenarios/{sampling,market}.py`, supported by `calculations/dynamics/` | Sampling inside expression evaluation or implicit changes to solver unknowns |
| Policy evaluation | Observe permitted history, decide actions, apply changes and retain decision evidence | Proposed `policies/`; investigation contracts in `specification`, execution in `execution` | Arbitrary serialized Python or reading future outcomes unless explicitly evaluating hindsight |
| External representation | pandas conversion, plotting, tables, exports, service transport and viewers | `adapters`; existing generic `table` and graph projections | Authoritative copies of Model data or schema-specific financial rules |
| Persistence and history | Versioned documents, explicit upgrades, immutable revision writes | Existing `io`, `model.update`, `model.diff`; separate migration tooling | Transparent interpretation of old Graph JSON as new Model JSON |

The proposed package tree is a responsibility map. Create only files justified
by an implemented contract; do not create empty frameworks.

```text
rangekeeper/
  model/
    duration.py             # schema-derived temporal content and access
    expression.py           # declared mathematics
    formulation.py          # Formulation records, not financial algorithms
  duration/
    calendar.py             # dates, calendar offsets, day-count operations
    period.py               # period/span construction and explicit boundaries
  calculations/
    series.py               # known-value arithmetic, alignment and resampling
    distribution.py         # PDFs/CDFs/interval mass and explicit sampling
    projection.py           # additive/multiplicative factors and allocation
    financial.py            # PV, dated NPV and IRR calculations
    account.py              # evaluated balance/interest recurrence
    interval.py             # interval partition arithmetic
    dynamics/               # trend, cycles, volatility, noise, shocks
  formulations/
    flow.py                 # general flows, including non-monetary quantities
    growth.py
    financial.py
    account.py
  scenarios/
    sampling.py
    market.py
  policies/                 # reviewed decision contracts and pure evaluation
  adapters/
    pandas.py
    formatting.py
    plotting.py
    speckle/
    cytoscape/layout/       # port verified presentation/layout capabilities
  workflow/
    workbench.py            # port source-workflow inspection/build progress
    layout_review.py        # orchestration of source and presentation review
  graph/                    # Model views and algorithms only after retirement
  specification/            # assignments, solve roles and policy investigation
  execution/                # capability checks, solve/evaluate, acceptance
  run/                      # finalized evidence, extended only as required
  io/
  units.py
```

Dependency rules:

1. Generated records and `model` must not import pandas, Polars, SciPy, plotting, service
   clients, numerical implementations or solver backends.
2. `duration` (currently `temporal`) and `units` provide explicit operations with no storage or solve
   effects. Calendar periods are not implicitly interchangeable with fixed
   physical durations.
3. `calculations` may consume canonical immutable content and use arrays internally.
   Returned pandas/NumPy objects are detached. Handwritten runtime results may
   hold computation state; they must not repeat the persistent field schema.
4. `formulations` constructs canonical mathematics from explicit arguments.
   It may use pure calendar/unit operations and fixed-coefficient calculations.
   It cannot numerically replace an expression that still depends on an unknown.
5. `execution` owns backend dispatch and publication. Builders and numerical
   routines neither certify a Run nor save output revisions on their own.
6. Adapters own representation dependencies. Layout solver dependencies remain
   optional presentation dependencies; they do not replace the selected domain
   execution backend.
7. Classes need coherent state or invariants. Pure operations use verb-led
   functions. Keep named constructors, explicit results and readable composition.
   Avoid a wrapper per generated record, attribute magic, root `rk.*` cycles and
   cross-module private-method calls.

### Why `calculations`

The user selected this name for operations on known data. It does not indicate
that these modules solve unknowns or select among indeterminate solutions. Declared
mathematics belongs in `model.expression`/`model.formulation`, construction helpers
in `formulations`, and solving/acceptance in `execution`.

### Flow units and a shared time axis

Flows represent quantities of any appropriate kind, including mass, energy,
area, counts, dimensionless factors and money. Sharing a time axis aligns movements;
it does not give every sampled value an extra time unit.

The user-confirmed composition intent is heterogeneous Streams with compatible
sums and meaningful products. Turn 1 implements these rules for known data:

- Summation requires compatible units, an explicit common output unit, compatible
  temporal meaning and aligned movements. Do not implicitly exchange currencies or
  sum balances across time as though they were movements.
- Products multiply value units normally. A pricing factor sampled monthly is
  dimensionless; multiplying it by rent does not multiply the time axis.
- A rate becomes an amount through an explicit duration/exposure operation under
  a declared calendar convention. Generic multiplication does not remove time.
- Distinguish a dimensionless price factor from a growth rate per year. Applying
  a growth rate requires its compounding/integration rule and elapsed time.

| Example | Result |
| --- | --- |
| Monthly factor `1.10` × monthly rent rate `100 AUD/month` | `110 AUD/month` |
| Monthly factor `1.10` × recorded period amount `100 AUD` | `110 AUD`, on the same axis |
| Price `20 AUD/(m²·month)` × area `50 m²` | `1,000 AUD/month` |
| Rate `100 AUD/month` × duration `2 months` | `200 AUD` |
| Energy price `0.30 AUD/kWh` × consumption `100 kWh` | `30 AUD` |

Time powers are not inherently meaningless: velocity squared has units m²/s².
If a particular stream product creates an unwanted time power, inspect operand
meaning and units. Deleting that power cannot establish a valid operation.

The [unit probe](research/full-migration/unit-probe.json) reproduces the helpers
called by `Stream.product`: dimensionless × AUD/month becomes AUD after the old
time-removal step, without applying a duration. A product of two rates with time
exponent -2 raises `NotImplementedError`. This could approximate a one-unit-period
calculation in some old callers, but is not a general unit rule. The existing
`test_stream_aggregation` asserts removed units; it does not prove integration
over actual period lengths. Caller intent still needs characterization before a
runtime change. The probe does not certify Stream alignment/resampling.

### pandas versus Polars

Turn 1 uses Polars for key alignment and grouped reductions, with detached pandas
adapters. The prior evaluation principle remains: do not retain pandas
solely on the assumption that Polars cannot resample. Polars supports dynamic
time grouping and upsampling; pandas supplies Period/PeriodIndex and extensive
calendar-offset behavior. See the official [Polars resampling guide](https://docs.pola.rs/user-guide/transformations/time-series/resampling/)
and [pandas time-series guide](https://pandas.pydata.org/docs/user_guide/timeseries.html).

Polars uses explicit columns instead of pandas-style indexes and offers lazy
query optimization. Its null/NaN distinction and absence of automatic index
alignment must be handled deliberately. These facts come from its official
[pandas migration guide](https://docs.pola.rs/user-guide/migration/pandas/).
Also, dynamic grouping does not create rows for empty windows automatically;
see [group_by_dynamic](https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.group_by_dynamic.html).

Recommendation: keep canonical duration/Flow semantics independent of either
engine, and compare one representative implementation in each before selecting
the default. Avoid building two complete runtimes or a general backend framework.
The comparison must cover period-end dates, month/year/multi-year boundaries,
empty windows, null versus zero, duplicate dates, alignment, rate/factor/amount
resampling, joins, plotting/export, conversion costs, runtime and memory on actual
consumer-sized data. Null handling must not be inherited silently from either
library. NumPy kernels may remain useful for recurrences irrespective of the
dataframe choice.

No Polars benchmark has been run. It is not installed in the inspected scalar
runtime (pandas 2.3.2, Pint 0.24.4). Choose from measured suitability; do not promise
a speedup or require Daniel to choose the engine before this investigation.

## Temporal contract: decisions before writing the schema

Flow stores ordered quantities, dates/periods and evidence. The overall model logic
determines whether an array means receipts, balances, rates or something else,
and selects the appropriate calculations. No Flow kind supplies that interpretation.

| Question | Recommended starting contract | Required example / check |
| --- | --- | --- |
| What does each entry mean? | The overall model logic owns interpretation; no stored Flow kind or basis. Operations specify their arithmetic and assumptions | The same Flow can be summed or reduced to a closing observation by explicit choice; means require weighting and integration requires exposure |
| What is the time axis? | Distinguish dated events, observation instants and bounded periods. Persist actual coordinates; frequency alone is insufficient | Irregular dates, two entries on one date, month ends, leap years, multi-year periods, fiscal anchors |
| What are the boundaries? | State inclusion, observation date and rate application timing explicitly. Prefer half-open period intervals internally, with explicit conversion from old inclusive spans | Adjacent periods neither overlap nor leave gaps; old period-end movements map to the same intended economic dates |
| What calendars are supported? | Date-only Gregorian calendar, with one day as the smallest resolution. Period movements store coverage; independent dates are optional. Reject Flow datetimes/timezones | Year/month/week anchors, leap years, partial periods, explicit valuation dates and datetime rejection |
| What is missing? | Separate absent series, unresolved quantity, missing movement and known zero. No blanket `fillna(0)` | All-missing aggregate remains unresolved; partial coverage is visible; observed zero remains present |
| How do values align? | Exact axis match by default. Require explicit union/intersection/resampling and fill policy when they differ | Unequal ranges, duplicate/unsorted dates, gaps, empty series and nonmatching rate calendars |
| How are units applied? | Declared Measure units and explicit conversion; integrate rates using explicit durations/exposure | AUD/year × a specified fraction of a year; unit-compatible sums; no implicit FX or dropping `[time]` |
| Who owns the content? | A Value owns its temporal payload; UUIDs identify Values independently of names. Prefer a Stream as a view/group of referenced Values, not duplicated persistent Flow contents | Same Value in several views has one owner; duplicate display names cannot replace identity |
| What is an Account? | Start with named balance/movement Values governed by an account Formulation; add an Account record only if a distinct persistence invariant requires it | Initial balance, transactions, interest and closing balance retain separate meanings and provenance |
| How are histories stored? | Schema-defined immutable content, explicit version changes and ordered serialization. Review inline arrays versus immutable referenced datasets against real sizes | JSON/YAML round trips, no array aliasing, movement order, revision conflict checks, bounded large-series memory |
| How are elements assigned or solved? | Specify element identity, shape, assignment precedence and publication before enabling temporal execution | Some movements fixed and others unknown; partial missingness; residuals identify both Value and coordinate |

Whole-value and movement-level provenance also need a decision: an aggregate must
identify its inputs, and source-cell evidence must not disappear when observations
are grouped into a series. Avoid adding a UUID to every movement unless independent
movement identity is required. Array offsets alone must not become stable identity
if inserting a date would change their meaning.

The review should include a small cashflow worked by hand, a stock balance, and
a rate converted over unequal periods. Those examples become schema fixtures and
independent numerical oracles. Exact field definitions, validation errors and
omission/null rules are an R2/R3 deliverable, not settled by this proposal.

## Disposition of every older module group

Paths below are relative to `src/rangekeeper/`. The symbol inventory expands each
row into constructors, methods and fields. Every symbol must be assigned to a
behavior-contract row before removal, including aliases and deprecated names.

| Current surface | Refactor and destination | Behavior that must be checked |
| --- | --- | --- |
| `graph/graph.py`, `_catalog.py` | Replace ownership with `Model` and its indexes; adapt any remaining useful lookup/query behavior | UUID lookup versus code/name search, canonical uniqueness, missing/wrong-type references, lookup within one revision |
| `graph/entity.py`, `relationship.py`, `assembly.py` | Generated `model` records; membership/traversal in `graph` | Separate Assembly storage, valid endpoints, sharing, cycles, ordering and multiplicity; distinguish an object from a viewer occurrence |
| `graph/characteristics.py` | Labels and identified owner-local Values; add reviewed rich-content variants where needed | Multiple Values per Measure, Feature meanings and types, zero/missing, identity and source lineage; no silent conversion to strings |
| `graph/classification.py`, `taxonomy.py`, `definitions.py` | Schema-derived definitions plus public lookup/validation | Parentage, scope, duplicates and classification identity; retained category meaning |
| `graph/provenance.py` | Canonical `model.provenance`; retain current transient `evidence` where it describes source processing | Claim derivation, location traversal, reconciliation, conflict status, selection and Fact targets |
| `graph/revision.py`, `update.py` | Full-Model revisions, `model.diff`, atomic `model.update`, `io` stores | Failed edit leaves input unchanged; deterministic content comparison includes mathematics; lineage and business IDs survive |
| `graph/adapter/json.py` and its exports | New documents use `io`; old documents use an explicit offline upgrade path | Version detection, identity map, unmapped-content report, provenance, no overwrite, no old-code dependency in the new runtime |
| `graph/legacy/view.py`, `legacy/reduction.py`, `graph/table.py` | Retire after callers use current Model View/Hierarchy/Reduction/projection and shared `table` | Direction, filters, scope/coverage, overlaps, reducer choice, repeated memberships, row identity and missing cells |
| `graph/__init__.py`, `graph/errors.py`, `graph/adapter/__init__.py`, `graph/legacy/__init__.py` | Remove old exports and errors only when their implementations/callers are resolved | Public import inventory, typed examples and installed-wheel tests; errors have documented replacements |
| `measure.py` | Retire old Measure/QuantityKind/AggregationRule domain shape. Consolidate required registry/conversion operations in `units` | Percent scaling, currencies, count dimensions, quantity compatibility and explicit reducers. Review `remove_dimension`, not merely rename it |
| `flux.py: Flow` | Split content/access, calendar conversion, `calculations.series`, `calculations.financial`, builders and adapters | Constructors, copying/mutation, negate/diff/total/collapse, resample/trim/clean, PV/NPV/IRR, names/units and empty-series behavior |
| `flux.py: Stream` | Group/view of canonical Values; explicit alignment/reduction; detached pandas export | Duplicate names, different units/frequencies, extract/sum/product/min/max/total, merge/extend/collapse, no accidental double count |
| `duration.py: Type, Period, Sequence, Span, measure, offset` | Generated persisted records in `model.duration`; pure behavior in `duration/` after the opening Turn 2 rename; retained old behavior temporarily in private `_legacy_duration.py` | Inclusive bounds, negative spans, leap/calendar boundaries, end stamping, partial periods and all existing frequencies; remove dependence on pandas alias spellings from persisted meaning; remove private old code after caller and comparison gates pass |
| `distribution.py: Form, Symmetric, Uniform, Triangular, PERT, Type` | `calculations.distribution`; schema-backed distribution parameters only where persisted scenario definitions require them | Parameter validation, interval mass/CDF, degenerate distributions, return shape, random-generator ownership and support bounds |
| `extrapolation.py: Form, StraightLine, Recurring, Compounding, Dynamic, Type` | Concrete factors in `calculations.projection`; corresponding mathematics in `formulations.growth` | Additive slope versus multiplicative factor, origin index, repeated values, supplied-path length, negative rates and overflow |
| Root `projection.py: Projection, Extrapolation, Distribution, Padding` | Temporal numerical projection/allocation; keep distinct from graph table projection | Bounds, NIL/UNITIZE/EXTEND semantics, period-count alignment, density mass and no unexplained endpoint duplication |
| `formula/financial.py: Account` and package exports | Evaluated recurrence in `calculations.account`; equations in `formulations.account`; canonical output Values | Simple/compound/capitalized interest, advance/arrears, initial negative balance, overdraft increments, irregular rates and `diff`; not all modes are automatically supported by the current solver |
| `dynamics/trend.py` | Pure growth/price calculation under `calculations.dynamics`; scenario construction outside the kernel | Initial value versus initial price factor, capitalization assumptions, per-period growth and seeded parameter draws |
| `dynamics/volatility.py` | Explicit-innovation recurrence and explicit sampling | Autoregression, mean reversion, innovation scale, initial conditions, reproducibility and worker independence |
| `dynamics/cyclicality.py` | Pure symmetric/asymmetric wave kernels; scenario parameter construction | Period, phase, amplitude, asymmetry, convergence/bounds, per-sample timing and parameter distributions |
| `dynamics/noise.py` | Observation-noise kernel and explicit scenario sampling | Noise applies to levels rather than accumulated increments; ordering and sample counts |
| `dynamics/black_swan.py` | Shock kernel and declared event-generation policy | First-event behavior, likelihood threshold, dissipation, impact parameter and horizon. Determine whether observed behavior matches the intended description before preservation |
| `dynamics/market.py`, `dynamics/__init__.py` | Compose kernels in `scenarios.market`; emit recorded exogenous paths | Rent/asset paths, noise/shocks, implied capitalization rates and returns, lag/index alignment and scenario identity |
| `policy.py` | Explicit policy interface, observation scope, actions and evaluation evidence | Condition/action semantics, decision timing, no look-ahead, reproducibility, unchanged input revisions, terminal/no-action cases |
| `segmentation.py: Type, Characteristic` | Map reusable category semantics to Definitions/Classifications when equivalent; domain-specific category helpers only if needed | Hierarchy, duplicate/cycle handling, mutation of parent/children, meaning of use/tenure/span/type |
| `segmentation.py: Interval, Segment` | Partition arithmetic in `calculations.interval`; persistent segments as reviewed domain objects/relationships when independently meaningful; display in adapters | Bound closure, split/subdivide, sum of extents, zero/negative inputs, child ordering, inherited characteristics and reporting |
| `api.py: Speckle` | `adapters.speckle`, separate transport and Model mapping | Authentication separate from pure mapping, duplicate object resolution, nested/shared objects, stable IDs, unsupported geometry/content and host contract version |
| `format.py` and `rgba_from_cmap` | `adapters.formatting` and plotting | Locale, currency/percent rounding, scalar/vector shape, missing-value display, dates, colors and detached dataframe formatting |
| Root `update_class` | Replace notebook class patching with ordinary functions, composition and equation builders | Preserve notebook teaching intent and scenario behavior; eliminate dependence on execution order and hidden patched methods |
| `space.py` | Remove commented prototype after confirming there is no live API; express actual future spatial semantics through the domain contract | Import references only; commented classes are not delivered functionality |
| Root `__init__.py`, dependency declarations | Export new supported APIs; remove legacy lazy exports; separate optional capabilities and development dependencies | Minimal base install, optional numerical/plotting/integration extras, supported Python versions, package resources and useful missing-extra errors |

Current `metadata`, `references`, `diagnostics`, `errors`, `units`, `table`,
`evidence`, `operation`, `validate`, shared record/encoding helpers, and the new
domain/graph/workflow/adapters are not retirement candidates merely because they
are at the root or reuse older code. Review their interfaces and dependencies,
and retain shared behavior with a current purpose.

## Behavior review: examples where preservation is not a copy operation

These are observed source behaviors or review candidates, not newly reproduced
bug reports:

1. `Flow.from_sequence` stamps movements at period end. Preserve intended payment
   timing when introducing explicit periods; do not shift a payment by a period.
2. `Flow.pv` discounts by period number starting at one. `npv` and `irr` call dated
   XNPV/XIRR. Keep these distinctions visible in names, rate basis and examples.
3. `Flow.from_projection` can draw a random input and then discard a Pint
   Quantity's unit metadata before constructing the output. Separate sampling,
   unit conversion and projection into explicit operations.
4. `Flow.resample` uses different rules for ticks and calendar offsets, including
   forward filling and endpoint adjustments. Define the new rule from temporal
   meaning; characterize old outputs before changing them.
5. `Stream.product` removes a time dimension. Replace any intended rate integration
   with an explicit duration/exposure operation; do not silently remove units.
6. `Stream` indexes columns and units by display name, and reductions use pandas
   missing-data defaults. Introduce stable keys and explicit coverage rules.
7. `distribution.Form` uses `all(parameters)` in a range guard. Add independent
   invalid-input examples; matching this check would not prove correct validation.
8. `Volatility` creates random samples internally. `BlackSwan` stores an impact
   parameter whose use needs review across the generator and market composition.
   A seeded numerical path must expose every random input and applied parameter.
9. `Account` distinguishes simple, compound and capitalized interest, clips some
   balances and reports overdraft movements. Review these rules separately; one
   generic balance formula is not a complete replacement.
10. Existing numerical tests include the known residual expectation failure, and
    some scenario tests emphasize construction/printing. Add independent result
    assertions rather than treating a successful test process as full parity.

A defect correction must have an old example, an explanation of the intended
behavior, a new expected result and a consumer-impact note. Old bugs need not be
kept, but changed outcomes must never be disguised as equivalent results.

## Concrete interface review, using Flow as the first worked slice

The exact signatures will follow R2. The proposed division is already testable:

| Old usage | Proposed operation shape | Contract to document |
| --- | --- | --- |
| `Flow.from_sequence(...)` | `adapters.pandas.from_series(...) -> Flow` with explicit coordinate/unit inputs | Validates shape and copies data; no stored pandas references or implicit end-date inference |
| `flow.resample(frequency)` | `calculations.series.resample(flow, *, periods, reduction, missing, weighting) -> AggregateResult` | Explicit reduction, mean weighting, alignment and coverage; input immutable; no semantic kind gate |
| `stream.sum()` | `calculations.series.aggregate(series, *, axis, reducer, units, missing) -> AggregateResult` | Result includes quantity and coverage; no implicit name-keyed identity |
| `flow.npv(rate)` | `calculations.financial.xnpv(series, *, rate, valuation_date, day_count) -> Quantity` | Known inputs only; explicit units/rate basis; invalid dates or rate domains reported |
| Account construction that calculates immediately | `calculations.account.calculate(...) -> AccountResult` | Pure evaluated recurrence; named output series; no Model mutation |
| The same account as governing mathematics | `formulations.account.build(...bindings..., ...timing...) -> Formulation` | Builds declarations only; stable references; compiler separately checks whether the requested unknowns are supported |
| `flow.plot()` / `stream.frame` | `adapters.plotting.plot_series(...)` / `adapters.pandas.to_frame(...)` | Explicit rendering; detached tabular output; no changes to content |

`TemporalQuantity`, `AggregateResult` and `AccountResult` are provisional names,
not a second handwritten field schema. Persisted shapes must come from LinkML.
Runtime results need only own calculation/coverage state. Decide whether these
operations accept a temporal Value or its payload consistently before coding.

For every public operation, the final review must state input and return types,
units, order, errors, mutation/copy behavior, randomness, external effects and
owning package. Error behavior and constructors belong in the mapping too.

## Numerical evaluation, equations and solver capability

Use a four-column capability register. A numerical operation, an expression
builder, backend support and accepted published results are four separate claims.

| Operation family | Numerical route | Equation route and execution gate |
| --- | --- | --- |
| Sum, fixed growth factors, balance continuity with fixed rates | Pure known-data calculation | Finite scalar expansion may remain affine. Preserve coordinate-to-Value mapping and residual attribution |
| Resampling and allocation | Explicit calendar, reduction, weighting and exposure operations | Symbolic form only for declared rules and known axis/weights; unknown-dependent interpolation cannot be hidden in preprocessing |
| Discounted cashflows | PV/XNPV with explicit timing/rate basis | Fixed factors may be affine in cashflows. Unknown discount/growth rates generally require capability beyond the present affine executor |
| IRR | Known cashflows, documented root selection/no-root/multiple-root behavior | Unknown-rate solve needs a separately designed and verified numerical/solver capability; no HiGHS support claim follows from an API move |
| Account conditions and policies | Explicit evaluated recurrence/decision rule | Piecewise, integer or nonlinear requirements depend on formulation and solve roles; reject unsupported cases |
| Distribution sampling and market paths | Seeded generation followed by immutable input capture | Exogenous sampled inputs, not re-sampled expressions. A probabilistic model is a distinct future contract if needed |

The current executor supports affine scalar feasibility and rejects several
schema-expressible operations, including calls/selections and optimization. R4
must decide finite scalar expansion versus native indexed lowering, element
assignment/publication, limit accounting and independent temporal residual checks.
Persisting a temporal record alone does not implement any of these capabilities.

Do not add a new production backend merely to make a migration table appear
complete. First identify the consumer requirement, prove a bounded implementation,
and review any capability that changes the selected execution architecture.

## Scenario and policy review

For random behavior, record the generator algorithm/version, seed or state,
scenario identifier, parameter inputs and realized arrays. A seed alone does
not guarantee replay across dependency versions. Parallel workers need explicit
independent streams; scheduling must not determine scenario content. Test fixed
innovations separately from statistical properties. Reuse the same realized
scenarios when comparing policies.

Policy review must specify observation times, allowed information, action
preconditions/effects, simultaneous decisions, no-action behavior, termination
and provenance. Preserve the walkthrough's distinction between hindsight and
adaptive decisions; do not accidentally give an adaptive policy future knowledge.

Prefer a pure `decide(observation, state) -> decision` boundary with explicit
application to a new revision/investigation. Determine which policy definitions
are declarative, which code implementations require pinned registries, and how
their evidence is recorded. Do not serialize a lambda or quietly reinterpret a
source WorkflowSpec as a policy or mathematical Specification. Whether scenario
generation/policy evaluation requires Run extensions is an explicit schema review.

## Consumer migration and proof sequence

| Consumer | Prerequisites and migration | Proof required |
| --- | --- | --- |
| Accommodation/equipment workflow examples; documentation examples; CLI | Feature decisions, workflow v2, explicit Value keys, current adapters/codecs | Build from synthetic inputs in a clean install; inspect checks and serialized Models; documentation commands execute |
| Mandarin YAML, tests and review notebook | Rich source Features, UUID/key mapping, comparisons, workbench and saved-layout feature port | Build independent of reference/archive; separate semantic comparator; fresh-kernel review; source hashes, business identity, Claims/decisions/findings and layout intent preserved |
| East Whisman December and November R2 | Same source mapping capabilities, distinct scenario scopes and current workflow APIs | Both builds and separate scope comparisons in project environment; no invented tower crosswalk, physical basement allocation or apartments |
| `basic_dcf.ipynb` | Units, time, projections, distributions, Flow/Stream and financial metrics | Dates, units, every cashflow, totals, PV/IRR and presentation verified; clean kernel and installed library |
| `deterministic_scenarios.ipynb` | Above plus explicit builders/composition replacing `update_class` | Baseline/optimistic/pessimistic scenarios and weighted comparisons; no hidden class patching or prior cells |
| `market_dynamics.ipynb` | Seeded dynamics/scenario contracts | Fixed-innovation paths plus stochastic property checks; explicit aligned market outputs |
| `flexibility_intro.ipynb` | Scenario and policy contracts; replacement for patched classes | Decision timing, hindsight assumptions, cashflows and policy comparison on common inputs |
| `flexibility_under_uncertainty.ipynb` | Above plus parallel reproducibility and scenario identity | Sequential/parallel agreement under a declared tolerance, distributions and decision records; bounded runtime |
| `load_design.ipynb` | Speckle adapter and domain mapping | Offline fixture plus actual service acceptance; canonical IDs, references and membership; unsupported geometry explicit |
| `drive_model_from_design.ipynb` | Speckle, Model aggregation, temporal Values and financial formulations | Design-derived input → canonical Model → financial results with provenance; shared membership not double counted |
| Test model implementations under `src/tests/models/` | Same builders and numerical interfaces | Migrate full implementations and assertions; inspect methods reached through instances, not only imports |
| Grasshopper C# components and tests | Cross-language canonical format and adapter contract | Fixture round trip plus actual Rhino/Grasshopper authoring checks; transport object identity is not Model revision identity |
| Hypar | Retired by explicit user decision in Turn 3 | Preserve historical files; excluded from supported-consumer acceptance |
| Parallel RK layout/workbench implementation | Inventory complete public behavior and current tests, then port against Model-backed graph/adapters/workflow | Inspection/progress, checked layouts, saved preferences and viewer edits preserved; layout backend/environment checks remain separate from domain solve tests |
| Other consumers discovered during repository/import/data-format searches | Add to this register and classify current version/capabilities | A named owner, environment, migration recipe, evidence and removal gate |

The installed-package requirement matters: the walkthrough currently declares
`rangekeeper>=0.8`, while Projects uses an editable sibling. Pin the actual artifact
under test and record import locations. A passing notebook against an unrelated
installed release does not prove this migration.

Inspect notebook code for side effects before execution. Use fresh output copies,
isolated output directories, fixed inputs and explicit seeds/locales. Never use
stored notebook output as current proof. Review plots for dates, units, labels and
series content; pixel equality is not the default acceptance criterion.

## Behavior ledger and evidence rules

The source inventory is the starting list, not a completed behavior ledger. For
each coherent behavior record:

```text
Behavior ID and old symbols (including fields, defaults and error cases)
Observed implementation + actual consumer locations + historical version
Intended meaning and examples
Disposition: retain / split / remodel / correct / retire
New module and public signature
Schema changes and dependency/capability requirements
Mutation, units, ordering, missingness, randomness and effects
Old baseline or reason it cannot run
Independent expected result + new result + explicit tolerances
Accepted differences and user decision, when required
Upgrade recipe and unsupported-input behavior
Retirement condition and actual evidence status
```

Use exact equality for identities, discrete content and order where meaningful;
declared absolute/relative tolerances for floating-point results; invariant and
statistical tests for stochastic behavior. Tolerances must be agreed before
looking at discrepancies. A round trip or two matching implementations alone
does not establish the intended mathematics.

Retain old baseline execution in a frozen environment outside new runtime code.
Use hand-calculated cases and independent identities such as cash conservation,
balance continuity, allocation mass and unit consistency. For methods with
mutation, verify both outputs and unchanged inputs in the new API. Add negative
cases for unsupported shapes, units, calendars and unknown-dependent operations.

Do not alter old tests to make a new output pass without documenting the contract
change. Existing failures are neither proof of a regression nor a blanket waiver;
reproduce, diagnose and decide them as part of the relevant slice.

## Proposed implementation order and acceptance checks

These work packages refine the expanded scope; they do not relabel delivered
Steps 1–5 or claim that temporal work has already passed acceptance.

| Package | Work | Exit and review |
| --- | --- | --- |
| P1 — complete behavior contracts | Expand the static inventory into the ledger; capture runnable old examples, data shapes, branch features and external environments | R1: no unassigned active behavior; limitations and unsupported sources explicit |
| P2 — content and temporal design | Decide rich Features, calendar/series/units/ownership, policy/scenario boundaries and concrete interfaces | R2/R3: worked examples, exact schema/API proposal, intentional breaks and dependency plan |
| P3 — schema and pure foundations | LinkML extensions, generation, validation, codecs/upgrades, immutable access, units/calendar operations | New conformance suites, round trips, revision invariants and unchanged scalar acceptance |
| P4 — numerical and presentation refactor | Move/split characterized algorithms; explicit sampling; detached pandas/plotting; finish synthetic workflow examples | Per-behavior equivalence or reviewed correction; minimal dependency/install checks |
| P5 — formulations and execution | Builders, element assignments/lowering/publication and independent acceptance for bounded temporal investigations | R4: declared capability matrix; authentic temporal Run/output evidence; forward/inverse only for supported equations |
| P6 — scenarios, policies and branch features | Reproducible scenario composition, explicit decisions, workbench/layout port | R5: common-scenario comparisons, decision timing, reproducibility, layout/workbench tests and host limits |
| P7 — migrate every supported consumer | Run the consumer rows above as soon as their prerequisites pass; author the upgrade guide alongside each migration | R6 per consumer: clean install/kernel/bootstrap, semantic comparisons, reviewed outputs, no runtime legacy imports |
| P8 — retire old architecture | Remove old classes/codecs/exports, root numerical paths, obsolete helpers and stale generated docs; complete optional dependency cleanup | Final R6: all ledger rows resolved, no supported consumer relies on old code, new runtime and guide stand alone |

This is a dependency order, not eight mandatory large turns. For example, migrate
the basic DCF alongside P4/P5, and source projects when their rich-content and
workbench prerequisites are ready. Do not postpone all consumer trials to the end.
Remove an old component only after its own gates pass. Full retirement waits for
every supported component, including service/host consumers; missing access stays
an explicit blocker rather than being called completion.

## Guidance for future upgrades of legacy consumers

Maintain a versioned `docs/LEGACY_UPGRADE_GUIDE.md` during implementation, containing:

1. A starting-version detector/checklist and supported upgrade routes. Distinguish
   Python API versions, workflow YAML versions, persisted Graph formats and Model
   schema versions. A package rename is not a data-format migration.
2. An old-symbol → new-operation table linked to behavior IDs, with constructors,
   return types, errors and default changes; runnable before/after examples.
3. Recipes for Graph→Model, Measurements→keyed Values, Feature interpretation,
   provenance/UUID mapping, revisions, temporal cashflows, units, distributions,
   account equations, policy decisions, plots and saved viewer preferences.
4. Explicit conversion tooling only for supported formats/content. Require a
   source hash, declared source version, mapping configuration, fresh output path,
   identity map and unresolved-content report. Do not partially publish a Model
   while concealing unmapped content. Preserve the original input unchanged.
5. A verification checklist covering source hashes, result comparisons, missing
   versus zero, units/calendar timing, provenance, random replay and installed
   imports; templates for migration tests and evidence manifests.
6. A troubleshooting section for unsupported Features, obsolete pandas/date
   assumptions, wrong installed RK version, absent extras, legacy callbacks,
   nonlinear requests, unavailable services and partial migration.
7. A frozen historical baseline route for old code that must still be inspected.
   If it is necessary to read an old format after runtime retirement, use a
   separately versioned offline conversion tool/environment, not imports of the
   deleted domain from the new package.

Prefer rebuilding source-driven projects from their original inputs and reviewed
mappings. Use conversion when persisted data must survive and cannot be rebuilt.
Never reinterpret old source evidence simply to fit a new field.

Test the guide itself on a small legacy project in a clean environment. Its
commands and snippets must run with the documented versions; it must remain
usable after the old modules are deleted.

## Completion criteria

Full refactoring is complete only when:

- Every inventoried behavior is preserved, deliberately remodeled/corrected, or
  explicitly retired with its consumers resolved. A moved file is not evidence.
- Every supported consumer has a reproducible migration and accepted results;
  a skipped notebook, absent service or unavailable host is not a pass.
- Canonical temporal/rich content round-trips and remains immutable, with units,
  order, ownership, missingness and provenance intact.
- Numerical, symbolic, solver and publication capabilities are documented and
  independently tested; unsupported capabilities fail explicitly.
- New runtime imports and installed artifacts contain no superseded domain or
  old numerical public paths. Historical references may remain only in clearly
  labelled migration documentation/evidence and isolated upgrade tools.
- Optional dependencies, root exports, examples, notebooks, generated docs and
  parallel feature ports match the final architecture.
- The upgrade guide succeeds without hidden notebook state, source checkouts,
  archived project code or the removed modules installed alongside the new API.

The next implementation work is Turn 2 in [the four-turn sequence](FULL_MIGRATION_TURN1.md#four-turn-sequence-and-review).
The P1–P8 items above are responsibility/dependency groups, not separate turns or
approval gates. No new blanket planning or user approval is needed to settle
routine implementation details. Full completion still requires the listed consumer
and retirement evidence.
