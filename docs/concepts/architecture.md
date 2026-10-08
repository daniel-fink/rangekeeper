# Rangekeeper library architecture

Rangekeeper keeps declared content separate from operations that read, derive or
publish it. This lets one Model support different investigations without changing
its equations or treating a recorded result as a fixed input.

## Package ownership and imports

Import `Model`, `Specification` and `Run` from `rangekeeper`. Import generated
metadata and enums through `rangekeeper.schema`, and shared Table, units, references
and errors through their `rangekeeper.shared` modules. Domain capability imports
follow the owning package shown below. See the [upgrade guide](../guides/upgrading.md)
for removed public paths.

```text
docs/                            maintained guides, plans and dated evidence
examples/                        notebooks, example builders and wire examples
tools/                           generation, verification and book builds
src/grasshopper/                 .NET authoring and Rhino/Grasshopper host project
schema/                          LinkML fields and structural contracts
src/rangekeeper/
  schema/                        generated records/enums, runtime, indexes and behaviors
  shared/                        tables, units, references, diagnostics and validation
  model/                         Model facade, declarations and semantic validation
    system/                      System records, views, membership and reductions
    expression/, formulation/    expression analysis and passive equation authoring
    duration/, scenario/         calendar rules, captured futures and replay
  specification/                 investigation requirements and composition
    policy/                      declarations, observation and causal evaluation
  run/                           finalized execution evidence and validation
    execution/                   preparation, solve, acceptance and publication
  calculations/                  known-data arithmetic and deterministic kernels
  workflow/                      source configuration, composition and builds
    evidence/, operation.py      native Claims, Evidence and invocation contracts
  adapters/                      file, service and presentation boundaries
  io/                            strict codecs and append-only revision stores
  migration/                     explicit historical wire conversion
  legacy/                        predecessor code held for the Windows gate
```

The Python distribution is built from `pyproject.toml`; its packages live under
`src/rangekeeper`. The independent .NET solution lives beside it at
`src/grasshopper`. Python adapter modules remain in `rangekeeper.adapters`.
Runnable examples and the separate `rangekeeper_examples` package live under
`examples/`; example builders are not shipped inside the library package.

`tools/` contains developer programs with generation or acceptance responsibilities.
It is not a runtime package. Complete example programs belong in `examples/`, and
maintained development instructions belong in [contributing](../contributing/README.md).

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
See [record contracts](../reference/records.md) and [contributor naming rules](../contributing/README.md).

## Validation and execution

Structural validation checks encoded shape. Domain validation checks identities,
references, units and mathematical scope. `Model` builds its `RecordIndex` once;
validation reuses it. Resolver-backed checks use exact revision IDs and never
silently substitute the newest document.

`Executor` owns sequential batch traversal. A per-call `Plan` resolves references
and composes each leaf once. Each `Attempt` owns its deadline, candidate and report,
and separates preparation, solving, acceptance and persistence. A solver candidate
becomes an output only after the original equations accept its serialized values.
The output is stored before its Run; storage is not a multi-document transaction.

Run validation combines `run.report` local evidence checks, `run.outputs` checks
for permitted changes and retained evidence, and one resolver-backed operation
for references, batch accounting and lineage. These checks do not rerun a solver or prove feasibility.
See [execution](../reference/execution.md) and [storage](../reference/run-and-storage.md).

## Data and presentation

Core content uses records, tuples, mappings and native dates. Polars is the only
maintained dataframe adapter. It serves detached tables, CSV and notebook display;
NumPy and SciPy serve numerical kernels. A dataframe is not a Model and does not
carry the full revision, unit or provenance contract. CSV is a textual projection.
See [tables](../reference/tables.md) and [source workflows](source-workflows.md).

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
until the [Windows gate](../contributing/legacy-retirement.md) closes. No compatibility aliases
restore retired public paths.

## Flow coordination and acausal relations

`model.flux.Stream` coordinates immutable flows and owns private reusable
calculation state. `calculations._batch` performs bulk Polars operations.
`model._flow_mapping` supplies fixed, amount-independent period membership to
both numerical calculations and passive formulations. Canonical Flow and Movement
records remain the persistent representation; frames and caches are never saved.

Specifications own solve roles. Stream calculations do not assign roles or declare
equations. Formulation builders consume explicit Value/Movement references and
return ordinary expression records. The existing affine compiler and independent
acceptance evaluator govern each investigation. See [ADR-005](../decisions/005-flux-and-stream-implementation.md).
