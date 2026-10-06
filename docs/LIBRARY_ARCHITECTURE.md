# Rangekeeper library architecture

Rangekeeper keeps declared content separate from operations that read, derive or
publish it. This lets one Model support different investigations without changing
its equations or treating a recorded result as a fixed input.

```text
schema/                          LinkML fields and structural contracts
src/rangekeeper/
  _schema/, _records.py          generated immutable records and encoding
  _behaviors/                   field-free intrinsic record methods
  model/, specification/, run/   root facades and semantic validation
  duration/, units.py            calendar and dimensional rules
  calculations/, formulations/  known-data arithmetic and declared equations
  scenarios/, policies/         captured futures and causal decisions
  execution/                    preparation, solve, acceptance, publication
  graph/                        views, membership, traversal and reductions
  table.py                      detached cells and optional row identity
  workflow/                     source evidence, composition and builds
  adapters/                     file, service and presentation boundaries
  io/                           strict codecs and append-only revision stores
  migration/                    explicit historical wire conversion
  legacy/                       predecessor code held for the Windows gate
```

## Records and behavior

LinkML is the field authority. The generator emits immutable Python and C# records
and schemas from the same resolved bundle. Python behavior mixins declare no
fields. They put operations such as `flow.check()` and `movement.number` on the
record whose invariant they enforce. Generated `replace()` preserves field
presence and runs structural validation. A root revision must also change content
and record its predecessor; ordinary replacement does not create a revision.

Use a method when one object owns the rule. Use an operation over several objects
when there is no single owner: alignment, aggregation, composition, encoding and
solving are examples. Prefer composition to inheritance between runtime services.
Inheritance is used for the schema's record relationships and field-free behavior.
See [record contracts](RECORD_BOUNDARY.md) and [naming](RK_NAMING.md).

## Validation and execution

Structural validation checks encoded shape. Domain validation checks identities,
references, units and mathematical scope. `Model` builds its lookup Index once;
validation reuses it. Resolver-backed checks use exact revision IDs and never
silently substitute the newest document.

`Executor` owns sequential batch traversal. A per-call `Plan` resolves references
and composes each leaf once. Each `Attempt` owns its deadline, candidate and report,
and separates preparation, solving, acceptance and persistence. A solver candidate
becomes an output only after the original equations accept its serialized values.
The output is stored before its Run; storage is not a multi-document transaction.

Run validation has three parts: local report checks, `Publication` checks for
permitted changes and retained evidence, and `Tree` checks for references, batch
accounting and lineage. These checks do not rerun a solver or prove feasibility.
See [execution](SCALAR_EXECUTION.md) and [storage](RUN_AND_STORAGE.md).

## Data and presentation

Core content uses records, tuples, mappings and native dates. Polars is the only
maintained dataframe adapter. It serves detached tables, CSV and notebook display;
NumPy and SciPy serve numerical kernels. A dataframe is not a Model and does not
carry the full revision, unit or provenance contract. CSV is a textual projection.
See [consumer boundaries](CONSUMER_MIGRATION.md).

The offline viewer uses a `Viewer` state interface and separate navigation,
projection, geometry and inspection modules. Its TypeScript sources generate the
bundled JavaScript. Layout `Formulation` builds Z3 expressions; solver control
owns deadlines and optimization. MiniZinc data encoding is separate from process
control. Both engines use an independent arithmetic checker before returning
accepted geometry. Browser display adjustments never revise the Model.

C# `Validator` uses embedded schemas and local ownership checks for authoring.
Python remains the complete semantic boundary. Host loading, connector publication
and receipt need their own acceptance evidence; portable tests cannot establish it.

## Dependency boundaries

Core imports load no dataframe, plotting library, service SDK or solver. Extras
install optional operations explicitly. `tables` installs Polars; `calculations`
also includes it for the numerical walkthroughs. `financial` supports PyXIRR
without SciPy or dataframe imports. Pyomo and HiGHS run in the execution worker.

Canonical modules do not import `legacy`. Historical conversion reads wire data
without constructing predecessor classes. The isolated predecessor code remains
until the [Windows gate](LEGACY_ISOLATION.md) closes. No compatibility aliases
restore retired public paths.
