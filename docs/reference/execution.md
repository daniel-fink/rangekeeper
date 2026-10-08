# Scalar execution with Pyomo and HiGHS

The execution package implements **actual affine feasibility execution** in `rangekeeper.run.execution`.
The executor reads the canonical Model and an additive Specification composition,
lowers declared mathematics, solves in a separate process, independently evaluates
the original expressions on serialized candidate quantities, and publishes accepted
Model revisions followed by finalized Runs. LinkML remains the field authority.

## Execute an investigation

Install the `execution` extra; YAML fixtures also need the `yaml` extra. See the
[installation guide](../guides/installation.md). Importing `rangekeeper` or
`rangekeeper.run.execution` does not load Pyomo or HiGHS. They load in the solve
worker. The pinned versions are declared in `pyproject.toml`.

`Executor(store, *, backend=None, units=default_units, tolerances=Tolerances())`
supports `MemoryStore`, `DirectoryStore` or a compatible `RecordStore`.
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

## Ownership and dependencies

| Module | Responsibility |
| --- | --- |
| `run/execution/preparation.py` | Reuse the prepared exact composition and Model, retain contributor scope, collect imposed predicates and normalize assignments to Measure units. |
| `run/execution/compiler.py` | Derive affine coefficients after assignments; check arithmetic capability and dimensions; retain original Constraint identity and row scaling. No Pyomo dependency. |
| `run/execution/acceptance.py` | Check serialized candidate quantities, exact assignments and every original equality/bound with `model.expression.evaluation` arithmetic; return dimensional residual diagnostics without compiled coefficients or solver variables. |
| `run/execution/publication.py` | Construct a new revision, update quantity evidence, round-trip through JSON and provide a candidate resolver for pre-publication Run validation. |
| `run/execution/settings.py` | Resolve requested/default limits and account for unsupported or adjusted settings. |
| `run/execution/backends/base.py` | Narrow problem/result protocol; a backend candidate is a claim awaiting acceptance. |
| `run/execution/backends/pyomo.py`, `_worker.py` | Parent deadline and private numerical JSON protocol; child builds Pyomo variables/constraints, invokes HiGHS and reports observed status/options/versions/counts. |
| `run/execution/executor.py`, `planning.py` | Sequential batches, reference resolution and one composition per leaf. |
| `run/execution/attempt.py` | Per-attempt deadline, preparation, backend result, independent acceptance and output-before-Run persistence. |

Derived preparation/compiler/result objects are runtime operations, not a second
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
Values and scenario generation follow the [temporal contract](scenarios-and-policies.md).
Structural interventions are unsupported. The executor never substitutes hard-coded
valuation formulas.

## Settings, limits and conclusions

- Default limits are **30 seconds**, **100,000 simplex iterations**, **10,000 symbols**
  and **20,000 affine constraints** per leaf.
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
  row scaling and ordered trace. A worker killed before returning evidence does
  not acquire an invented solver result, count or implementation invocation.

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
a universal monetary tolerance. `Tolerances(absolute=..., relative=...)` changes this
acceptance policy independently of Specification/solver settings. Diagnostics state
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

[Graph views and reductions](system.md), [tables](tables.md) and [source workflows](workflow.md)
consume canonical Models independently of numerical execution. Nonlinear solving,
optimization and structural interventions require separate capability and acceptance
contracts. See [verification](../contributing/verification.md) for current checks.

## Implementation identity

`run.execution.implementation` records distinct compiler and evaluator fingerprints.
Each manifest includes its declared semantic Python sources, packaged schema
resources, and relevant library versions. Shared arithmetic changes alter both
identities. Comments and docstrings do not. Missing declared files fail explicitly.
Solver implementation/version evidence remains owned by the backend. Workflow and
scenario calculations share hashing mechanics but retain separate manifests and
provenance contracts.
