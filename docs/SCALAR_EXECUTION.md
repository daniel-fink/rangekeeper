# Scalar execution with Pyomo and HiGHS

Step 5 implements **actual affine feasibility execution** in `rangekeeper.execution`.
The executor reads the canonical Model and an additive Specification composition,
lowers declared mathematics, solves in a separate process, independently evaluates
the original expressions on serialized candidate quantities, and publishes accepted
Model revisions followed by finalized Runs. LinkML remains the field authority.

The first checkpoint produces capital value **11,000,000 AUD** and NOI
**550,000 AUD/year**. New Specification revisions pinned to that actual output
produce rent **27,500 AUD/dwelling/year** and NOI **500,000 AUD/year**. The previous
recorded rent of 30,000 remains an observation in the input snapshot and does not
fix the inverse solve. [Retained evidence](research/scalar-execution/README.md)
contains authentic Runs, Models, batch accounting and verification commands.

## Use the library

Install the optional backend, plus YAML if loading those fixtures, from this checkout:

```sh
python -m pip install './src[execution,yaml]'
```

The backend pins are `pyomo==6.10.1` and `highspy==1.15.1`. Importing
`rangekeeper` or `rangekeeper.execution` does not load either backend. Pyomo/HiGHS
load in a child process when solving. Pint may load NumPy during unit operations
when NumPy is installed. Existing legacy dependency metadata is otherwise unchanged.

```python
from pathlib import Path
from rangekeeper import Model, Specification
from rangekeeper.execution import Executor
from rangekeeper.io import DirectoryStore, yaml

examples = Path("schema/examples")
store = DirectoryStore(Path("scalar-revisions"))
store.put(yaml.read(examples / "model.yaml", kind=Model))
store.put(yaml.read(examples / "specification-common.yaml", kind=Specification))
specification = yaml.read(examples / "specification-composed-forward.yaml",
                          kind=Specification)
run = Executor(store).execute(specification)
if run.report.status.solution == "feasible":
    output = store.load_model(run.record.outputs[0])
```

`Executor(store, *, backend=None, units=default_units, tolerances=Tolerances())`
supports `MemoryStore`, `DirectoryStore` or a compatible `RecordStore`.
`execute(specification: Specification) -> Run` stores the supplied root after
reference-graph preflight. Referenced Models, includes and cases must already be
available. Expected capability, settings and numerical outcomes appear in the Run.
Missing/wrong-kind revisions, invalid cyclic batch graphs or batch Model assertions,
storage failures and programming errors raise to the caller.

Run the complete reproducible example from the repository root, choosing a fresh
output directory:

```sh
python tools/execution/valuation.py --examples schema/examples --output /tmp/rk-valuation
```

For a source checkout without an installed package, prefix that command with
`PYTHONPATH=src`. The script executes forward, revises the shared and inverse
Specifications to pin the genuine output, executes inverse, then executes a
sequential batch. It writes standalone JSON documents plus a complete revision
store. It never reads the synthetic expected-output fixtures as results.

## Ownership and dependencies

| Module | Responsibility |
| --- | --- |
| `execution/preparation.py` | Compose/validate exact revisions, retain contributor scope, collect imposed predicates and normalize assignments to Measure units. |
| `execution/compiler.py` | Derive affine coefficients after assignments; check arithmetic capability and dimensions; retain original Constraint identity and row scaling. No Pyomo dependency. |
| `execution/evaluator.py` | Traverse original numerical expression trees. Uses no compiled coefficients or solver variables. |
| `execution/acceptance.py` | Check serialized candidate quantities, exact assignments and every original equality/bound; return dimensional residual diagnostics. |
| `execution/publication.py` | Construct a new revision, update quantity evidence, round-trip through JSON and provide a candidate resolver for pre-publication Run validation. |
| `execution/settings.py` | Resolve requested/default limits and account for unsupported or adjusted settings. |
| `execution/backends/base.py` | Narrow problem/result protocol; a backend candidate is a claim awaiting acceptance. |
| `execution/backends/pyomo.py`, `_worker.py` | Parent deadline and private numerical JSON protocol; child builds Pyomo variables/constraints, invokes HiGHS and reports observed status/options/versions/counts. |
| `execution/executor.py` | Attempt orchestration, sequential batches, status/evidence construction, output-before-Run persistence. |

Derived preparation/compiler/result objects are runtime operations, not a second
authoritative field schema. Domain classes do not import execution or solvers.
The existing public Run validator now accepts physically equivalent assignments
through explicit conversion; its raw conformance entrypoint keeps strict defaults.
Failed composition cases remain accountably visible within batch Runs.

## Supported mathematics

The first slice supports Model-owned scalar Measurements with explicit fixed and
unknown roles, quantity literals, references, negation, addition, subtraction,
multiplication with at least one fixed expression, division by a nonzero fixed
expression, and powers that remain affine after assignment. Constraints support
equality, nonstrict upper/lower bounds, conjunctions and Boolean constants.

All Model and Specification Constraints are imposed. Unused reporting expressions
remain passive, including the fixture's area query. No stored amount supplies a
missing role. Estimates are reported as unused by this simplex feasibility method.
Canonical units come from each Value's Measure; conversion is explicit and
equations must compare compatible dimensions. Multiplicative arithmetic that would
require unsupported offset-unit handling is rejected.

The adapter explicitly rejects nonlinear unknown products/divisors/powers, strict
comparisons, disjunctions, function calls, selections, imposed queries, ordered
optimization objectives and Specification-local Value publication. Rich temporal
Values, structural interventions, scenario generation and graph consumer migration
remain later checkpoints. It never substitutes hard-coded valuation formulas.

## Settings, limits and conclusions

- Default limits are **30 seconds** and **100,000 simplex iterations** per leaf.
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
not the lowered rows. Copied assignments and Boolean assertions are exact. For
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

## Next checkpoint

Step 6A/6B now implements [Model-backed graph views and reductions](GRAPH_MODEL.md).
Next adapt tables, presentation adapters and workflows to the canonical Model,
then retire their old domain implementation
under the existing [consumer migration map](DOMAIN_MIGRATION_MAP.md). Richer mathematics
and optimization remain explicitly scoped extensions. No commit or push is part of
this local execution implementation.
