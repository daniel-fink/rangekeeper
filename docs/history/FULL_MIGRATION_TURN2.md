# Full migration Turn 2: temporal equations, scenarios and policies

> Historical design or implementation record. Names, commands and status below describe that checkpoint. Use the [current documentation](../README.md) for supported APIs.

**Naming follow-up, 2026-10-06:** [RK vocabulary alignment](../RK_NAMING.md) is implemented.
The current check is 971 passing local tests, all seven schema suites, static
and installed-package checks, and five executed walkthroughs. This supersedes
older counts below. Market methods use v2 names with an explicit draft upgrade.
No commit or push was made.

Implemented from `7b8dcd4` on `acausal-modelling`. The required verification gates pass: 967 local tests, all seven schema suites,
typing, installed-package checks, and all five numerical notebooks.
The [evidence report](../research/full-migration/turn2/README.md) records exact commands,
environments, input hashes, intermediate failures and final results. No commit,
push or release is part of this turn. Full legacy retirement remains open.

## Record contracts

LinkML remains authoritative. Model and Specification are **0.5.0**; Run is
**0.2.0**. Generated immutable records and the native LinkML bundle are regenerated
together. Schema changes are deliberate draft-format breaks, with explicit
revision-producing upgrades. Historical Runs and research outputs keep their
original formats and pins.

`ValueReference(value: UUID, movement: str | None = None)` identifies a Value or
one of its owner-local Movement keys. The containing Model or composed
Specification fixes revision scope. Movement order and coordinates have meaning,
but neither array position nor a separate Movement UUID determines identity.

- `Expression.target`, `Assignment.target`, estimates and `Specification.unknowns`
  share that reference shape. Bindings continue to refer to whole Values.
- Numerical roles accept scalar measurements or individual Movements. Whole-Flow
  roles require explicit expansion with `assign_flow()` or `unknown_flow()`.
- Flow units, shape, keys and coordinates must exist before solving. Magnitudes
  may be absent or null. Known zero is distinct from either unresolved state.
- Duplicate roles and assignment/unknown/control conflicts use the pair of Value
  UUID and optional Movement key. Contributions cannot override each other, even
  with identical quantities. One policy contribution is permitted per composition.
- Loading recorded values or supplying estimates never assigns them.
  `assign_flow()` explicitly copies resolved recorded magnitudes in Flow units.
- Movement assignments convert to Flow units; scalar assignments convert to
  Measure units. Symbolic arithmetic retains dimensions, including time powers.
- Diagnostic references carry the document revision plus ValueReference, so a
  residual can identify both its Constraint and participating Movements.

A limited Run can use `not_assessed` when preparation consumes its time budget
before numerical assessment. It requires runtime evidence and a diagnostic, and
publishes no output. This differs from a solver's unknown mathematical conclusion.

## Package ownership and interfaces

```text
rangekeeper/
  model/
    duration.py                 Period, Span
    flow.py                     Flow, Movement, Stream
    expression.py               Expression, ValueReference
    scenario.py                 generated scenario record exports
    _references.py              shared scoped reference checks
    _scenario.py                pure captured-record conformance
    _availability.py            shared observation availability rules
    _predicate.py               pure Boolean/arithmetic tree evaluation
  duration/
    calendar.py                 date/day-count operations
    period.py                   explicit calendar grids and date resolution
  formulations/
    expression.py               literal, reference, add, multiply, equal, ...
    flow.py                     build_sum, build_scale, build_accumulation
    growth.py                   build_linear, build_compound
    financial.py                build_discount, build_present_value, build_reversion
    account.py                  build_balance, build_interest
    _identity.py                deterministic UUID5 declaration IDs
    _alignment.py               coordinate matching and key references
    _construction.py            assemble finite immutable declarations
  specification/
    targets.py                  scalar, movement, assign_flow, unknown_flow
    policy.py                   generated policy record exports
    _policy_validation.py       declaration and decision-trace checks
  scenarios/
    plan.py                     make_plan, validate
    random.py                   create_generator, stable component identifiers
    market.py                   sample, capture, generate, realize
    replay.py                   replay
    view.py                     Market: typed, revision-pinned access
  policies/
    observation.py              observe
    evaluation.py               decide, evaluate
    resale.py                   build_stop_gain_resale_policy
    result.py                   Observation, DecisionHistory, PolicyResult
  execution/
    symbols.py                  scalar/Movement resolution
    preparation.py              explicit roles and policy assignments
    compiler.py                 affine lowering under fixed assignments
    evaluator.py                independent original-expression evaluation
    acceptance.py               exact assignments, residuals, scoped evidence
    publication.py              new immutable output revisions
    executor.py                 attempt limits, backend orchestration, storage
  examples/investment.py        named author/formulate/specify/report operations
  adapters/plotting.py          detached Flow, distribution and paired plots
  migration/drafts.py           upgrade_model, upgrade_specification
  _legacy_duration.py           temporary retained-caller support
```

`formulations.build_formulation(id=, name=, equations=, values=)` supports explicit
custom finite equations. Builders return declarations only. They read Flow shapes,
not recorded amounts as hidden constants. They perform no calculation, solve or IO.
Coordinate mismatches and ambiguous duplicate coordinates fail. Lagged reversion
uses an explicit result-key to income-key mapping. Generated IDs use Formulation
ID, operation, Movement/equation key and expression-tree path; operand order is
preserved. Units are checked when mathematics is compiled and independently accepted.

`duration/` replaces `temporal/`, with no alias. `model.duration` and the Period/Span
wire fields are unchanged. Old `duration.Type/Sequence/Span` are not the new API.
The private legacy module exists only for unmigrated consumers and characterization
checks. The namespace slice was verified before schema extensions.

Generated classes define persistent fields. Runtime result classes contain only
derived access/execution state. Domain validation imports no solver, plotting,
dataframe or random-generation implementation. NumPy/SciPy and PyXIRR remain
calculation dependencies; the Pyomo/HiGHS extra remains optional and process isolated.
No new solver backend or vector-expression language was added.
The extra stock LinkML loader probe passes nine of ten actual documents and fails
on a terminal policy Action. Public generated immutable records and codecs pass
all ten. The private stock loader is not the runtime persistence path; its exact
limitation and retained nonzero result are in the evidence report.

## Finite temporal execution

Each Movement equation becomes an ordinary scalar Expression and Constraint.
Reference tokens used inside the compiler/backend are private lookup keys, not a
new persistent identity scheme. Assignment quantities replace fixed symbols;
recorded values and estimates do not fill missing roles.

| Operation | Supported route |
|---|---|
| Aligned sums, fixed scaling, signed balance continuity | Affine execution |
| Compound/linear growth and discounting | Affine when explicit roles make all coefficients fixed |
| Inverse initial amount or rent, with fixed rates | Same equations with different assignments and unknowns |
| Unknown rates, general IRR, products of unknowns | Not supported as a HiGHS investigation; use known-data calculations where applicable |
| Interest on declared nonnegative principal | Explicit principal bounds and principal × fixed periodic rate |
| Overdraft-dependent/piecewise interest | Known-data account calculation; unsupported symbolic branches fail |
| Finite exogenous policy decisions | Evaluate once before compilation; supply recorded explicit control assignments |
| Endogenous sequential policy / multistage optimization | Capability rejection; no hidden iterative solver |

Discount rates are per declared step. Growth begins with the initial amount at
index zero; discounting begins at exponent one by default. Neither builder infers
annualization. `build_linear` takes an amount increment, not a proportional rate.

Defaults are **10,000 expanded symbols**, **20,000 affine constraints** and the
existing **30-second attempt budget**. Applied limits and expansion counts appear
in the Run report. Preparation and recursive compilation check the shared deadline;
the backend receives only its remaining budget. These are cooperative Python
checkpoints, not hard interruption of a single structural-validation call.

Publication retains Value identities, Movement keys, coordinates, order, Flow
units, unrelated content and historical Claims. It changes only explicit assigned
or solved magnitudes and supporting evidence. Changed Movements gain fresh Claims;
affected Values gain Facts. The candidate passes through the codec before original
Expressions and exact normalized assignments are checked. Rejected candidates are
never stored as outputs; input revisions remain unchanged. The Specification and
failed Run are still retained as execution evidence.

The installed temporal oracle verifies `100, 110, 121`, discounted at 10% for
periods 1–3, produces PV `3000/11`. Reusing that actual output with PV assigned to
300 solves initial amount 110. Scalar valuation acceptance remains $11 million
forward and $27,500 rent inverse.

## Reproducible scenarios

Plans record all defaults, distributions, periods, method/version and master seed.
`market.v2` composes trend, autoregression, mean reversion, cycles, noise and one
shock amplitude. `market.estimates.v2` retains linked phase/period estimates from
the old uncertainty walkthrough. `independent.v2` retains paired independently
sampled space factors and capitalization rates for the probabilistic test model.
These paths are normalized dimensionless factors; investment equations apply units.

`sample()` records draws only. `capture()` records supplied quantities/innovations
without randomness. `realize(model, plan, draws=...)` constructs paths from a draw
Model derived from that base revision. `generate()` combines sampling and
realization. `replay()` recomputes from captured inputs and checks stored paths
without drawing again. Stored paths remain ordinary usable Values if regeneration
is unavailable in another implementation version.

NumPy SeedSequence/PCG64 streams derive from the seed, scenario key and stable
component identifier, using SHA256 rather than Python hash or dispatch order.
Worker communication contains detached data. Results retain requested key order;
worker count and key reordering do not change a scenario's content. Storage is
outside workers. Realizations record stream identifiers, library versions, named
input/output Value references and availability under Model provenance.

`Market` exposes canonical Values through typed properties such as
`space_market_price_factors`, `asset_true_value`, `implied_reversion_cap_rates`,
`autoregressive_returns` and `cumulative_volatility`. The input scale is named
`volatility_per_period`. Explicit `resolve_input` and `resolve_output` remain
available; `value(name)` rejects ambiguous names. Access performs no calculation.

`market.make_trend`, `make_volatility`, `make_cyclicality`, `make_noise` and
`make_black_swan` compose generated ScenarioParameter records into `make_plan`.
Duplicate explicit parameters fail. Space-cycle variation remains centred on zero;
the multiplier is one plus that variation. Amplitude remains half the full height.

The [naming update](../RK_NAMING.md) documents the shared generated Distribution,
Binding and RandomStream records, DecisionHistory, and the explicit v1-to-v2
scenario upgrade. Original Runs and research evidence retain their old formats.

Captured shapes, parameter support, finite resolved inputs, output inventories and
availability are validated. Next-period ratios (`implied_reversion_cap_rates`, `returns`)
cannot be observed until that next period ends. Availability is evidence, not a
permission to use future data early.

## Declarative policy and sale convention

Policy, DecisionPoint, Rule, Action and Decision are generated records. Points are
finite and dated. Ordered rules use Boolean Expressions; the first matching rule
applies all its actions atomically. The fallback is explicit. Supported effects
assign declared controls and terminate the sequence. No callback/import is stored.

`observe()` provides only named quantities available by the decision date.
`decide(point, observation, state)` receives no Model or store. Earlier decisions
can supply later observations; recorded old control values cannot substitute for
current decisions. Missing observations fail. An explicit availability date can
delay access, but cannot advance it before coordinate/provenance requirements.

The resale policy uses a strict factor **greater than** threshold, an explicit
minimum holding period and a final-horizon fallback. A sale at a period end includes
that period's operating cashflow and sale proceeds. All later investment controls
are zero. There is exactly one sale. The complete market path is retained.

Decision evidence records date, matched rule, observed references/quantities,
assignments and termination reason in the Run report. Validation checks timing,
first-match choice, declared actions and exactly-once coverage of control targets.
Policy evaluation does not establish numerical feasibility. Acceptance still
checks the resulting governing equations.

## Consumer placement and intentional changes

| Consumer | Delivered replacement and acceptance |
|---|---|
| `deterministic_scenarios.ipynb` | Explicit author/formulate/specify/execute/report; component cashflows, base/optimistic/pessimistic comparisons, PV and dated IRR; horizon selection is labelled hindsight |
| `market_dynamics.ipynb` | Recorded plan/draws/paths, market components, delayed observations and replay |
| `flexibility_intro.ipynb` | Traditional, fixed and threshold outcomes on the same realized market; explicit decision trace, one sale and no post-sale investment amounts |
| `flexibility_under_uncertainty.ipynb` | Paired fixed/policy comparisons for identical scenario realizations; visible count, PV/IRR distributions, differences and sale dates |
| Deterministic/probabilistic/flexible test models | Canonical named operations; no old Flow, dynamics, callback policy or constructor calculations |
| Basic DCF and source workflow regression | Current reference/schema shape and duration imports; original accepted results retained |
| Service/design notebooks, Projects/workbench, integrations | Turn 3: source/service-specific acceptance remains required |
| Old numerical/domain implementations and comparison tests | Turn 4 removal after remaining caller proof and retained behavior evidence |

The uncertainty notebook keeps `FULL_SCENARIO_COUNT = 2000`. Routine acceptance
uses `RK_SCENARIO_COUNT=4`, shown in its output. That small run verifies execution,
not distribution convergence or the performance of a 2,000-scenario study.
`RK_SCENARIO_WORKERS` controls generation workers explicitly. A threshold policy
can improve or reduce realized value; it does not guarantee sale at the market peak.

Plotting consumes detached data and returns figures. There is no locale-dependent
calculation, `update_class`, or hidden constructor execution in migrated consumers.
See the [upgrade guide](../LEGACY_UPGRADE_GUIDE.md) and the
[retained-dependency inventory](../research/full-migration/turn2/legacy-dependencies.json).

## Verification and remaining work

The fresh starting suite passed **946** local tests. Earlier counts remain historical.
Final actual counts, all seven schema suites, typing, wheel checks, authentic
outputs and five executed notebooks are recorded in the evidence report.
External services and the full 2,000-scenario study are not claimed as verified.

Next is Turn 3 of the agreed four-turn migration: finish remaining consumer and
integration ports with explicit format/service acceptance. Turn 4 then removes
superseded implementations and unused dependencies only after those retirement
gates pass. The current public API has deliberate breaking draft changes; it does
not make all existing downstream consumers compatible automatically.
