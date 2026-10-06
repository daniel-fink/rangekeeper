# Model tables, adapters, and source workflows

**Turn 2 update, 2026-10-06:** [Temporal equations, scenarios and policies](FULL_MIGRATION_TURN2.md)
now use Model/Specification 0.5.0 and Run 0.2.0. `ValueReference` addresses scalar
Values or owner-local Movement keys. The canonical calendar package is `duration/`;
`temporal` has no public alias. Finite Flow formulations, captured scenario replay,
exogenous declarative policies and the four numerical walkthroughs are implemented.
See [verification](research/full-migration/turn2/README.md) and the
[upgrade guide](LEGACY_UPGRADE_GUIDE.md). Turn 3 completes remaining consumers and
integrations; Turn 4 retires obsolete code after their acceptance gates.
The dated checkpoint descriptions below remain historical context.

**Flow semantics update, 2026-10-06:** Flows no longer carry semantic kinds or
basis. The overall model logic owns their meaning and selects operations; units,
dates, alignment and missingness remain checked. See the
[current contract](FULL_MIGRATION_TURN1.md#flow-semantics-and-explicit-operations)
and [verification](research/full-migration/flow-semantics/README.md).

**Full migration update, 2026-10-04:** [Turn 1 foundations](FULL_MIGRATION_TURN1.md)
implements Model 0.4.0 rich properties and Flow Values, `model.duration`,
`temporal`, `calculations`, detached dataframe adapters, and explicit Graph conversion.
The basic DCF notebook, financial test model and synthetic source workflows migrated.
Read the [upgrade guide](LEGACY_UPGRADE_GUIDE.md) and [verification](research/full-migration/turn1/README.md).
Turn 2 is implemented; see the current contract and verification linked above.
Turns 3–4 finish remaining consumers and retire old modules. The six-checkpoint
history below remains the scalar/core work record; full migration is not complete.

Step 6C/6D, implemented locally on 2026-10-03. LinkML remains authoritative.
These changes move presentation and source construction onto the canonical Model.
They do not migrate external projects or remove the remaining old Graph domain.
See the [verification record](research/consumer-migration/README.md).

## Package ownership

```text
rangekeeper/
  table.py                       Row, Table, TableError; no domain dependency
  evidence.py                    transient source observations and support chains
  operation.py                   Operation, Outcome, Diagnostic; source invocations
  _encoding.py, _structured.py    exact source fingerprints and immutable requests
  graph/
    projection.py                FieldColumn, ValueColumn, LabelColumn
                                 to_table, to_tree_table
    view.py, hierarchy.py        pinned Model selection and traversal
  adapters/
    csv.py, pandas.py            Table interchange; not Model persistence
    document.py, excel/          native source snapshots and evidence extraction
    visualization.py            Model-backed View and Table presentation
    cytoscape/                   Model/View projection and packaged offline viewer
  workflow/
    specification.py, _schema.py WorkflowSpec, StepSpec, load, schema
    catalog.py, _contracts.py     closed capabilities and explicit input wiring
    runtime.py                   run -> Outcome[WorkflowResult]
    composition.py               compose -> Model, findings, business-key index
    provenance.py                source support -> generated Claims/Sources/Facts
    checking.py, _operands.py    source comparisons and Model invariants
    ingestion/                   Evidence[Table], transforms, fingerprints
    review.py, __main__.py        explicit export and CLI
  model/, specification/, run/   canonical records and domain behaviour
  io/                            canonical JSON/YAML and revision stores
  execution/                     mathematical execution; unchanged by a workflow run
```

The adapter and workflow implementations were moved, not copied into a second
compatibility package. General tables and source operations have no old Graph
object dependency. Source observations can hold native immutable values; they are
not serialized Model records. Only `workflow.provenance` converts their support
chains into schema records. Canonical domain behaviour does not import readers,
workflows, presentation, filesystem stores, or solver backends.

## Tables and presentation

```python
from rangekeeper.graph import View, Hierarchy
from rangekeeper.graph.projection import (
    FieldColumn, ValueColumn, LabelColumn, to_table, to_tree_table,
)
from rangekeeper.adapters import csv, pandas, cytoscape

columns = (
    FieldColumn("model_id", "model_id"),
    FieldColumn("entity_id", "entity_id"),
    FieldColumn("name", "name"),
    ValueColumn("net_area", "net", "meter**2"),
    ValueColumn("gross_area", "gross", "meter**2"),
)
view = View(model)
table = to_table(view, columns=columns)
frame = pandas.to_dataframe(table)
csv.write(table, "areas.csv")
cytoscape.write_viewer([cytoscape.project(model, "Review")], viewer_path)
```

`FieldColumn(name, field)` supports `model_id`, `entity_id`, `code`, `name`,
`entity_kind`, `classification_id`, `classification_code`, and `classification_name`.
`ValueColumn(name, key, units, measure=None)` selects an owner-local key. Optional
`measure` asserts a Measure UUID; it does not select by Measure. Units are explicit.
`LabelColumn(name, key)` returns classification UUIDs, not ambiguous codes.

`to_table(view, *, columns=DEFAULT_COLUMNS, units=default_units)` returns `Table`.
The defaults are Model UUID, Entity UUID, and name. Each Row ID is the Entity UUID;
row order follows the View. Duplicate names and invalid fields raise `TableError`.
Wrong column/View types raise `TypeError`; incompatible units raise `UnitError`;
a Measure mismatch raises `SelectionError`. Missing and unresolved quantities
project to `None`; zero remains zero. The Model still distinguishes an absent
Value from a declared Value without a quantity.

`to_tree_table(hierarchy, *, columns=DEFAULT_COLUMNS, units=default_units)` adds
`parent_id` and returns preorder rows. The caller first chooses relationship or
membership hierarchy semantics. Shared membership is not forced into one parent.
A Table is shallowly frozen and may hold native cells; it is not an immutable
Model snapshot. CSV writes UUID cells as text and rejects rich cells. Pandas/CSV
readback does not restore Row identity or a Model. Canonical persistence remains
`io.json` and `io.yaml`, with explicit `kind=Model` on reads.

Cytoscape records the pinned `modelId`. Canonical Entity and Relationship UUIDs
remain unique. Shared membership uses separate display-only connectors and
membership paths; collapse summaries retain their original Relationship IDs.
They do not create extra canonical objects. A repeated outliner occurrence is not
a second Entity. The existing collapse/routing client is retained. Viewer exports
remain display documents and cannot be read as Model JSON.

## Source workflow version 2

```python
from rangekeeper.workflow import load, run
from rangekeeper.workflow.review import export
from rangekeeper.io import DirectoryStore

spec = load(spec_directory)
outcome = run(spec, input_root=input_directory)
if outcome.output is not None:
    result = outcome.output
    model = result.model
    DirectoryStore(revisions_directory).put(model)
    export(result, review_directory)
```

All four outer YAML documents (`sources`, `model`, `decisions`, `checks`) now
require `version: 2`. Native Excel extraction policies retain their own version 1.
There is no automatic version-1 conversion. The operation names and closed
catalogue remain. `WorkflowSpec` is source configuration, distinct from mathematical
`Specification`; `Operation`/`Outcome` are distinct from solver `Run`.

A Measure declaration supplies `code`, `name`, `units`, optional `definition` and
`tags`. It no longer carries legacy `quantity_kind` or `aggregation` policy.
The existing `measurements` and shared `measurement_sets` declaration names remain,
but each entry requires its own `key`, `measure`, and `binding`:

```yaml
measurements:
  - key: net
    measure: area
    binding: {column: parsed_net}
  - key: gross
    measure: area
    binding: {column: parsed_gross}
```

Entries create schema Values. `kind` defaults to `measurement`; `parameter` and
`decision` are explicit alternatives. `integer: true` enforces an integer reading.
An unavailable reading creates a declared Value with `quantity: null`; the source
Evidence and optional finding explain it. Conditional exclusion omits the Value.
Multiple keys can use one Measure. Duplicate local keys are rejected.

`features` and `on_unavailable.feature` are rejected before source execution.
The workflow does not discard those declarations or place their intended domain
content in opaque Claims. Rich source observations remain available as Evidence;
they need a supported schema representation before becoming Model state.

Check operands are now `model_keys`, `model_count`, `model_total`, and `model_value`.
Value selection uses `value_key`; totals and individual Value comparisons require
`units`. Business-key membership checks remain explicit. Missing contributors and
known subtotals remain separate from complete results.

Composition uses stable business-key UUIDs for declarations and owner-local Value
keys. Assemblies are stored in `System.assemblies`. Model revision UUIDs are derived
from the complete built content, including provenance. An unchanged build has the
same revision ID; changed source content or support changes the revision. A new
build does not infer a predecessor. Use `Model.revise` for an explicit revision
relationship.

`Model.create` validates the whole candidate before it is returned. Expected source
failures and invalid Model candidates return an unavailable Outcome with diagnostics.
Malformed configuration fails at loading/construction. No partial Model is stored.
Unexpected programming errors still propagate.

Source Claims preserve locations, source checksums, methods, and upstream support.
Their content uses an explicit `rk.source-value/v1` type encoding so native dates,
tuples, false, zero, and unavailable readings remain distinct. Fact Claims record
the generated declaration they support; all canonical links use UUIDs. The result
also retains named Evidence, source checks, findings, invocation records, source
fingerprints, effective configuration, and exact/semantic implementation manifests.

`run` does not write exports, publish revisions, or solve equations. `export` writes
`model.json`, checks, a manifest, and offline review/viewer files. Use a fresh export
directory: the canonical JSON writer does not overwrite an existing revision file.

## Supported end-to-end example

From `src`, with the workflow and execution dependencies installed:

```sh
PYTHONPATH=. python ../tools/workflow/scalar.py --output /tmp/rk-source-example
```

The output directory must not exist. The example reads an XLSX observation of
10 m², builds a Model with separate net/gross Values using one Measure, and passes
it through YAML. It then explicitly authors the equation `gross = net + net` in a
new Model revision. The filesystem store and real executor produce gross **20 m²**.
The inverse investigation reuses that output, assigns gross **50 m²**, and solves
net **25 m²**. Both Runs receive resolver-backed validation. Source provenance
remains in the accepted output Models.

## Remaining consumer gates

The expanded [full migration review](FULL_MIGRATION_REVIEW.md) now inventories
numerical/temporal consumers, formerly version-1 workflow examples and parallel RK
workbench/layout features. It proposes the additional contracts and proof needed
before complete consumer migration and retirement can be claimed.

6E migrates Mandarin, East Whisman, notebooks, and other repository/host consumers
in their own environments. Their old imports, workflow version 1, Feature content,
and persisted Graph JSON need explicit changes. They were not run in this slice.
Old Graph JSON is not Model JSON. Turn 1 now supplies an explicit bounded v1
converter and migrated synthetic examples; this does not certify external consumers.

6F removes the old domain and persistence implementations after consumer acceptance.
For now `graph.table` retains its old Graph projection methods over the shared
`table.Table` storage class; `Graph.view()` and old reductions still use
`graph.legacy`. Existing old Graph tests retain those characterizations. New
adapters and workflows do not use those modules. `graph.adapter` retains only the
old Graph JSON codec. The removed `graph.workflow` and presentation-adapter paths
have no compatibility aliases.
