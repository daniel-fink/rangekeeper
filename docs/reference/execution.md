# Scalar execution with Pyomo and HiGHS

The execution package implements **actual affine feasibility execution** in `rangekeeper.execution`.
The executor reads the canonical Model and an additive Specification composition,
lowers declared mathematics, solves in a separate process, independently evaluates
the original expressions on serialized candidate quantities, and publishes accepted
Model revisions followed by finalized Runs. LinkML remains the field authority.

## Execute an investigation

Install the `execution` extra; YAML fixtures also need the `yaml` extra. See the
[installation guide](../guides/installation.md). Importing `rangekeeper` or
`rangekeeper.execution` does not load Pyomo or HiGHS. They load in the solve
worker. `pyproject.toml` declares the supported version ranges. The worker does
not refuse other versions; the Run evidence records the Pyomo and HiGHS versions
that it found.

`Executor(store, *, config=None)` supports `MemoryStore`, `DirectoryStore` or a
compatible `RecordStore`. `config` is an [`ExecutionConfig`](#configuration);
without it, the defaults apply. Each Run records the backend as a `solver`
implementation, with its registered name and fingerprint.
`execute(specification: Specification) -> Run` stores the supplied root after
reference-graph preflight. Referenced Models, includes and cases must already be
available. Expected capability, settings and numerical outcomes appear in the Run.
Missing or wrong-kind revisions, invalid cyclic batch graphs or batch Model
assertions, storage failures and programming errors raise to the caller.

Use the [examples guide](../guides/examples.md) for the complete valuation procedure and
[its source](../../examples/execution/valuation.py). It executes forward, revises the
shared and inverse Specifications to pin the actual output, executes inverse,
then executes a sequential batch. Synthetic expected-output fixtures do not stand
in for execution results.

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
and only the backend starts a process. `Executor` calls the stages for each case
and stores the results.

| # | Stage | Input | Result | Raises |
| --- | --- | --- | --- | --- |
| 1 | `resolve_cases(specification, *, resolver)` | The root Specification | `Cases`: the documents, the pinned Models and one composition for each leaf. `Cases` is also a resolver | Missing or wrong-kind revisions, cycles, a contradicted batch Model pin. A leaf whose composition fails keeps its `ValidationError` |
| 2 | `validate(composition, *, resolver, units=None)` | One composition | `Validation`: the report, the input Model and the unit system | Nothing for a content problem; it is an issue in the report |
| 3 | `bind_roles(validation, *, checkpoint=)` | A `Validation` | `Binding`: assignments in Measure units, unknowns, assertions and rule evidence | `ValidationError` for an invalid report; `UnsupportedError` |
| 4 | `build_problem(binding, *, limits=None, checkpoint=)` | A `Binding` | `AffineProblem`: affine rows that keep the original Constraint identity | `UnsupportedError`, with the `symbol_limit` or `constraint_limit` code when the problem exceeds `limits`; `NumericalError` |
| 5 | `Backend.solve(problem, *, limits, remaining, options)` | An `AffineProblem` | `Result`: termination, candidate values and evidence | `BackendUnavailableError`, `NumericalError` |
| 6 | `make_candidate(binding, values, *, run_id)` | Solved values | A candidate Model revision, round-tripped through JSON | `NumericalError` |
| 7 | `verify(binding, candidate, *, tolerances=Tolerances())` | The candidate | `Verification`: accepted or not, with residual diagnostics | `NumericalError`, `UnsupportedError` |
| 8 | `assemble(specification, report, *, id, output, resolver, units=None)` | The report of one leaf | The finalized Run, validated once with the output laid over the resolver | `ValidationError` |

`checkpoint` is a callable that raises `AttemptDeadlineError` when the attempt's
time limit has passed. The stages call it between steps.

## Ownership and dependencies

| Module | Responsibility |
| --- | --- |
| `execution/planning.py` | Stage 1: the case graph, the pinned Models and one composition for each leaf. |
| `execution/preparation.py` | Stages 2 and 3: validate the composition against its exact Model, keep the contributor scope, collect imposed predicates and normalize assignments to Measure units. |
| `execution/compiler.py` | Stage 4: derive affine coefficients after assignments; check arithmetic capability, dimensions and the symbol and constraint limits; keep the original Constraint identity and row scaling. No Pyomo dependency. |
| `execution/backends/base.py` | Stage 5: the narrow problem and result protocol; a backend candidate is a claim that waits for verification. |
| `execution/backends/pyomo.py`, `_worker.py` | Parent deadline and private numerical JSON protocol; child builds Pyomo variables/constraints, invokes HiGHS and reports observed status/options/versions/counts. |
| `execution/publication.py` | Stage 6: construct a new revision, update quantity evidence, round-trip through JSON and provide a candidate resolver for pre-publication Run validation. |
| `execution/acceptance.py` | Stage 7: check serialized candidate quantities, exact assignments and every original equality/bound with `model.expression.evaluation` arithmetic; return dimensional residual diagnostics without compiled coefficients or solver variables. |
| `execution/assembly.py` | Stage 8: make the finalized Run of one leaf and validate it against the candidate overlay. |
| `execution/config.py` | `ExecutionConfig`: the backend, unit system, limits, tolerances and backend options, with one source of defaults. |
| `execution/settings.py` | `Limits`; apply a Specification's requested settings over the configured limits and account for unsupported or adjusted settings. |
| `execution/attempt.py` | One leaf attempt: the deadline, the stage calls in order, and the status of each expected failure. It stores nothing. |
| `execution/executor.py` | Sequential batches, and output-before-Run persistence. |
| `execution/rule/` | Finite rule evaluation over explicit observations (`execution.rule.evaluate`). The rule declarations are in `specification.rule`. See [market paths and rules](market-paths-and-rules.md). |

Derived stage results are runtime objects, not a second
authoritative field schema. Domain classes do not import execution or solvers.
The existing public Run validator now accepts physically equivalent assignments
through explicit conversion; its raw conformance entrypoint keeps strict defaults.
Failed composition cases remain accountably visible within batch Runs.

## Supported mathematics

The executor supports Model-owned scalar Measurements and finite Flow Movements with explicit fixed and
unknown roles, quantity literals, references, negation, addition, subtraction,
multiplication with at least one fixed expression, division by a nonzero fixed
expression, and powers that remain affine after assignment. Constraints support
equality, nonstrict upper/lower bounds, conjunctions and Boolean constants. Strict
comparisons are supported only when every referenced operand is explicitly fixed;
this check precedes simplification and is repeated during acceptance.

All Model and Specification Constraints are imposed. Unused reporting expressions
remain passive, including the fixture's area query. No stored amount supplies a
missing role. Estimates are reported as unused by this simplex feasibility method.
Canonical units come from each scalar Value's Measure or Flow units; conversion is explicit and
equations must compare compatible dimensions. Multiplicative arithmetic that would
require unsupported offset-unit handling is rejected.

The adapter explicitly rejects nonlinear unknown products/divisors/powers, strict
comparisons involving unknowns, disjunctions, function calls, selections, imposed queries, ordered
optimization objectives and Specification-local Value publication. Rich temporal
Values and market path generation follow the [temporal contract](market-paths-and-rules.md).
Structural interventions are unsupported. The executor never substitutes hard-coded
valuation formulas.

## Settings, limits and conclusions

- Default limits are **30 seconds**, **100,000 simplex iterations**, **10,000 symbols**
  and **20,000 affine constraints** per leaf. `ExecutionConfig.limits` changes
  these defaults; a Specification's `settings` replace them for its cases. An attempt that exceeds the symbol or
  constraint limit fails with a `symbol_limit` or `constraint_limit` diagnostic.
  Requested `iteration_limit` maps to HiGHS simplex iterations; presolve reductions
  are separate. Requests exceeding HiGHS's integer maximum are clamped with a
  `settings_adjusted` diagnostic.
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
  Each row is divided by `max(1, largest absolute coefficient)`. Rows with scaled
  nonzero coefficients at/below `1e-12`, or constant magnitude at/above `1e19`,
  are rejected rather than silently dropped or interpreted as infinite bounds.
- Every attempt records its termination, actual available implementation versions,
  effective settings, timing, solver option mapping, observed iteration count,
  row scaling and ordered trace. The `values` of the `solver_termination` and
  `solver_scaling` diagnostics hold this evidence as JSON, and each
  `settings_adjusted` diagnostic names its settings in `values.settings`
  ([Run diagnostics](errors.md#run-diagnostics)). A worker killed before returning
  evidence does not acquire an invented solver result, count or implementation
  invocation.

Only an independently accepted candidate produces `solution: feasible` and outputs.
HiGHS's `provenInfeasible` becomes a completed/infeasible conclusion for the compiled
affine problem. Limits, ambiguous termination and solver failure do not prove
infeasibility. A zero-objective feasibility solve establishes no preference optimum.
Equality-rank deficiency is reported using NumPy's numerical SVD threshold; bounds
may constrain otherwise free directions, so rank alone is not a uniqueness proof.
Completely unconstrained Values use an explicitly reported zero initialization.

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

Full Run validation occurs against the candidate overlay before storage. The output
is stored first, then its finalized Run. A rejected candidate is never published.
As with the stores, there is no multi-document transaction: IO failure can leave a
complete accepted output or completed child Run. Every direct batch case has its own
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
