# Temporal equations, scenarios and policies

Model and Specification use schema **0.7.0**; Run uses **0.4.0**. LinkML owns
persistent fields. Generated Python and C# artifacts change together. Readers
accept current versions. Explicit migration creates new revisions and remaps pins;
it does not rewrite historical Runs or claim to reproduce old execution.

## Declarations and numerical roles

`Reference(target: UUID)` identifies a Value or Movement in one revision scope.
Movement keys and coordinates support alignment; they do not determine identity.
Bindings refer to whole Values. `specification.targets.assign_flow` and
`unknown_flow` expand declared Flow shapes into individual Movement roles.
Recorded amounts and estimates do not supply missing assignments.

Flow units, shape, UUIDs and coordinates must exist before solving. Magnitudes may
be absent or null. Known zero is distinct from both. Duplicate roles and conflicts
between assignments, unknowns and policy controls use UUID identity. Composition
permits one policy contribution; it does not allow contributions to override roles.

Period fields are `start_inclusive` and `end_exclusive`. `PeriodTiming.FIRST`,
`LAST` and `END` select the first date, final included date and excluded boundary.
A recorded Movement date takes precedence over a requested representative date.
See [calendar and account contracts](calculations.md).

## Ownership

| Owner | Responsibility |
| --- | --- |
| `model.expression` | Generated expression exports, static domains, validation and pure numerical arithmetic |
| `model.scope` | UUID-indexed mathematical declarations and explicit recorded scalar access |
| `model.formulation.authoring` | `identify`, `identify_tree` and `declare` for stable declaration identities |
| `model.formulation.flow` | `sum`, `scale`, `accumulate`, and symbolic shape/alignment helpers |
| `model.formulation.growth` | `linear` and `compound` |
| `model.formulation.financial` | `discount`, `present_value` and `reversion` |
| `model.formulation.account` | Explicit principal `interest` and coordinated passive `schedule` |
| `model.scenario.contracts` | Immutable method, parameter, input and output inventories; captured-record conformance without random generation |
| `model.scenario.market` | `make_plan`, `validate`, `sample`, `capture`, `realize` and `generate` |
| `model.scenario.implementation` | Calculation provenance and its declared source/dependency manifest |
| `model.scenario.replay` | Check saved paths against captured inputs and the available calculation |
| `specification.policy` | Generated declarations/outcomes, `evaluate`, `observe` and derived results |
| `specification.policy._availability` | Pure date rule, shared by runtime observation and stored-evidence checks |
| `specification.policy.predicate` | Exact Boolean truth and short-circuiting; arithmetic uses the shared evaluator |
| `specification.policy.validation` | Policy declaration and independent stored-outcome checks |
| `rangekeeper_examples.investment` | The model-specific resale policy and investment author/formulate/specify/report operations |

Builders return immutable declarations. They do not solve or read recorded amounts
as hidden constants. `model.formulation.authoring.declare(id, name, equations, values)`
assembles custom finite mathematics. IDs use the Formulation UUID, operation,
Movement UUID or equation label, and expression path. Operand order is preserved.
Coordinate mismatches and ambiguous duplicates fail. Reversion uses an explicit
result-Movement to income-Movement mapping.

## Finite temporal execution

Each Movement equation becomes a scalar Expression and Constraint. Internal
symbols are UUID keys. Assignments fix quantities; the affine compiler and its
backend never infer assignments from stored amounts.

| Operation | Supported route |
| --- | --- |
| Aligned sums, fixed scaling and signed balance continuity | Affine execution |
| Growth, discounting and inverse initial amounts | Affine when explicit roles fix all required coefficients |
| Six account conventions with a fixed rate and nonnegative principal | Explicit passive schedule, bounds and ordinary equations |
| Unknown rates, products of unknowns or overdraft-dependent branches | Capability rejection; known-data calculations remain separate |
| Strict comparison of fixed or literal operands | Exact check before solving and again during independent acceptance |
| Strict comparison involving an unknown | Rejected before simplification, even when terms cancel |
| Finite exogenous policy | Evaluate once before compilation, then use explicit control assignments |
| Endogenous sequential policy or multistage optimization | Capability rejection |

Discounting begins at exponent one by default; growth starts at the initial amount.
Rates are per declared step. Builders do not infer annualization. `growth.linear`
takes an amount increment. [Scalar execution](execution.md) defines limits,
independent acceptance, implementation fingerprints and publication.

## Captured scenarios and replay

Use `from rangekeeper.model.scenario import market`. Stable method codes are `market`,
`market.estimates` and `market.independent`. `market.sample` records random inputs only; `market.capture`
records supplied inputs without randomness. `market.realize(model, plan, draws=)`
constructs paths from a draw Model derived from that base. `market.generate`
combines sampling and realization. Its sequential path calls the calculation
directly; workers exchange detached wire data and preserve requested key order.

SeedSequence/PCG64 streams derive from the seed, scenario key and stable component
identifier using SHA256. Worker count and key order do not alter a scenario's
stream. Component authors such as `market.make_trend`, `make_volatility`,
`make_cyclicality`, `make_noise` and `make_black_swan` create plan parameters.
Duplicate parameters fail. Space-cycle variation stays centred on zero; amplitude
is half the full height.

Captured provenance records streams and library versions separately from
`CalculationProvenance(name, fingerprint, versions)`. A realized Model revision
hash includes its complete candidate content, except its new root ID, and the
calculation provenance. The encoding is sorted-key, compact, ASCII JSON with
nonfinite values forbidden, SHA256, then UUID5 under the realization UUID with
`realized-model/v1:`. Changed paths or calculation code therefore change the
revision; declaration IDs and sampling streams remain stable.

`model.scenario.replay` never draws again. It requires captured inputs, checks calculation
identity, and compares recomputed paths with saved paths. `ReplayUnavailableError`
means the saved result is readable but its calculation implementation is unavailable.
It differs from `UnsupportedVersionError`, which rejects a document version at
load time. Migration preserves saved values and cannot invent current calculation
provenance for old results.

`Market` provides revision-pinned access, including `space_market_price_factors`,
`asset_true_value`, `implied_reversion_cap_rates`, `autoregressive_returns` and
`cumulative_volatility`. `resolve_input` and `resolve_output` are explicit;
`value(name)` rejects ambiguous names. Access performs no calculation. Next-period
ratios cannot be observed until their required next period ends.

## Policy declarations and evidence

Import `Policy`, `Decision`, `Rule`, `Action`, `ActionKind` and `DecisionOutcome`
from `rangekeeper.specification.policy`. `Policy.decisions` contains dated declarations;
`Report.outcomes` contains evidence. Each outcome's `decision` identifies its
declaration. There is no public `decide` or `DecisionHistory` wrapper.

`evaluate(policy, model=..., units=...)` prepares the scope and availability index
once, then applies the first true rule or the explicit fallback. Actions assign
controls and may terminate. `observe` accepts only named quantities available by
the decision date. Earlier outcomes can supply later observations; a recorded
control value cannot substitute for an earlier decision. Declared availability can
delay access, but cannot advance coordinate or provenance requirements.

`PolicyResult.outcomes` is an immutable tuple. Its assignments are derived from
those outcomes. Independent stored-evidence validation checks dates, observed
quantities, first-match choice, actions, termination, complete trace and exactly-once
control coverage. It applies to Runs with and without published outputs. Runtime
and stored checks use the caller's unit context. Neither certifies numerical
feasibility; acceptance still checks the original governing equations.

The investment resale example uses a strict factor greater than the threshold,
a minimum holding period and final-horizon fallback. Sale includes that period's
operating cashflow and proceeds. Later controls are zero; the full market path
remains recorded. These economic roles belong to the investment example.

See [migration](../guides/upgrading.md), [record methods](records.md), and
[verification](../contributing/verification.md) for repeatable checks and their external limits.

## Scenario vocabulary

| Name | Responsibility |
|---|---|
| Model | Canonical immutable content and provenance |
| Market | Read-only, typed access to a recorded market within one Model revision |
| ScenarioPlan | Complete generation inputs, method, periods and seed |
| ScenarioParameter | Named fixed quantity or distribution input |
| ScenarioRealization | Captured inputs and outputs, random identities and availability |
| Distribution | One LinkML-generated probability-distribution record |
| Binding | A local name referring to a canonical Value; the container defines scope |
| RandomStream | Recorded identity of a random sequence, separate from a Flow Stream |
| Decision | Dated policy declaration with observations, rules and fallback |
| DecisionOutcome | Recorded observations, assignments and termination for one Decision |
| CalculationProvenance | Calculation identity distinct from random-stream evidence |

`schema/distribution.yaml` and `schema/binding.yaml` contain reusable contracts.
`schema/scenario.yaml` imports them. A Formulation and a realization use the same
Binding record; each container validates local uniqueness and target resolution.
No generated field schema is repeated in a handwritten distribution class.

## Composable market authoring

`model.scenario.market` exposes `make_plan`, `make_trend`, `make_volatility`,
`make_cyclicality`, `make_noise`, `make_black_swan`, `sample`, `capture`, `realize`
and `generate`. Component constructors return tuples of generated
ScenarioParameter records. They do not sample or create output Flows. Duplicate
explicit parameters across components or the parameter mapping fail.

Given a base `model` and explicit calendar `periods`, compose the plan as follows:

```python
from rangekeeper.model.scenario import market

plan = market.make_plan(periods=periods, seed=23, components=(
    market.make_trend(growth_rate=.02),
    market.make_volatility(volatility_per_period=.03),
    market.make_cyclicality(space_amplitude=.25),
    market.make_noise(lower=-.02, upper=.02),
    market.make_black_swan(likelihood=.02, impact=-.25),
))
markets = market.generate(model, plan, scenario_keys=("base",))
pricing_value = markets[0].space_market_price_factors
pricing_flow = pricing_value.flow
```

`Market` stores only its Model and selected realization. Named properties resolve
canonical Values; they do not own copied Flow content or calculate on access.
Missing components raise KeyError, including components not provided by an
independent-path method. Captured inputs without realized outputs cannot be
presented as a Market. Selecting evidence from a different revision fails.

## Quantities retain their meaning

| Earlier public name | Current name |
|---|---|
| pricing_factor | space_market_price_factors |
| true_value | asset_true_value |
| implied_cap_rate | implied_reversion_cap_rates |
| input volatility | volatility_per_period |
| output volatility | cumulative_volatility |
| output autoregression | autoregressive_returns |

The autoregression coefficient is still an input named `autoregression`.
Cumulative volatility is a rental level after accumulation and mean reversion,
not a return increment. Space-cycle variation is centred on zero; its multiplier
is `1 + space_cycle`. The legacy `space_waveform` already included that one, so it
is not a synonym. Amplitude remains half the peak-to-trough height. No formula,
Flow semantic kind, or implicit assignment is introduced by these names.

Black Swan is the walkthrough name for the once-per-scenario shock recipe. The
general numerical function remains `calculate_shock`. `make_noise` declares the
current method's uniform bounds; it does not claim support for arbitrary deal-noise
distributions. Linked cycle estimates remain available through
`market.estimates` and explicit plan parameters.
