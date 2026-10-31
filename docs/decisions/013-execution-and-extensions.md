# ADR-013: Execution pipeline and extension points

Status: accepted for 1.0; extension points implemented in 1.0.0a2 (#131); typed stages, `ExecutionConfig`, `solve`, `execute`, the backend contract, validate-once and the status tables implemented (#125, #128, #126, #129, #132, #134); `Outcome` reading implemented (#127); the reusable isolated worker, sparse rows and the fingerprint cache of each process implemented (#130); batch worker processes implemented (#529). Recorded: 2026-10-26. Batch worker processes recorded: 2026-10-31.

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

`solve(*, specification, resolver=None, config=None) -> Outcome` is pure. It does
not write to a store. Without a resolver, it resolves the documents that made the
Specification (#293). `execute(*, specification, store, config=None) -> Outcome` runs
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

### Batch worker processes

A batch uses all the cores of the machine by default (#529). The solver is about
8 % of a batch, and the rest is Python work (the profile on #523), so this needs
processes, not threads. `ExecutionConfig(workers=)` sets another count, and
`workers=1` solves in the calling process.

- **Start.** A batch worker is a new interpreter on every platform: the spawn
  start method, by `subprocess`. It has the import path and the environment of the
  caller. `multiprocessing` does not start it, because the spawn of
  `multiprocessing` imports the caller's `__main__` again. A script with no
  `__main__` guard then runs again in each process: in a test, a spawn pool in such
  a script had not finished after three minutes. A new interpreter has no such
  requirement, so scripts and notebooks behave the same. The work functions are in
  library modules. A batch worker does not use `python -I`, because it needs the
  imports of the caller, and an extension can come from them.
- **One solve worker for each process.** Each batch worker holds its own solve
  worker, as in [Worker process](#worker-process). It is about 58 MiB, and it
  closes at exit. A batch worker of lesson 04 reached about 300 MiB at 500 paths.
- **Evidence.** `workers` enters no fingerprint and no Run. The first leaves solve
  in the calling process and the others in workers, by the same `solve_leaf`.
  Results return by position, so the finish order has no effect. The calling
  process assembles and validates the batch Run, and only it publishes. Run UUIDs
  are random and times differ, as between two sequential solves.
- **Failures.** A deadline stays with its own case: `Attempt` owns it, in the worker
  as in the caller. An expected failure is a Run. A batch worker that ends gives its
  case one failed Run, with a `numerical_failure` diagnostic, its exit code and the
  end of its stderr. A new process then solves the other cases. The lost case is
  not tried again, so a case that kills its process cannot stop the batch. A
  programming error raises from `solve`, with the trace of the worker in a note.
  It stops the cases that have not started. Cases start in order, so this is the
  error that a sequential solve raises. An interrupt ends each process. When the
  caller dies, the stdin of each batch worker ends, so the worker exits.
- **Small batches.** The first leaf of a process pays one-off costs, for example
  1.3 s against 0.035 s for a later small case, so its time decides nothing. After
  each later leaf, with `t` its time, `n` the leaves that remain and `w` the lesser
  of `n` and the workers, processes start only when `n * t * (1 - 1/w)` exceeds
  2 seconds. The figure comes from lesson 04: 0.4 s to import Rangekeeper and read
  the setup, and 1.4 s more for the first solve of a process than for its later
  solves. So a batch of up to 3 leaves never starts a process, and neither does a
  batch of small cases. The decision reads a clock, but where a leaf solves does not
  change its evidence.
- **Nested use.** A solve in a batch worker stays in that process, so processes do
  not multiply. Rangekeeper does not know of a process pool of the caller; such a
  caller sets `workers=1`.
- **Extensions.** A backend moves to each worker by `pickle`. Each unit system and
  profile registered in the caller moves too, so that a registration made at run
  time reaches the worker, and evidence records the same name and fingerprint. A
  value that does not move gets a clear fallback, not an error: a `RuntimeWarning`
  says why, and the calling process solves the leaves, with the same evidence. This
  applies when a value cannot be pickled, when a worker cannot read it (for example
  a class in `__main__`, in a script or a notebook) and when a process cannot start.
  A path generator runs before the solve, and only its `Paths` move. Geometry
  providers take no part in a solve.
- **What crosses.** Models and Paths cross once for each worker. Each leaf crosses
  with its composition. The Outcome and the validation scope return. Records and
  facades do not support `pickle`, so a private pickler (`execution/_boundary.py`)
  writes their state, and remakes them with no further validation. A Specification
  crosses without its Model and resolver, so a store stays in the caller. Facades
  cost less than records alone. An Outcome of lesson 04 is 768 KiB and reads in
  3.9 ms, with the index of its output Model. Without the index, the calling process
  takes 37 ms to make the Model again, for each leaf.
- **What stays serial.** Composition and the one validation of the whole tree
  (`validate_executed`, about 60 ms for each leaf) run in the calling process. They
  limit the gain: on 20 cores, lesson 04 takes 21.1 s at 40 paths against 113.2 s with
  `workers=1`, and 157 s at 500 paths against about 1,410 s (projected).

### Extension points

Every extension point uses one pattern: a `Protocol`, and a registry with
`register(name=, implementation=)`. Third-party packages can register through an
optional Python entry point group, `rangekeeper.<point>`. Each implementation
has a fingerprint, and evidence records it.

The extension points are:
- execution backends;
- path generators ([ADR-014](014-market-paths.md));
- profiles (`rk.profile`, added by #201, decision D12);
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
- **Use `multiprocessing` or `ProcessPoolExecutor` for batches.** Their spawn
  needs a `__main__` guard in each script, and one process that dies breaks the
  pool, so each other case would need a new submission.
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
