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
| `market.series` | `Dynamics`, `generate` and `DynamicsGenerator`, the built-in path generator `dynamics` |
| `market.paths` | `Paths`, the market paths document, and `MarketPath`, one path of it: access, construction from data, means, availability and `regenerate` |
| `market.generator` | The `PathGenerator` Protocol and the `generators` registry |
| `market._components` | The components of a series (trend, cycle, volatility, noise and shock), each a small object with its parameters per Period (internal) |
| `market._kernels` | The deterministic trend, cycle, autoregression, volatility and shock kernels over supplied draws (internal) |
| `market.validation` | The checks of a `Paths` document |
| `specification.rule._declaration` | `Window`, `Where`, `Rule` and `Rules`, and the conversion to and from the stored `Rule` record (internal; `rk.specification` exports the names) |
| `specification.rule._query` | What the engine reads of a sequential rule, `RuleQuery`, and the checks that need no solve (internal) |
| `execution.rule.sequence` | Sequential evaluation: `run_rules` returns `Decisions` for one case (internal) |
| `execution.rule.provisional` | One provisional solve, with the current decided values fixed (internal) |
| `run._rule.availability` | When a Movement is known, shared by the rule engine and the trace check |
| `run._rule.predicate` | Exact Boolean truth and short-circuiting; arithmetic uses the shared evaluator |
| `run._rule.truth` | The truth of a sequential condition: true, false or unknown |
| `run._rule.trace` | The records of a decision trace, and its independent check (`check_trace`) |
| `rangekeeper_examples.investment` | The model-specific resale rule and investment author/formulate/specify/report operations |

Builders return immutable declarations. They do not solve or read recorded amounts
as hidden constants. `rk.model.formulation.declare(id=, name=, equations=, values=)`
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
| Sequential rules that read solved values | `fix(key=rule)` [declares them](#declare-a-rule), and the solve runs them [on each path](#sequential-rule-evaluation) |
| Multistage optimization | Capability rejection |

Discounting begins at exponent one by default; growth starts at the initial amount.
Rates are per declared step. Builders do not infer annualization. `growth.linear`
takes an amount increment. [Scalar execution](execution.md) defines limits,
independent acceptance, implementation fingerprints and publication.

## Market dynamics and generated paths

`rk.market.Dynamics` declares how one series moves
([#299](https://github.com/daniel-fink/rangekeeper/issues/299), D29, D31), and
`rk.market.generate(dynamics=, periods=, seed=None, count=)` makes `count` paths
of each named series over `periods`, as a `Paths` document:

```python
trend = rk.market.Dynamics(trend="2 % pa")
one_path = rk.market.generate(dynamics={"rent_index": trend}, periods=years, count=1)
cycle = trend.replace(cycle_period="10 years", cycle_amplitude="10 %")
dynamics = cycle.replace(
    volatility="5 % pa", noise="2 %", shock_probability="2 % pa", shock_size="-25 %"
)
paths = rk.market.generate(
    dynamics={"rent_index": dynamics}, periods=years, seed=1, count=500
)
```

| Parameter | Meaning | Default |
| --- | --- | --- |
| `trend` | Growth per year, `"2 % pa"` | `"0 % pa"` |
| `cycle_period`, `cycle_amplitude` | The length of a sine cycle, `"10 years"`, and half its peak-to-trough height, `"10 %"`. Give both or neither | No cycle |
| `volatility` | The standard deviation of the yearly returns, `"5 % pa"`. The returns follow an AR(1) process with coefficient 0.2, and in each Period the level reverts by 10 % of its distance from the trend | No volatility |
| `noise` | The half-width of independent uniform noise in each Period, `"2 %"` | No noise |
| `shock_probability`, `shock_size` | The chance per year of one rare shock, `"2 % pa"`, and its size, `"-25 %"`. Half of the remaining shock ends in each later year. Give both or neither | No shock |

Each parameter is a Quantity, its text or a `rk.model.Distribution` that each
path draws from once; a ratio can also be a number. Units that do not convert
raise `UnitError`, a value outside its range `ContractError`, and a cycle or a
shock with one parameter `ContractError` that names the other. `replace` returns
new Dynamics with the given parameters changed. Dynamics are values: `==`
compares their parameters.

Each series starts at 1, in `ratio` units, with a lag of zero. The trend
compounds; the volatility returns act on the level; the cycle, the noise and the
shock each multiply it by one plus their value. Rates per year convert for the
Periods: a growth `g` per year is `(1 + g) ** t - 1` in a Period of `t` years, a
volatility is `volatility * sqrt(t)`, and a shock probability `p` is
`1 - (1 - p) ** t`. The Periods must have one length (`ContractError`). On the
same draws, the components give the results of rk 0.8's market dynamics.

The series are independent: `generate` has no correlation argument (D31). Compose
markets that move together with Flow arithmetic, such as
`path["market_index"] * path["hotel_factor"]`, or with a Model equation.

Volatility, noise, shocks and distributed parameters are random, and `generate`
needs `seed`, a whole number of zero or more. Without one, it raises
`ContractError`; the message and `values["random"]` name the random components
of each series. Fixed dynamics take no seed (`ContractError`). Each path of each
series draws from its own streams, one for each random component and each
distributed parameter: `numpy.SeedSequence/PCG64`, seeded by the seed, the index
of the path and the stream identifier. The first paths are the same whatever the
count, and adding a series changes no other series. The paths are keyed
`path_1` to `path_<count>`, zero-padded to one width.

The built-in generator `dynamics` (`rangekeeper.market.DynamicsGenerator`) is
registered in `rangekeeper.market.generators`. The capture record keeps its name
and fingerprint, the parameters of each series as `PathParameter` records, the
seed, the algorithm, the streams and the Python and NumPy versions. So
`paths.regenerate(seed=1) == paths`, and `paths.regenerate(seed=2)` gives the same
generator, parameters, Periods and count with another seed.

## The market paths document

`rangekeeper.market.Paths` is a stored, immutable document of market paths
([ADR-014](../decisions/014-market-paths.md),
[#298](https://github.com/daniel-fink/rangekeeper/issues/298)). A path is one
possible history of external conditions: one Flow for each named series, over the
Periods of the document. The document stores the amounts, so a use of the paths
draws no random numbers. Its kind is `Paths`, with the record
`rangekeeper.schema.records.Paths` from [market.yaml](../../schema/market.yaml).

```python
paths = rk.market.Paths.from_flows(
    flows={
        "recovery": {"rent_index": recovery},
        "downturn": {"rent_index": downturn},
    },
    lag="1 month",
)
paths.keys  # ("recovery", "downturn")
paths["downturn"]["rent_index"]  # a Flow over the Periods of the document
paths.mean(name="rent_index")  # one Flow: the mean of each Period
paths.available(name="rent_index")  # the date on which each amount is known
paths.capture  # how the paths were made
```

| Member | Result |
| --- | --- |
| `keys`, `names`, `periods` | The path keys, the series names and the Periods, in order |
| `paths[key]` | The `MarketPath` with that key. A missing key raises `MissingReferenceError` with the keys in `candidates` |
| `path[name]` | The Flow of one series, in the units of the series. A missing name raises `MissingReferenceError` with the names |
| `mean(name=)` | The mean of a series over the paths, Period by Period, as one Flow |
| `series(name=)` | The declaration of a series: its `name`, `units` and `lag` |
| `available(name=)` | The date on which each amount is known: the end of its Period plus the lag of the series ([ADR-021](../decisions/021-sequential-decisions.md)) |
| `capture` | The `PathCapture` record: `generator`, `fingerprint`, `seed`, `count`, `parameters`, `algorithm`, `streams` and `versions` |
| `regenerate(seed=)` | The paths again from the same generator, parameters, Periods and count, with another seed |

`Paths.from_flows(flows=, lag="0 days", name=None, description=None)` makes paths
from data: a mapping from each path key to its Flows by series name. Every path
has the same names, and each Flow has the Periods of the first path and the units
of its series (`ALIGNMENT_DIFFER`). A Flow with a dated amount raises
`ContractError`. `lag` is one whole length of zero or more, such as `"1 month"`,
or a mapping from each series name to its length; a length that is not a whole
number of days, weeks, months, quarters or years raises `UnitError`. Paths from
data have no generator, so `regenerate` raises `ContractError`.

A path generator makes its paths with
`Paths.create(periods=, series=, members=, capture=, name=None, description=None)`.
The UUID of each revision is a digest of its content, without the UUID. The same
paths, capture record, name and description give the same revision, so
`paths.regenerate(seed=paths.capture.seed) == paths`; `==` compares the content.
Construction checks the document: Periods in order that do not overlap, unique
series names with known units and lags, unique path keys, one finite amount of
each series in each Period, and a capture record that agrees with the paths.
`validate()` and `check()` take the same arguments as on the other documents; a
Paths document refers to no other document.

### Path generators

A path generator satisfies `rangekeeper.market.PathGenerator`:
`generate(*, parameters, periods, seed, count) -> Paths`. `parameters` are the
`PathParameter` records of each series, a constant `quantity` or a
`distribution`. `seed` is None when nothing is random. The registry is
`rangekeeper.market.generators`, the extension point `market`
([extension points](extensions.md)); the built-in is `dynamics`. The capture
record keeps the registered name, the fingerprint and the parameters, so
`regenerate` finds the generator by its name; an unknown name raises
`UnknownExtensionError`.

### Investigation across paths

`Specification.across(paths=, series=None)` makes one case for each path: each
path series fixes the Model value with the same key, and `series=` maps the
others. A case refers to its path by UUID and key and does not copy the amounts;
its composition expands the path into assignments. Runs pin the Paths in
`run.paths`, and the Run of each case records its path key in `run.path_key`. See
[cases across market paths](specification.md#cases-across-market-paths).

### Storage

`MemoryStore`, `DirectoryStore` and the Bundle `Reader` store a Paths document
under its UUID and return it with `load_paths(id)`; the codecs read it with
`kind=rk.market.Paths`. An identical write changes nothing.

## Rule declarations and evidence

A rule is a query over a window, and a Specification stores it as a `Rule` record
([declare a rule](#declare-a-rule)). A Run stores what the rule did as one
`RuleEvidence` ([the decision trace](#the-decision-trace)). There is no public
`decide` or `DecisionHistory` wrapper.

The investment resale example decides its `sale_date` with a rule:
`stop_gain_resale_rule(model, threshold=, minimum_holding_periods=)` gives it to
`specify(model, rule=)`. The rule uses a strict factor greater than the threshold, a
minimum holding period and a sale in the final period. `author(factors=, cap_rates=)`
records the factors and capitalization rates of one market path, such as
`paths[key]["space_market_price_factors"]`. Sale includes that period's operating
cashflow and proceeds. The `holding` and `sale` Flows follow from `sale_date`, and
hold zero after it; the full market path remains recorded. These economic roles
belong to the investment example.

See [migration](../guides/upgrading.md), [record methods](records.md), and
[verification](../contributing/verification.md) for repeatable checks and their external limits.

## Sequential rule evaluation

[ADR-021](../decisions/021-sequential-decisions.md) decides each value of a rule
during the solve, on each path by itself. A Specification
[declares its rules](#declare-a-rule), `rk.execution.solve` runs them, and the Run
[records the trace](#the-decision-trace). The parameters of rules come with
[#301](https://github.com/daniel-fink/rangekeeper/issues/301). The dated slice above
stays in place until the last step of
[#300](https://github.com/daniel-fink/rangekeeper/issues/300).

### Declare a rule

A rule is a query over a window of dates. The query needs no Model:

```python
window = rk.specification.Window(earliest=date(2027, 1, 1), latest=date(2030, 1, 1))
rule = window.where(condition="rent_index >= start_trigger").first(
    otherwise=rk.duration.NEVER
)
strategy = fixed.fix(start_trigger=1.05, start_date=rule)
```

| Call | Meaning |
| --- | --- |
| `Window(earliest=None, latest=None, periods=None, timing=PeriodTiming.FIRST)` | The dates on which a rule may act. `earliest` and `latest` are inclusive, and each is a date or date text such as `"shared_start + 1 year"`. Without `periods`, a window date is each date on which a value that the condition reads becomes known. With `periods`, it is the `timing` day of each Period |
| `where(condition=)` | A condition in the equation language. It writes equality with `==`, as in `b_start == NEVER`; `=` states an equation, and here it is an error that suggests `==`. Text that does not parse raises `EquationError` |
| `first(otherwise=, then=None)` | The `Rule`: the first window date that meets the condition, or `then` on that date. `otherwise` applies when no window date qualifies. A date Value takes a date or `NEVER`; a scalar Value takes a quantity and needs `then` |
| `fix(key=rule)` | The value becomes decided. Rules run in the order that they are fixed. A later `fix` of the key replaces the rule or the value, a rule in the same position. `free(key)` removes the rule. One `fix` call can give values and rules together |
| `spec.parameters(**values)` | Declares named Specification values that rules read, such as a trigger: a Quantity, Quantity text or a bare number for a ratio. A condition or a bound reads a parameter by key, on every window date. `fix` and `cases` change it like other values, without a new Model revision. `free(key)` removes it |
| `spec.rules` | The `Rules` by key, in their order. `spec.rules[key]` is a `Rule` whose `triggers` hold the parameters that it reads. `fix` with that Rule brings each of them that the other Specification does not declare; a parameter that it declares stays. A fixed Model value that the rule reads does not come with it. A key without a rule raises `MissingReferenceError` |

`fix` reads the text against the pinned Model and stores a `rangekeeper.schema.records.Rule`
in the ordered `rules` of the Specification. The record has the `target`, and
Expressions for `condition`, `otherwise`, `then`, `earliest` and `latest`, with the
`periods` and the `timing`. `otherwise` and `then` are literals.

The ordered `parameters` of the Specification hold each `RuleParameter`, a `key` and
a `quantity`. An Expression refers to a parameter by the version 5 UUID, in the URL
namespace, of the text `rangekeeper:rule-parameter:<key>`. The solve reads the
parameters of each case in the process that solves it, and the check of a stored
trace reads them from the composed Specification of the Run.

| Failure at `fix` | Error |
| --- | --- |
| A condition that reads ahead, such as `rent_index.shift(by=-1)` | `AvailabilityError` with `key` |
| A condition that reads its own value or a later rule, or a scalar that depends on one | `ValidationError` with the code `rule_order` |
| A condition that depends on a free input | `ValidationError` with the code `rule_reads_unknown` |
| A value that is not a date or a scalar, a value of another kind than its target, a condition that is not a test, a call other than `flow.shift(by=)` in a condition, and a bound that is not a date | `ValidationError` with the code `rule_capability` |
| A name that is neither in the Model nor a parameter | `EquationError` |
| A key of `parameters` that a Value of the Model has | `ContractError` with the code `UNIQUE` |
| A new value of a parameter in units that do not convert to its units | `UnitError` |
| A parameter that an included Specification declares, given to `fix` or `parameters` | `ContractError`: change it in that Specification |
| A condition that reads a free input, or `free` of a parameter that a rule reads | `ValidationError` with the code `rule_reads_unknown` |

A Flow can be free at `fix`, because a later `across` can fix it: lesson 05 calls
`fix` before `across`. So `fix` counts each Flow as known. `across` checks the rules
again with the Movements that its paths fix, `free` checks them when it frees a
value, and `validate` and the solve check them with what the case fixes. A later
`fix` of a value alone adds what a rule can read, so it does not check them. A rule
can read a Flow that depends on a later rule, because a decision cannot change the
past, so that is not `rule_order`.

`Window` itself raises `ContractError` with `rule_capability` for `earliest` after
`latest`, for no Periods, and for `timing` without `periods`.

### The stage of a rule

`bind_roles` makes each decided value free. Then
`execution.rule.sequence.run_rules(binding=, rules=, solver=, parameters=None,
paths=None, progress=None)` takes the bound case and returns `Decisions`: the decided
values with their decision dates, the trace and the number of provisional solves.
`Decisions.bind(binding)` fixes the decided values, so the later stages solve one
affine problem that contains no rule. A case in a batch worker process runs the same
stage, with the Models and the Paths of its `Setup`. So the decisions and the trace do
not depend on the number of workers.

### The dates of a rule

| Rule | Window dates | Date on which it takes `otherwise` |
| --- | --- | --- |
| With `periods` | The `timing` day of each Period | The first date processed after `latest` or, at the latest, the end of the last Period |
| Without `periods`, reads a Flow | Each date on which an amount of the Flow is known: the end of its Period plus the lag | The next date of this calendar after `latest`. A calendar that ends takes `otherwise` on its last date, after the rules of that date |
| Without `periods`, reads no Flow | Its `earliest` and `latest` dates, and the decision date of a value that it reads | Its last date, after the rules of that date |

Every rule also takes `otherwise` on any date that is processed after its `latest`
bound, and when its `earliest` bound becomes `NEVER`. A window date outside a
literal bound has no record. A window date outside a bound that is an expression,
or a bound that reads an undecided value, gives the result `SKIPPED`.

A path that starts in 2027 has no amount that is known before 2028-01-01. So a yearly
rule on it has no window date on 2027-01-01, and its first check reads 2027 on
2028-01-01. To check on 2027-01-01, give the path the Period of 2026.

### What a rule reads

Availability follows [ADR-021](../decisions/021-sequential-decisions.md#what-a-rule-can-observe).
A condition reads Values, parameters and `flow.shift(by=)`. Another call in a
condition raises `UnsupportedError`.

- A direct reference to an undecided value is unknown. So is a date that the date
  equations determine only from undecided dates. `False and unknown` is false,
  `True or unknown` is true, and any other expression that reads an unknown is
  unknown. Only a true condition fixes the value.
- A rule reads every value of its condition on each check, also when `and` or `or`
  could decide without it. So an unavailable value always fails the case.
- A Flow that no path fixes is known at the end of its Period. A fixed Flow
  follows the same date.

### Failures

Each failure below ends one case. `Attempt` gives it a Run with the status
`FAILED`.

| Error | Code | When |
| --- | --- | --- |
| `AvailabilityError` | `observation_unavailable` | A shift to a later Movement, before any date; a value that is not known on the window date. `key` is the decided value; `available_on` and `decision_date` are the dates, when they exist |
| `ContractError` | `rule_order` | A condition reads its own value or a later rule's value, or a scalar that depends on one. A Flow can depend on one |
| `ContractError` | `rule_reads_unknown` | A condition depends on a Value that no equation defines and the case does not fix |
| `ContractError` | `rule_capability` | A rule gives another kind of value than its Value holds, a value with two rules, or a rule with no window date |
| `DecisionError` | `decision_changes_past` | A decision determines a date before its decision date, such as `marketing_start = b_start - 6 months`, or a later solution changes a Movement of a Period that ended before a decision. `values` name the decision and the date or Movement |
| `DecisionError` | `provisional_infeasible` | The provisional problem is infeasible. `values["constraints"]` gives the date constraints that the decisions break, `values["window_date"]` the date of the solve, and `values["decided"]` the decisions so far |
| `DecisionError` | `rule_capability` | A rule has no window date on this case |
| `DecisionError` | `rule_trace` | `check_trace` rejects the trace |

The `ContractError` rows raise out of the stage. `fix` and `validate` report the same
problems [as `ValidationError`](#declare-a-rule), so a solve reports them as a case
with the status `INVALID`.

A final solve that the decided dates make infeasible has the status `INFEASIBLE`,
with one `constraint_residual` error diagnostic for each date constraint that they
break. Its `values["equation"]` gives the text of the constraint, such as
`b_start >= shared_start + 1 year`. The trace stays in the Run.

### The trace check

`run._rule.trace.check_trace(rules=, checks=, facts=)` is the independent check of
one trace. It reads only the declarations, the recorded readings, the path data and
the candidate. So it can run on a stored Run, without a solve. It checks the date
order and the written order; the bounds; each reading against the path, the
candidate and its availability date; each condition against its readings; the first
true window date, or `otherwise` on a date that the window allows; that no window
date of the calendar is missing; and that the candidate holds each decided value.
`rk.run.validate` runs it on each stored Run that has an output, and reports a
failure as an issue with the code `rule_trace`. A Run without an output has no
candidate, so it has no check. The check uses the default tolerances (`1e-8` absolute,
`1e-9` relative), because a stored Run does not record `ExecutionConfig.tolerances`.

### The decision trace

```python
outcome = rk.execution.solve(specification=strategy.across(paths=paths))
outcome.decisions  # one row for each case and window date
outcome.decisions.where(key="b_start", result=rk.execution.DecisionResult.DECIDED)
outcome.case(key=paths.keys[0]).trace  # the same rows, of one case
```

| Member | Contents |
| --- | --- |
| `outcome.decisions` | A `DecisionTable` of each leaf case. Its rows are `DecisionRow` records. A case without rules has no rows, and a case that fails during its rules keeps the rows up to its failure |
| `outcome.trace` | The `DecisionTable` of a leaf Outcome. A batch raises `ContractError` with `batch.unsupported` |
| `DecisionTable.where(*, key=None, result=None)` | The rows of one rule, of one result, or of both. A key that no rule decides raises `MissingReferenceError` |
| `DecisionTable.observations` | One `ObservationRow` for each value that has an availability date: `case`, `key`, `decision_date`, `name`, `target`, `value`, `available_on` and `source`. A fixed value and a parameter are always available, and an undecided value has no value, so they have no row |
| `DecisionTable.table` | A `Table`, for display and for columns. A notebook shows it |
| `DecisionRow` | `case`, `key`, `decision_date`, `result` (a `DecisionResult`), `condition` (True, False, or None for unknown or no test), `value` (what the row fixes, else None), `observed` (each value read, by the text that reads it; None for an undecided value) and `observations` |
| `run.rule_evidence` | The stored `RuleEvidence`, or None for a case without rules |

`Report.rule_evidence` holds these stored records. LinkML defines them in
`schema/rule.yaml`:

| Record | Fields |
| --- | --- |
| `RuleEvidence` | `checks`, `decided`, `provisional_solves` and `verified`. The final solve is one solve more than `provisional_solves`. `verified` says that the trace check passed on a candidate; an output needs it |
| `Check` | `target` and `key` of the rule, `date`, `result`, `condition`, `observations`, `earliest`, `latest` and `value`. There is one for each window date and each `otherwise`. An absent `condition` is unknown, or no test. An absent bound is undecided, or no bound |
| `Observation` | `name`, `target` (the Value, or the Movement of a Flow), `source` (an `ObservationSource`: `path`, `fixed`, `parameter`, `decided` or `solved`), `value` (absent when undecided) and `available_on` (absent when always available, or undecided) |
| `DecidedValue` | `target`, `key`, `value` and `decision_date` |
| `TraceValue` | Exactly one of `quantity`, `date` and `never` |

A failed trace check is a `rule_trace` diagnostic in `Report.diagnostics`.

`rk.execution.replay` [compares the traces](execution.md#replay-a-stored-run) of a
stored Run and a new solve.

## Market path vocabulary

| Name | Responsibility |
|---|---|
| Model | Canonical immutable content and provenance |
| Paths | A captured, replayable set of market paths with its capture record |
| MarketPath | One path of a Paths document: one Flow for each series |
| Dynamics | How one series moves: trend, cycle, volatility, noise and shock |
| PathGenerator | A registered method that makes market paths from parameters |
| PathCapture | How a Paths document was made: generator, fingerprint, parameters, seed, streams and versions |
| PathParameter | One constant or distributed parameter of a generator for one series |
| PathCase | The reference of a case to one path: the Paths UUID, the path key and the Movements that each series fixes |
| Distribution | One LinkML-generated probability-distribution record |
| Binding | A local name referring to a canonical Value; the container defines scope |
| RandomStream | Recorded identity of a random sequence, separate from a Flow Stream |
| Rule | One stored rule of a Specification: its target, condition, `otherwise`, `then` and window |
| RuleEvidence | The decision trace of one case: its Checks, decided values, solve count and trace check result |

`schema/market.yaml` holds the Paths records; `schema/distribution.yaml` and
`schema/binding.yaml` contain reusable contracts. No generated field schema is
repeated in a handwritten distribution class.
