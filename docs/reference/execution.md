# Scalar execution with Pyomo and HiGHS

The execution package implements **actual affine feasibility execution** in `rangekeeper.execution`.
Execution reads the canonical Model and an additive Specification composition,
lowers declared mathematics, solves in a separate process, independently evaluates
the original expressions on serialized candidate quantities, and returns an
`Outcome`. `execute` also publishes accepted Model revisions followed by
finalized Runs. LinkML remains the field authority.

## Execute an investigation

Install the `execution` extra; YAML fixtures also need the `yaml` extra. See the
[installation guide](../guides/installation.md). Importing `rangekeeper` or
`rangekeeper.execution` does not load Pyomo or HiGHS. They load in the solve
worker. `pyproject.toml` declares the supported version ranges. The worker does
not refuse other versions; the Run evidence records the Pyomo and HiGHS versions
that it found.

| Function | Writes | Returns |
| --- | --- | --- |
| `solve(*, specification, resolver=None, config=None)` | Nothing | An `Outcome` |
| `execute(*, specification, store, config=None)` | The case Specifications of a batch, then the Specification, then for each case its outputs and then its Run, cases before their batch | The same `Outcome` |

Without `resolver`, `solve` resolves the documents that made the Specification:
the Model revision that `model.specify()` pinned, the Specification itself, and
what the Specification's own resolver supplies, such as its includes. Each
chained call (`fix`, `free`) keeps them, so `solve(specification=back)` needs no
store. A Specification read from data keeps none of them; pass `resolver` for
it, or a missing revision raises `MissingReferenceError`. `resolver` is any
`DocumentResolver`, for example a `MemoryStore`; it must supply the Models,
includes and cases that the Specification names. `store` is a
`MemoryStore`, `DirectoryStore` or a compatible `RecordStore`. `config` is an
[`ExecutionConfig`](#configuration); without it, the defaults apply. Each Run
records the backend as a `solver` implementation, with its registered name and
fingerprint. Expected capability, settings and numerical outcomes appear in the
Run. Missing or wrong-kind revisions, invalid cyclic batch graphs or batch Model
assertions, storage failures and programming errors raise to the caller; when
solving raises, `execute` writes nothing.

An `Outcome` holds the finalized `run`, the accepted `outputs` in the order of
`run.record.outputs`, and for a batch one Outcome in `cases` for each direct
case. `walk()` yields each case before its batch. See
[read an Outcome](#read-an-outcome).

Each execution validates once ([#132](https://github.com/daniel-fink/rangekeeper/issues/132)):

| Check | When it runs |
| --- | --- |
| Batch graph | Once, in `resolve_cases` |
| Composition | Once for each leaf, in `resolve_cases` |
| Specification against its Model | Once for each leaf, in `validate` |
| Candidate Model | Once for each candidate, when `make_candidate` builds it |
| Run tree | Once for each execution: one validation of the root Run, as `rangekeeper.run.validate` does, with the unstored outputs and case Runs laid over the resolver (`Overlay`). It reuses the compositions and Specification checks above |

`execute` runs this validation against `store` before it puts anything, with the
unit system of the input Model as a store does. It marks each Run as validated
against that store, so `store.put` does not validate it again; another store
validates it in full. Run validation still checks the input Model and each output
Model for the publication rules; a Model does not keep the result of its
construction check.

Use the [examples guide](../guides/examples.md) for the complete valuation procedure and
[its source](../../examples/execution/valuation.py). It executes forward, revises the
shared and inverse Specifications to pin the actual output, executes inverse,
then executes a sequential batch. Synthetic expected-output fixtures do not stand
in for execution results.

## Read an Outcome

Read a solved value by its key, its dotted key, or the text of its Value UUID:
each key that `Model.value(key=)` takes. A scalar value gives a
`Quantity`; a Flow value gives its `Flow`:

```python
outcome = rk.execution.solve(specification=back, resolver=store)
outcome.raise_for_status()
outcome["land_cost"]  # a Quantity in AUD
outcome["project.land_cost"]  # the same value, by its dotted key
```

| Member | Leaf | Batch |
| --- | --- | --- |
| `outcome["key"]` | The solved value. Without an output, the error of `raise_for_status()` | `ContractError`, `batch.unsupported`: read a case |
| `quantity(reference)` | The solved Quantity of a scalar Value or a Movement, by `Reference` or UUID | `ContractError`, `batch.unsupported` |
| `model` | The accepted output Model. Without one, the error of `raise_for_status()` | `ContractError`, `batch.unsupported` |
| `status` | A `Status`, from the Run report | The status of the first leaf case, in `walk()` order, that is not `FEASIBLE`; else `FEASIBLE` |
| `raise_for_status()` | Returns the Outcome when its status is `FEASIBLE`; otherwise raises | Raises for the first leaf case that is not `FEASIBLE` |
| `free_unknowns` | The keys of the free values that the equations do not determine | `ContractError`, `batch.unsupported` |
| `diagnostics` | The Run's diagnostics, in report order | The batch Run's diagnostics |
| `evidence` | The typed solver `Evidence` | `ContractError`, `batch.unsupported` |
| `key` | The name of the solved Specification: for a case, its case key. None when it has no name | The same |
| `case(key=)` | `ContractError`, `batch.required` | The Outcome of the direct case with that key. No such case raises `MissingReferenceError` (`kind="Outcome"`, `by="key"`) with the keys that exist |
| `table(*keys)` | One row | One row for each leaf case, in `walk()` order |
| `stream(*keys)` | A `Stream` of the solved Flows, named by key. A scalar value raises `ContractError` | `ContractError`, `batch.unsupported`: read a case |

`rk.execution.Status` has one member for each result:

| `Status` | Run report | `raise_for_status()` raises |
| --- | --- | --- |
| `FEASIBLE` | Solution `feasible`, and no `underdetermined` or `uniqueness_not_assessed` diagnostic | Nothing |
| `UNDERDETERMINED` | Solution `feasible`, with an `underdetermined` or `uniqueness_not_assessed` diagnostic: the equations leave some unknowns free, with or without bounds | `OutcomeError`, with the code of that diagnostic |
| `INFEASIBLE` | Solution `infeasible` | `OutcomeError`, code `solver_termination` |
| `LIMITED` | Completion `limited`, with no accepted candidate | `AttemptDeadlineError` for `attempt_deadline`; else `OutcomeError`, code `solver_termination` |
| `INVALID` | Failed, with `specification_invalid` | `ValidationError`, with the validation issues of the attempt |
| `FAILED` | Failed, with `numerical_failure`, `numerical_rejection`, `active_side`, `backend_unavailable` or another error diagnostic, or with no error diagnostic | `NumericalError` or `BackendUnavailableError`; else `OutcomeError` |
| `UNSUPPORTED` | Failed, with the code of an `UnsupportedError`: `unsupported_capability`, `nonaffine_unknowns`, `symbol_limit` or `constraint_limit` | `UnsupportedError` with that code, `document_id`, `targets`, `equation` and `unknowns` |

The error class comes from the same `FAILURES` row as the status. Each error
carries the code of the diagnostic that gives the reason, and the fields that
the attempt wrote into that diagnostic's `values`: a `ValidationError` has
every issue of the attempt, with its code, path, targets and values.
`OutcomeError` also has `status`. In an underdetermined Outcome, `outcome["key"]`
still reads every value; a free unknown holds one candidate value.

`free_unknowns` names every undetermined unknown, in unknown order (D7). An
unknown is undetermined when its value can change while every equality row still
holds. In lesson 02's loose back door, freeing both the land cost and the rent
factor leaves one degree of freedom along a line through all seven chained
values, so all seven are named; fixing any one of them determines the rest. A
bound that reads one of these values can still restrict it; the diagnostic is
then `uniqueness_not_assessed`, and the status is still `UNDERDETERMINED`.

`table(*keys)` returns a [Table](tables.md) with the columns `case`, `status`
and one column for each key: the Quantity of a scalar value, or the Flow of a
Flow value. `case` is the case key, with the keys of nested batches joined by
`/`; a leaf gives its own key. A case without an output has None for each value,
and its `status` says why.

```python
cases_outcome = rk.execution.solve(specification=base.cases(cases=cases))
cases_outcome.table("unlevered_npv")  # one row for each case
cases_outcome.case(key="weak").stream("land", "works")
```

`Evidence` holds the backend's `termination` (None when no backend ran), the
backend's own `backend` evidence, `equality_rank` and `unknown_count` from the
rank analysis of an underdetermined solve, and the Run's `implementations`. It
reads stored and converted Runs too: `limit` and `error` from a Run before
1.0.0b1 are `LIMITED` and `FAILED`. A missing word, as in a Run that
`tools/upgrade` converted, or a backend word of a 1.0.0a1 Run is `UNKNOWN`, and
`backend` keeps that word.

## Compare Outcomes

`rk.execution.compare(outcomes=, keys=, baseline=None)` compares two or more
named Outcomes on some scalar keys with one call (D30). Without `baseline` it
returns a `SideBySide`; with `baseline`, the name of one of the Outcomes, it
returns a `Paired`. Each displays as a table with the `calculations` extra:

```python
rk.execution.compare(
    outcomes={"Front door": front_outcome, "Back door": back_outcome},
    keys=["land_cost", "rent_factor", "noi", "mortgage"],
)
```

A `SideBySide` compares leaf Outcomes. `values` is a `Table` with a `key`
column and one column for each Outcome, and `select(*keys)` gives the same
comparison on some of its keys.

A `Paired` pairs each other Outcome with the baseline:

| Member | Result |
| --- | --- |
| `compared` | The names of the Outcomes that are not the baseline |
| `pairs(outcome=)` | The `Pair`s of one Outcome: each `member`, the `baseline` member it pairs with, and its `case` key (None when both are leaves) |
| `difference(outcome=, key=)` | The paired differences, value less baseline, in the baseline's units |
| `differences` | A `Table`: `outcome`, `key`, `case`, `value`, `baseline` and `difference` for each pair |
| `summary()` | A `Table`: `outcome`, `key`, `count`, `mean`, `minimum`, `maximum` and `share_above_zero` of the paired differences |
| `select(*keys)` | The same comparison on some of its keys |
| `where(**values)` | The comparison of the pairs whose compared member has these values; a list means any of them, and Quantities compare after unit conversion |

Each member is one leaf case, in `walk()` order. The cases of two batches pair
by case key, the `case` column of `Outcome.table`: the keys of nested batches
joined by `/`, or the position of a case without a key. A leaf pairs with every
case of the other side. Neither type has a public constructor: make them with
`compare`.

| Failure | Error |
| --- | --- |
| A key that names no value of an Outcome, or that the comparison does not have | `MissingReferenceError` (`kind="Value"`, `by="key"`) |
| A baseline or outcome name that is not compared | `MissingReferenceError` (`kind="Outcome"`, `by="name"`) |
| A Flow value | `ContractError`, `comparison.scalar` |
| A batch without `baseline` | `ContractError`, `comparison.batch` |
| Batches with different case keys, or a key that two cases share | `ContractError`, `comparison.cases`, with `missing` and `extra`, or `repeated`, in `values` |
| `where` keeps no case of an Outcome | `ContractError`, `comparison.empty` |
| Fewer than two Outcomes, or a repeated key | `ContractError` |
| A wrong Python type, such as one string for `keys` | `TypeError` |

`by`, `by_case` and `distribution(outcome=, key=)` follow with paths
([#296](https://github.com/daniel-fink/rangekeeper/issues/296),
[#310](https://github.com/daniel-fink/rangekeeper/issues/310)).

## Configuration

`ExecutionConfig` is the one public configuration of an execution, and the one
source of its defaults. It is frozen.

| Field | Default | Meaning |
| --- | --- | --- |
| `backend` | `"pyomo-highs"` | A `Backend`, or the name of one in `execution.backends.registry` ([extension points](extensions.md)) |
| `units` | `None` | The [unit system](units.md) of each case. Without it, each case uses the unit system of its input Model |
| `limits` | `Limits()` | The default budget of each leaf: `time_limit=30` seconds, `iteration_limit=100000`, `symbol_limit=10000`, `constraint_limit=20000`. A Specification's `settings` replace a limit for its own cases. `Limits` refuses a value that is not positive and finite |
| `tolerances` | `Tolerances()` | The policy of independent verification; see [independent acceptance](#independent-acceptance-and-immutable-publication) |
| `backend_options` | `{}` | String keys and JSON scalar values that go to the backend unchanged |

`pyomo-highs` reads `backend_options` as HiGHS options. They replace the
worker's defaults, and the `solver_termination` evidence records the options that
HiGHS received. The backend sets `output_flag`, `log_to_console`, `log_file`,
`threads`, `time_limit` and `simplex_iteration_limit` itself: an attempt that
asks for one of them fails with an `unsupported_capability` diagnostic.

## Stages

Execution runs as typed stages ([ADR-013](../decisions/013-execution-and-extensions.md)).
Each stage is a function in `rangekeeper.execution`. No stage writes to a store,
and only the backend starts a process. `solve` calls the stages for each case;
`execute` then stores the results.

| # | Stage | Input | Result | Raises |
| --- | --- | --- | --- | --- |
| 1 | `resolve_cases(*, specification, resolver)` | The root Specification | `Cases`: the documents, the pinned Models, the `compositions` of the leaves that compose and the `failures` (a `ValidationError` each) of those that do not. `Cases` is also a resolver | Missing or wrong-kind revisions, cycles, a contradicted batch Model pin. A leaf whose composition fails is in `failures` |
| 2 | `validate(*, composition, resolver, units=None)` | One composition | `Validation`: the `report`, the `composition`, the input `model` and the `units` | Nothing for a content problem; it is an issue in the report |
| 3 | `bind_roles(*, validation, checkpoint=)` | A `Validation` | `Binding`: assignments in Measure units, unknowns, assertions and rule evidence | `ValidationError` for an invalid report; `UnsupportedError` |
| 4 | `build_problem(*, binding, limits=None, checkpoint=)` | A `Binding` | `AffineProblem`: `variables`, unscaled `rows` (each with a `Relation` and its original Constraint; `equalities` and `bounds`) and its `Analysis`: `equality_rank`, `unknown_count`, the `undetermined` unknowns and those of them that a bound reads (`bounded`) | `UnsupportedError`, with the `symbol_limit` or `constraint_limit` code when the problem exceeds `limits`, or for a row that is not affine; `NumericalError` |
| 5 | `Backend.solve(*, problem, limits, remaining, options)` | An `AffineProblem` | `backends.BackendResult`: a `Termination`, the candidate values, the applied limits, the backend's diagnostics and its raw evidence | `BackendUnavailableError`, `NumericalError`, `UnsupportedError` for a refused option or row |
| 6 | `make_candidate(*, binding, unknowns, run_id)` | Solved values | A candidate Model revision, round-tripped through JSON | `NumericalError` |
| 7 | `verify(*, binding, candidate, tolerances=Tolerances())` | The candidate | `Verification`: `passed` or not, with residual diagnostics | `NumericalError`, `UnsupportedError` |
| 8 | `assemble(*, specification, report, id, output)`; `assemble_batch(*, specification, cases)` | The report of one leaf; the Outcomes of a batch's cases | An `Outcome` with the finalized Run. Nothing is resolved or validated | `ValidationError` for a Run that is not locally consistent |

Run validation is its own step after stage 8: `rk.run.validate(run=outcome.run,
resolver=rk.execution.Overlay(resolver=resolver, models=..., runs=...))`. The `Overlay`
returns the unstored outputs and case Runs, and reads everything else from the
resolver, so nothing is stored before the Run is valid. `solve` validates the
whole tree once this way.

`solve` does not run stage 4 alone. When a row is not affine under the fixed
values, it builds the problem in stages ([staged solve](#staged-solve)), and the
Run's trace records each stage. A `max` or `min` call that reads an unknown takes
an active side first ([piecewise equations](#piecewise-equations)). The public
stages give the problem of one stage.

`checkpoint` is a callable that raises `AttemptDeadlineError` when the attempt's
time limit has passed. The stages call it between steps.

## Ownership and dependencies

| Module | Responsibility |
| --- | --- |
| `execution/planning.py` | Stage 1: the case graph, the pinned Models and one composition for each leaf. |
| `execution/preparation.py` | Stages 2 and 3: validate the composition against its exact Model, keep the contributor scope, collect imposed predicates and normalize assignments to Measure units. |
| `execution/compiler.py` | Stage 4: derive affine coefficients after assignments; check arithmetic capability, dimensions and the symbol and constraint limits; keep the original Constraint identity. No backend dependency. |
| `execution/staging.py` | The staged solve: build the affine rows' problem, read its rank analysis, solve it when it determines a deferred row's unknown, and fix the determined values for the next stage. The rounds that pick and check the active side of each `max` and `min` call. |
| `execution/piecewise.py` | Piecewise equations: find the Model's `rx.max` and `rx.min` Functions, read the active side of each call at given values, and write the equations of a set of sides and the bounds that keep them active. It solves nothing. |
| `execution/analysis.py` | Rank and free-variable analysis of the rows, in pure Python. |
| `execution/backends/base.py` | Stage 5: the narrow problem and result protocol; a backend candidate is a claim that waits for verification. |
| `execution/backends/pyomo.py`, `_worker.py` | Parent deadline and private numerical JSON protocol; child builds Pyomo variables/constraints, invokes HiGHS and reports observed status/options/versions/counts. |
| `execution/publication.py` | Stage 6: construct a new revision, update quantity evidence, round-trip through JSON and provide a candidate resolver for pre-publication Run validation. |
| `execution/acceptance.py` | Stage 7: check serialized candidate quantities, exact assignments and every original equality/bound with `model.expression.evaluation` arithmetic; return dimensional residual diagnostics without compiled coefficients or solver variables. |
| `execution/assembly.py` | Stage 8: make the Outcome of a leaf or a batch, and validate its Run against an overlay of the unstored outputs and Runs. |
| `execution/comparison.py` | `compare`, `SideBySide` and `Paired`: values side by side, or paired differences from a baseline by case key, with `summary`, `select` and `where`. |
| `execution/outcome.py` | `Outcome`: the Run, the outputs and the case Outcomes; values by key, `status`, `raise_for_status()`, `free_unknowns` and `Evidence`. |
| `execution/config.py` | `ExecutionConfig`: the backend, unit system, limits, tolerances and backend options, with one source of defaults. |
| `execution/settings.py` | `Limits`; apply a Specification's requested settings over the configured limits and account for unsupported or adjusted settings. |
| `execution/attempt.py` | One leaf attempt: the deadline, the stage calls in order, and one `except` arm for the expected failures. It stores nothing. |
| `execution/status.py` | `Status`, in a module that imports nothing from `execution`. |
| `execution/statuses.py` | `FAILURES`: one row for each expected error, with its completion, solution, `Status` and diagnostic code. `TERMINATIONS`: one row for each `Termination`. |
| `execution/pipeline.py` | `solve`: the stages for each case of a batch, in order. `execute`: `solve`, then output-before-Run publication. |
| `execution/rule/` | Finite rule evaluation over explicit observations (`execution.rule.evaluate`). The rule declarations are in `specification.rule`. See [market paths and rules](market-paths-and-rules.md). |

Derived stage results are runtime objects, not a second
authoritative field schema. Domain classes do not import execution or solvers.
The existing public Run validator now accepts physically equivalent assignments
through explicit conversion; its raw conformance entrypoint keeps strict defaults.
Failed composition cases remain accountably visible within batch Runs.

## Supported mathematics

Execution supports Model-owned scalar Measurements and finite Flow Movements with explicit fixed and
unknown roles, quantity literals, references, negation, addition, subtraction,
multiplication with at least one fixed expression, division by a nonzero fixed
expression, powers that remain affine after assignment, and calls of `rx.max`
and `rx.min` ([piecewise equations](#piecewise-equations)). Constraints support
equality, nonstrict upper/lower bounds, conjunctions and Boolean constants. Strict
comparisons, `!=`, `or` and `not` are supported only when every referenced operand
is fixed; this check precedes simplification and is repeated during acceptance.
Their fixed values decide them exactly, with no tolerance. A true one needs no
row. A false one is the row of a false constraint, `1 = 0`, so the backend proves
the problem infeasible and the Outcome is `INFEASIBLE`, as for `False`
([ADR-016](../decisions/016-safety-defaults.md#solution-outcomes),
[#153](https://github.com/daniel-fink/rangekeeper/issues/153)).

### Staged solve

A row that is not affine under the fixed values can become affine when other rows
determine one of its unknowns. In lesson 02's front door,
`effective_income = rent_factor * reference_income` has two unknowns, but
`reference_income` is a sum of products of fixed values. `solve` then solves in
stages (`execution.staging`, internal) ([#276](https://github.com/daniel-fink/rangekeeper/issues/276)):

1. Build the problem of the rows that are affine, and read its rank analysis.
2. When the analysis determines an unknown of a deferred row, solve that problem
   with the backend and fix each determined unknown to its value.
3. Repeat until every remaining row is affine. The last stage is one affine
   problem over the unknowns that remain; rows that only determined values
   satisfy are removed from it.
4. If a stage determines no unknown of a deferred row, the first deferred row
   raises its `UnsupportedError`, as without stages.

A subexpression whose references are all fixed, or determined by an earlier stage,
is evaluated as a constant. So a non-affine function of determined values, such
as a product, quotient or power, takes part in the last stage. The candidate
holds the backend's values and the determined values, and verification checks
every original row against it. An earlier stage that does not end with a feasible
candidate, for example a proof of infeasibility, ends the attempt with its own
result. Each earlier stage adds a `solve` step to the trace; only the last backend
result gives the `solver_termination` evidence. A problem without such rows is
one stage, unchanged.

### Piecewise equations

A call of `rx.max` is the largest of its operands, and a call of `rx.min` the
smallest. Each is a call of a Function of the Model's definitions with the code
`rx.max` or `rx.min`, with two or more positional operands. In lesson 03 the
loan takes what the equity cannot cover:
`loan_principal = rx.max(0 AUD, funding_need - equity)`
([D2](../../examples/walkthrough/proposed/README.md#decisions)). The
equation-function catalogue gives these Functions to equation text and `rx`
([#309](https://github.com/daniel-fink/rangekeeper/issues/309),
[#278](https://github.com/daniel-fink/rangekeeper/issues/278)); a Model that
declares a Function with one of these codes can call it in its records.

A call whose references are all fixed, or determined by an earlier stage, is a
constant. A call that reads an unknown is affine once one of its operands is its
**active side**. `solve` then works in rounds (`execution.staging`, internal)
([#308](https://github.com/daniel-fink/rangekeeper/issues/308)):

1. The first sides are the active sides where each unknown is zero.
2. A round solves the affine problem of its sides, in stages, and reads the
   active side of each call at that solution. A side that holds within a tie
   tolerance (`1e-6` in the units of the call's first operand, plus `1e-9` times
   the larger magnitude) stays.
3. When the sides of the solution are the sides of the round, they hold. The
   last problem is the problem of those sides with one bound for each other
   operand: the side of a `max` is at least each other operand, and the side of
   a `min` at most. The backend solves it, and verification checks every
   original equation, with each call at the active side of the candidate's
   values. Verification does not use the sides that the solve picked.
4. Otherwise the next round tries the sides of the solution. After an
   infeasible round, each call whose side reads no unknown, such as `0 AUD` in
   `30 AUD = max(0 AUD, need - equity)`, takes its active side among the
   operands that read one.

A wrong side is reported, not hidden. When sides repeat, when 20 rounds give no
sides that hold, or when an infeasible round has no side to change, the attempt
fails with an `active_side` diagnostic and `Status.FAILED`;
`raise_for_status()` raises `NumericalError` with the code `ACTIVE_SIDE`. Its
`targets` are the Constraints whose sides disagree; after an infeasible round,
each Constraint with a call that reads an unknown. This proves nothing about
the equations: they can have a solution with other sides. The solve is
`INFEASIBLE` only when the rows without such a call are infeasible on their own.

Each round's solve adds a `solve` step to the trace, and the formulation step
gives the number of calls and rounds. A determined result is determined at the
sides that the solve found; the solve does not search the other sides. A bound
that keeps a side active reads the unknowns of its operands, so an unknown that
only such a bound restricts is underdetermined, with the code
`uniqueness_not_assessed`.

All Model and Specification Constraints are imposed. Unused reporting expressions
remain passive, including the fixture's area query. No stored amount supplies a
missing role. Estimates are reported as unused by this simplex feasibility method.
Canonical units come from each scalar Value's Measure or Flow units; conversion is explicit and
equations must compare compatible dimensions. Multiplicative arithmetic that would
require unsupported offset-unit handling is rejected.

After staging, the adapter explicitly rejects nonlinear unknown products/divisors/powers
with a `nonaffine_unknowns` diagnostic. Its `values` give the `equation` text and
the keys of the `unknowns` in the term that is not affine. It also rejects strict
comparisons, `!=`, disjunctions and negations involving unknowns, calls of
Functions other than `rx.max` and `rx.min`, selections, imposed queries, ordered
optimization objectives and Specification-local Value publication. Rich temporal
Values and market path generation follow the [temporal contract](market-paths-and-rules.md).
Structural interventions are unsupported. Execution never substitutes hard-coded
valuation formulas.

## Settings, limits and conclusions

- Default limits are **30 seconds**, **100,000 simplex iterations**, **10,000 symbols**
  and **20,000 affine constraints** per leaf. `ExecutionConfig.limits` changes
  these defaults; a Specification's `settings` replace them for its cases. An attempt that exceeds the symbol or
  constraint limit fails with a `symbol_limit` or `constraint_limit` diagnostic.
  Requested `iteration_limit` maps to HiGHS simplex iterations; presolve reductions
  are separate. The `pyomo-highs` backend clamps a request above HiGHS's integer
  maximum, 2147483647, with a `settings_adjusted` diagnostic, and records the
  clamped value in the effective Runtime Settings.
- `time_limit` supplies the scalar-attempt preparation/solver budget. The child
  receives the remaining time after preparation; the parent kills and reaps a worker
  that exceeds it, including worker startup/imports. Reference preflight, document
  construction/validation, independent acceptance and persistence are synchronous;
  there is no hard deadline on the complete API call. Large expression trees can
  make structural validation expensive before a worker starts.
- The generic `relative_tolerance` request has **no justified mapping** to the
  chosen LP solver's absolute feasibility criteria. It is reported as unapplied
  with `settings_adjusted`, and omitted from effective Runtime Settings. It is
  never silently treated as an absolute tolerance or an acceptance guarantee.
- HiGHS uses deterministic, single-thread simplex with presolve, random seed 0,
  and absolute primal/dual feasibility tolerances of `1e-7` on compiled rows.
  These are HiGHS limits, so they live in the `pyomo-highs` backend, not in
  `build_problem`. The backend divides each row by `max(1, largest absolute
  coefficient)`. It refuses a row with scaled nonzero coefficients at/below
  `1e-12`, or constant magnitude at/above `1e19`, with an `unsupported_capability`
  diagnostic for its Constraint, rather than silently dropping it or reading it
  as an infinite bound.
- Every attempt records its termination, actual available implementation versions,
  effective settings, timing, solver option mapping, observed iteration count,
  row scaling and ordered trace. The `values` of the `solver_termination` and
  `solver_scaling` diagnostics hold this evidence as JSON, and each
  `settings_adjusted` diagnostic names its settings in `values.settings`
  ([Run diagnostics](errors.md#run-diagnostics)). A worker killed before returning
  evidence does not acquire an invented solver result, count or implementation
  invocation.

Only an independently accepted candidate produces `solution: feasible` and outputs.
Generic code reads only the backend's `Termination`:

| `Termination` | Completion | Solution | `pyomo-highs` conditions |
| --- | --- | --- | --- |
| `FEASIBLE` | completed | `feasible` when verification accepts the candidate | `convergenceCriteriaSatisfied` |
| `INFEASIBLE` | completed | `infeasible`, for the compiled affine problem | `provenInfeasible` |
| `LIMITED` | limited | `feasible` only for an accepted candidate, else `unknown` | `maxTimeLimit`, `iterationLimit`, `objectiveLimit`, a killed worker |
| `FAILED` | failed | `unknown` | `error`, `interrupted` |
| `UNKNOWN` | completed | `feasible` only for an accepted candidate, else `unknown` | any other condition |

`execution.statuses.TERMINATIONS` holds this table. The `solver_termination`
evidence keeps the backend's own condition as `termination_condition`.

An expected error ends an attempt with a failed Run, not an exception.
`execution.statuses.FAILURES` maps each one; any other error raises to the caller.
"Bound" means that `bind_roles` returned; "solved" means that the backend returned.
The `Status`, the diagnostic code and the raised error of a failure change
together in this one table: `Outcome.status` reads the `Status` of a failed
attempt's decisive code from it, and `raise_for_status()` reads the error class.
The decisive diagnostic is the last one with a code of this table, whatever its
severity, or else the last error. A code that the table does not name gives
`FAILED`.

| Error | Completion | Solution | `Status` | Diagnostic code | `raise_for_status()` raises |
| --- | --- | --- | --- | --- | --- |
| `AttemptDeadlineError` | limited | `not_assessed` | `LIMITED` | `attempt_deadline` (warning) | `AttemptDeadlineError` |
| `ValidationError` | failed | `not_assessed`; `unknown` once bound | `INVALID`; `FAILED` once bound | `specification_invalid`; `numerical_rejection` once bound | `ValidationError`; `NumericalError` once bound |
| `UnsupportedError` | failed | `not_assessed`; `unknown` once solved | `UNSUPPORTED` | The error's own code: `unsupported_capability`, `nonaffine_unknowns`, `symbol_limit` or `constraint_limit` | `UnsupportedError` |
| `UnitError` | failed | `not_assessed`; `unknown` once solved | `UNSUPPORTED` | `unsupported_capability` | `UnsupportedError` |
| `BackendUnavailableError` | failed | `not_assessed` | `FAILED` | `backend_unavailable` | `BackendUnavailableError` |
| `NumericalError` | failed | `unknown` | `FAILED` | The error's own code: `numerical_failure`, or `active_side` when no active side of each `max` and `min` holds ([piecewise equations](#piecewise-equations)) | `NumericalError` |
| `ArithmeticError` | failed | `unknown` | `FAILED` | `numerical_failure` | `NumericalError` |

`Attempt.fail` builds the diagnostic of each expected failure.
`statuses.diagnosed` copies the error's structured fields into the diagnostic's
`values`: the `equation` and `unknowns` of an `UnsupportedError`, and each
issue of a `ValidationError`. `statuses.rebuilt` reads them back into the
error that `raise_for_status()` raises
([Run diagnostics](errors.md#run-diagnostics)).

Limits, ambiguous termination and solver failure do not
prove infeasibility. A zero-objective feasibility solve establishes no preference
optimum. `build_problem` computes the equality rank and the undetermined unknowns in
pure Python, for every backend: Gaussian elimination on rows divided by their
largest coefficient, where an entry at or below `max(rows, unknowns)` times the
machine epsilon counts as zero. Bounds may constrain otherwise free directions,
so rank alone is not a uniqueness proof. `Analysis.bounded` names the
undetermined unknowns that an inequality row reads. The diagnostic references
the free unknowns that the equations do not determine, as `free_unknowns` reads
them: its code is `uniqueness_not_assessed` when `bounded` is not empty, and
`underdetermined` otherwise. Both give `Status.UNDERDETERMINED`, because no
check proves that a bound fixes a value. `pyomo-highs` gives each free unknown
the value zero.

## Independent acceptance and immutable publication

The proposed Model is reconstructed through the public JSON codec before numerical
checking. The evaluator reads its quantities and the original expression trees,
not the lowered rows. Copied assignments, Boolean assertions and supported strict comparisons are exact. For
each numerical comparison the default tolerance is:

```text
1e-8 + 1e-9 * max(abs(left), abs(right))
```

Both residual and tolerance use that comparison's evaluated left-side units. This
is an explicit absolute floor of `1e-8` of that unit plus a relative term; it is not
a universal monetary tolerance. `ExecutionConfig(tolerances=Tolerances(absolute=..., relative=...))`
changes this acceptance policy independently of Specification/solver settings. Diagnostics state
the signed left-minus-right residual, dimensional tolerance, relation and outcome.

Accepted revisions retain declarations, definitions, unrelated quantities, original
equations and lineage. Temporary Specification mathematics stays in the Specification.
Old provenance Claims remain; Facts for written Values refer to new method-labelled
Claims describing the accepted assignment/solution and its Run/Specification. This
uses existing schema fields and does not introduce a typed cross-document provenance
contract. Constant-only feasible revisions record a fresh feasibility Claim.

`execute` validates the Run tree before it stores anything, then stores each
output first, then its finalized Run. A rejected candidate is never an output, so
it is never published. As with the stores, there is no multi-document
transaction: IO failure can leave a complete accepted output or completed child
Run. Every direct batch case has its own
Run, including failures; parent outputs are exactly the unique union of child outputs.

## Related boundaries

[Graph views and reductions](system.md), [tables](tables.md) and source applications
consume canonical Models independently of numerical execution. Nonlinear solving,
optimization and structural interventions require separate capability and acceptance
contracts. See [verification](../contributing/verification.md) for current checks.

## Implementation identity

`execution.implementation` records distinct compiler and evaluator fingerprints.
Each manifest includes its semantic Python sources, packaged schema resources,
and relevant library versions. The sources are the static import closure of the
role's entry modules in `rangekeeper`: `shared.fingerprints.import_closure` reads
the import statements with `ast` and does not import the modules. Shared
arithmetic changes alter both identities. Comments and docstrings do not. A
missing entry or imported module fails explicitly.
Each Run with a Runtime also records the numerical convention for currency
amounts as `Implementation(kind=convention, name="rangekeeper.money",
version=money.CONVENTION)` ([ADR-023](../decisions/023-decimal-money.md)).
Version `1` means float64 inside, `math.fsum` for sums, `to_number` correctly
rounded and `to_amount` at 15 significant digits, half even. Acceptance compares
assignments exactly and other values in float64 with its tolerances; it never
rounds to minor units. Publication copies each assigned amount without
conversion and writes each solved amount through `to_amount`. A residual or
tolerance in currency units is an amount.
Solver implementation/version evidence remains owned by the backend. The
backend's own fingerprint comes from its [registration](extensions.md#fingerprints). Workflow and
scenario calculations share hashing mechanics but retain separate manifests and
provenance contracts.
