# Temporal equations, market paths and rules

Model, Specification and Run use format **1.0.0**. LinkML owns persistent fields.
Generated Python and C# artifacts change together. A reader accepts every format
with its major version, up to its own version. Conversion creates new revisions and
remaps pins; it does not rewrite historical Runs or claim to reproduce old execution.

## Declarations and numerical roles

`Reference(target: UUID)` identifies a Value or Movement in one revision scope.
Movement keys and coordinates support alignment; they do not determine identity.
Bindings refer to whole Values. `specification.targets.assign_flow` and
`unknown_flow` expand declared Flow shapes into individual Movement roles.
Recorded amounts and estimates do not supply missing assignments.

Flow units, shape, UUIDs and coordinates must exist before solving. Magnitudes may
be absent or null. Known zero is distinct from both. Duplicate roles and conflicts
between assignments, unknowns and rule controls use UUID identity. Composition
permits one rule set contribution; it does not allow contributions to override roles.

Period fields are `start` (included) and `end` (excluded). `PeriodTiming.FIRST`,
`LAST` and `END` select the first date, final included date and excluded boundary.
A recorded Movement date takes precedence over a requested representative date.
See [calendar contracts](calculations.md).

## Ownership

| Owner | Responsibility |
| --- | --- |
| `model.expression` | Generated expression exports, static domains, validation and pure numerical arithmetic |
| `model._scope` | UUID-indexed mathematical declarations over raw mappings (internal) |
| `model.targets` | The owning Value, units and recorded scalar of a Reference target in one Model |
| `model.formulation.authoring` | `identify`, `identify_tree` and `declare` for stable declaration identities |
| `model.formulation.flow` | `sum`, `scale`, `accumulate`, and symbolic shape/alignment helpers |
| `model.formulation.growth` | `linear` and `compound` |
| `model.formulation.financial` | `discount`, `pv`, `reversion` and explicit principal `interest` |
| `market.contracts` | Immutable method, parameter, input and output inventories; captured-record conformance without random generation |
| `market.generation` | `make_plan`, `validate`, `sample`, `capture`, `realize` and `generate` |
| `market.dynamics` | Deterministic trend, cycle and shock kernels over supplied inputs |
| `market.implementation` | Calculation provenance and its source/dependency manifest, from the import closure of the calculation |
| `market.replay` | Check saved paths against captured inputs and the available calculation |
| `specification.rule` | Generated declarations and evidence |
| `specification.rule.validation` | Rule declaration checks |
| `execution.rule` | `evaluate`, `observe` and derived results |
| `run._rule.availability` | Pure date rule, shared by runtime observation and stored-evidence checks |
| `run._rule.predicate` | Exact Boolean truth and short-circuiting; arithmetic uses the shared evaluator |
| `run._rule.evidence` | Independent stored-evidence checks (the trace check) |
| `rangekeeper_examples.investment` | The model-specific resale rules and investment author/formulate/specify/report operations |

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
| Unknown rates, products of unknowns or overdraft-dependent branches | Capability rejection; known-data calculations remain separate |
| Strict comparison of fixed or literal operands | Exact check before solving and again during independent acceptance |
| Strict comparison involving an unknown | Rejected before simplification, even when terms cancel |
| Finite exogenous rules | Evaluate once before compilation, then use explicit control assignments |
| Endogenous sequential rules or multistage optimization | Capability rejection |

Discounting begins at exponent one by default; growth starts at the initial amount.
Rates are per declared step. Builders do not infer annualization. `growth.linear`
takes an amount increment. [Scalar execution](execution.md) defines limits,
independent acceptance, implementation fingerprints and publication.

## Captured market paths and replay

Use `from rangekeeper.market import generation as market`. Stable method codes are `market`,
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

`rangekeeper.market.replay` never draws again. It requires captured inputs, checks calculation
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

## Rule declarations and evidence

Import `RuleSet`, `Decision`, `Rule`, `Action`, `ActionKind` and `RuleEvidence`
from `rangekeeper.specification.rule`. `Specification.rules` holds a `RuleSet`;
`RuleSet.decisions` contains dated declarations. `Report.rule_evidence` contains
the evidence. Each record's `decision` identifies its declaration. The rule
queries of [ADR-021](../decisions/021-sequential-decisions.md) replace these
records ([#215](https://github.com/daniel-fink/rangekeeper/issues/215)). There is no public `decide` or `DecisionHistory` wrapper.

Import `evaluate`, `observe`, `RuleResult` and `RuleCapabilityError` from
`rangekeeper.execution.rule`. `evaluate(rules, model=..., units=None)` prepares the scope and availability index
once; without `units` it uses `Model.unit_system`. It then applies the first true rule or the explicit fallback. Actions assign
controls and may terminate. `observe` accepts only named quantities available by
the decision date. Earlier evidence can supply later observations; a recorded
control value cannot substitute for an earlier decision. Declared availability can
delay access, but cannot advance coordinate or provenance requirements.

`RuleResult.evidence` is an immutable tuple. Its assignments are derived from
that evidence. `rk.execution.DecisionResult` names the result of one check:
`DECIDED`, `NOT_MET`, `SKIPPED` or `OTHERWISE`. `DecisionResult.of(evidence)`
reads it from one `RuleEvidence` record: `DECIDED` when a rule matched, else
`OTHERWISE`. The checks on each window date, which also give `NOT_MET` and
`SKIPPED`, come with the rule queries
([#300](https://github.com/daniel-fink/rangekeeper/issues/300)). Independent stored-evidence validation checks dates, observed
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

## Market path vocabulary

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
| RuleSet | The rules of a Specification: controlled targets and dated decisions |
| Decision | Dated rule declaration with observations, rules and fallback |
| RuleEvidence | Recorded observations, assignments and termination for one Decision |
| CalculationProvenance | Calculation identity distinct from random-stream evidence |

`schema/distribution.yaml` and `schema/binding.yaml` contain reusable contracts.
`schema/scenario.yaml` imports them. A Formulation and a realization use the same
Binding record; each container validates local uniqueness and target resolution.
No generated field schema is repeated in a handwritten distribution class.

## Composable market authoring

`market.generation` exposes `make_plan`, `make_trend`, `make_volatility`,
`make_cyclicality`, `make_noise`, `make_black_swan`, `sample`, `capture`, `realize`
and `generate`. Component constructors return tuples of generated
ScenarioParameter records. They do not sample or create output Flows. Duplicate
explicit parameters across components or the parameter mapping fail.

Given a base `model` and explicit calendar `periods`, compose the plan as follows:

```python
from rangekeeper.market import generation as market

plan = market.make_plan(
    periods=periods,
    seed=23,
    components=(
        market.make_trend(growth_rate=0.02),
        market.make_volatility(volatility_per_period=0.03),
        market.make_cyclicality(space_amplitude=0.25),
        market.make_noise(lower=-0.02, upper=0.02),
        market.make_black_swan(likelihood=0.02, impact=-0.25),
    ),
)
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
