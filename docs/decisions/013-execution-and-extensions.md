# ADR-013: Execution pipeline and extension points

Status: accepted for 1.0; implementation pending. Recorded: 2026-10-26.

## Problem

- **Execution is one call that needs a store.** It always writes to the store,
  and its stages are not public.
- **Reading a solved value takes four steps and a UUID constant.**
- **The backend contract carries HiGHS vocabulary:**
  - generic code reads Pyomo termination strings;
  - rank analysis runs only inside the Pyomo worker;
  - the compiler contains HiGHS scaling limits.
- **Each solve starts a new Python process** (about one second each). The
  process is not started in isolated mode.
- **Each execution validates the same content several times.**
- **Computation fingerprints hash hand-listed source files.** The lists miss
  modules that the computation imports.
- **Each extension point uses its own mechanism.** The extension points are
  backends, scenario methods, units and geometry providers.

## Choice

### Pipeline

`rangekeeper.execution` owns the pipeline ([ADR-010](010-layers-and-packages.md)).
Each stage is a public, typed, pure function:

1. **Resolve cases:** build the case graph of a Specification and its includes
   and cases.
2. **Validate the composition** once. Pass a validated composition forward.
3. **Bind roles:** give each value its role (fixed, free, decided, estimate or
   bound). When the Specification has rules, the decide stage then evaluates
   them for each path, in date order ([ADR-021](021-sequential-decisions.md)).
   It calls stages 4 and 5 for each provisional solve.
4. **Build the problem:** make an `AffineProblem` with variables, rows,
   relations and bounds. This stage also runs rank and free-variable analysis.
5. **Solve:** the backend returns a `BackendResult`.
6. **Make a candidate:** write the solved values into a candidate Model revision.
7. **Verify:** check the candidate independently against the original
   equations, assignments and bounds.
8. **Assemble** an `Outcome`.

`solve(specification, resolver, *, config=None) -> Outcome` is pure. It does not
write to a store. `execute(specification, store, *, config=None) -> Outcome` runs
`solve` and then publishes: it puts the outputs, then the Run. The Run is
validated once.

`ExecutionConfig` holds the limits, tolerances, unit system and backend options.
It has one source of defaults.

### Reading results

`Outcome` gives direct access to the result:

- `outcome["key"]` and `outcome.quantity(reference)`;
- `.status`, `.raise_for_status()` and `.free_unknowns`;
- typed solver evidence;
- `.run` and `.outputs`.

Solver evidence is in typed fields, not JSON text inside messages
([ADR-016](016-safety-defaults.md)).

### Backend contract

A backend receives an `AffineProblem`. It returns a `BackendResult` with three
parts:
- a `Termination` value: feasible candidate, proven infeasible, limit, error or
  unknown;
- the candidate values;
- the raw evidence.

Generic code reads only `Termination`. Backend-specific limits, such as
coefficient scaling, belong to the backend. Pyomo with HiGHS is the built-in
backend.

### Worker process

The built-in backend keeps process isolation for deadlines and crash safety.
It reuses one worker for each executor session:
- the worker starts with `python -I`;
- problems use sparse rows;
- fingerprints are cached for each process.

### Extension points

Every extension point uses one pattern: a `Protocol`, and a registry with
`register(name, implementation)`. Third-party packages can register through an
optional Python entry point group, `rangekeeper.<point>`. Each implementation
has a fingerprint, and evidence records it.

The extension points are:
- execution backends;
- path generators ([ADR-014](014-market-paths.md));
- unit systems and aliases ([ADR-016](016-safety-defaults.md));
- Bundle geometry providers.

### Fingerprints

A computation fingerprint hashes the static import closure of its entry point.
The closure is calculated automatically, so moved modules and new dependencies
are always included. Fingerprints change once, at the 1.0.0a2 rename pass
([ADR-012](012-naming-and-glossary.md)).

## Alternatives and consequences

- **Keep one `execute` entry point and make the store optional.** Its stages
  would stay untestable without a subprocess.
- **Map statuses inside the Pyomo backend only.** Other backends would still
  miss the underdetermined analysis.
- **Solve in the calling process.** This is fastest, but a solver crash would
  stop the caller.
- **Keep the built-ins closed.** This was rejected: one registry pattern costs
  little, and it gives one documented way to extend the library.

Each stage can be unit-tested without a subprocess. ADR-003's separation stays
the same: independent verification still decides publication.

## Sources and related decisions

- [ADR-003: computation and evidence](003-computation-and-evidence.md), amended
  by this record for package location and backend contract.
- [Execution reference](../reference/execution.md), which changes when the
  implementation lands.
- [ADR-016: safety defaults](016-safety-defaults.md).

Supersedes: none. Amends: ADR-003. Superseded by: none. Amended by: [ADR-021](021-sequential-decisions.md) adds the decided role and the decide stage.
