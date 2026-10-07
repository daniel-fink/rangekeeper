# Tables, adapters and source workflows

Source workflows build canonical Models from explicit evidence. Tables and dataframe projections support inspection and interchange; they do not replace Model persistence.

## Package ownership

```text
rangekeeper/
  table.py                       Row, Table, TableError; no domain dependency
  evidence/                      source Claims, Evidence, transforms and fingerprints
  operation.py                   Operation, Outcome, Diagnostic; source invocations
  _encoding.py, _structured.py    exact source fingerprints and immutable requests
  graph/
    projection.py                FieldColumn, ValueColumn, LabelColumn
                                 to_table for View or Hierarchy
    view.py, hierarchy.py        pinned Model selection and traversal
  adapters/
    csv.py, polars.py            Table interchange; not Model persistence
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
    reporting.py, review.py       shared report preparation, HTML and export
    __main__.py                  explicit CLI
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
    EntityField, FieldColumn, ValueColumn, LabelColumn, to_table,
)
from rangekeeper.adapters import csv, polars, cytoscape

columns = (
    FieldColumn("model_id", EntityField.MODEL_ID),
    FieldColumn("entity_id", EntityField.ENTITY_ID),
    FieldColumn("name", EntityField.NAME),
    ValueColumn("net_area", "net", "meter**2"),
    ValueColumn("gross_area", "gross", "meter**2"),
)
view = View(model)
table = to_table(view, columns=columns)
frame = polars.to_frame(table)
csv.write(table, "areas.csv")
cytoscape.write_viewer([cytoscape.project(model, "Review")], viewer_path)
```

`FieldColumn(name, field)` requires an `EntityField` member: `MODEL_ID`,
`ENTITY_ID`, `CODE`, `NAME`, `ENTITY_KIND`, `CLASSIFICATION_ID`,
`CLASSIFICATION_CODE`, or `CLASSIFICATION_NAME`. Raw strings are rejected.
`ValueColumn(name, key, units, measure=None)` selects an owner-local key. Optional
`measure` asserts a Measure UUID; it does not select by Measure. Units are explicit.
`LabelColumn(name, key)` returns classification UUIDs, not ambiguous codes.

`to_table(source, *, columns=DEFAULT_COLUMNS, units=default_units)` returns `Table`.
The defaults are Model UUID, Entity UUID, and name. Each Row ID is the Entity UUID;
row order follows the View. Duplicate column names raise `TableError`.
Wrong column, field or source types raise `TypeError`; incompatible units raise `UnitError`;
a Measure mismatch raises `SelectionError`. Missing and unresolved quantities
project to `None`; zero remains zero. The Model still distinguishes an absent
Value from a declared Value without a quantity.

`to_table(hierarchy, *, columns=DEFAULT_COLUMNS, units=default_units)` adds
`parent_id` and returns preorder rows. The caller first chooses relationship or
membership hierarchy semantics. Shared membership is not forced into one parent.
`Table` reuses an existing Row when its ordered columns match, and indexes Row IDs
for lookup. Reordering creates a new Row without changing the input. A Table is shallowly frozen and may hold native cells; it is not an immutable
Model snapshot. CSV writes UUID cells as text and rejects rich cells. Polars/CSV
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
known subtotals remain separate from complete results. Each `CheckResult` has
`left` and `right` operand objects that retain value, Claims, targets, missing
contributors and known subtotal. Count reports retain the original members and
derive the displayed count. The old flattened side fields are removed;
`checks.json` uses `rk.workflow-checks/v2` with explicit operand sides.

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

## Direct evidence and layout APIs

Import `Evidence`, `Claim`, `ClaimKind`, `Severity`, `tabular`, `validate` and
`fingerprint` from `rangekeeper.evidence`. The old `workflow.ingestion` package is
removed. `operation.Severity`, `evidence.Severity` and `run.Severity` are the same
generated enum; `evidence.ClaimKind` and `model.ClaimKind` are also identical.
Typed Python APIs require enum members. YAML and JSON retain their string values.

Workflow requests belong to their capability modules, such as
`adapters.excel.workflow` and `workflow._table_operations`; the old dynamic request
aliases in `workflow.specification` are removed. The workflow semantic manifest and
run method use version 5. Exact installed-file hashes remain separate audit data.

Layout review belongs to `adapters.cytoscape.layout.review`. Call
`build(model, bundle=..., profile=..., output_root=...)` with a canonical Model and
its complete review bundle. It checks the complete Model content with type-sensitive
comparison, including distinctions such as `0` and `False`.
It does not require a workflow Attempt. Layout result enums are owned by the layout
package; geometry and review documents retain their existing string fields.

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


## Polars and CSV contract

`polars.to_frame(Table | Flow)` creates detached columns. `polars.to_table(frame)`
copies cells to a Table; `polars.from_frame(frame, units=...)` reads the explicit
Flow movement format. Opaque or mixed Table cells use Object columns to avoid
silent coercion. Row UUIDs and Claims stay in separate evidence, not hidden columns.

CSV rejects rich cells and nonfinite numbers. UUID cells become text. Reading uses
Polars inference: empty fields become None, while `NA` remains text. Preserve
leading-zero identifiers with `csv.read(path, schema_overrides={"code": pl.String})`
after `import polars as pl`. CSV cannot reconstruct a Model or its provenance.
