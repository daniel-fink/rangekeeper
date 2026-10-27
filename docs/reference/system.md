# Model-backed graph operations

Views select canonical Model objects. Membership and hierarchy are explicit projections; a graph operation does not define domain ownership or revise stored content.

## Architecture and ownership

The [architecture map](../concepts/architecture.md) places these operations under
`rangekeeper.model.system`. `View` owns selection, `Hierarchy` owns explicit tree
projection, `Reduction` owns recorded-Value aggregation, and `Pivot` holds one
Reduction per column of a Taxonomy. `membership` provides
Assembly traversal; `selection` provides owner-local Value selection. None of
these operations owns canonical field declarations.

The algorithms consume canonical Model records. Operation-local preparation uses
the Model's existing index for declared Measures and local Value selection; it does
not build another domain representation. A Hierarchy owns only derived UUID adjacency and
traversal order. It never fabricates Relationship records for Assembly membership.
Domain code does not import graph algorithms.

Importing `rangekeeper.model.system` loads neither legacy Graph nor Pint, NetworkX, pandas,
plotting, service integrations or solvers. Unit-bearing reductions explicitly use
`UnitSystem`, which loads Pint when needed. Tree validation/traversal uses Python
collections and iterative traversal; no NetworkX dependency is needed for this slice.

## Selection and traversal

```python
from rangekeeper.model.system import View, Hierarchy
from rangekeeper.model.system.membership import entities_in, containing_assemblies

view = View(model, assembly=assembly_id)
children = view.successors(parent_id)   # selected Relationships only
members = entities_in(model, assembly_id, recursive=True)
parents = containing_assemblies(model, entity_id, recursive=True)

two_bed = view.filter(entity_classification=two_bed_id)  # includes sub-types
exactly = view.filter(entity_classification=two_bed_id, exclusive=True)
relationship_tree = Hierarchy.from_relationships(view)

membership_view = View(
    model,
    entities=(assembly_id, *(entity.id for entity in members)),
    relationships=(),
)
membership_tree = Hierarchy.from_membership(membership_view, root=assembly_id)
```

These are two different edge meanings. A general View may have cycles, parallel
Relationships, shared descendants and disconnected selections. A Hierarchy requires
one nonempty rooted tree over exactly the selected Entities. It rejects multiple
parents, parallel edges and cycles rather than choosing an arbitrary path.
Overlapping Assemblies remain valid Model content, but may not form a tree in a
particular selection. Membership hierarchy construction restricts membership to
selected nodes; explicitly include transitive members when that is intended.

`View(model, *, entities=None, relationships=None, assembly=None)` supports:

- Neither explicit selector: every canonical Entity/Assembly and Relationship.
- Entity IDs only: the induced relationships between selected endpoints.
- Relationship IDs only: those relationships and their endpoints.
- Both: exactly those selections, rejecting any unselected endpoint.
- Assembly: the Assembly itself, direct Entity members and declared Relationship
  members; mutually exclusive with explicit selectors.

All lookups take UUIDs. `view.entity(id)` and `view.relationship(id)` distinguish
missing/wrong-kind Model references from known-but-unselected objects. The latter
raise `SelectionError`. `filter()` ANDs classification selectors and an optional
Boolean predicate. A classification selector matches that Classification and its
sub-types in its Taxonomy, at any depth. `exclusive=True` matches only that
Classification, for both the Entity and Relationship selectors. Classification
UUIDs must exist; an unknown UUID raises `MissingReferenceError`. Code/name
searching remains explicit through `Model.find_entities`, which matches
classifications exactly.

`Model.descendants(classification_id)` and
`rangekeeper.model.definitions.descendants(definitions, classification_id)` return
the sub-types of a Classification. They follow each Classification's `parent`,
exclude the Classification itself and keep Taxonomy declaration order. A leaf
Classification has no descendants. Traversal is iterative.

`entities`, `relationships`, `roots` and `leaves` are immutable tuples.
`predecessors(id)` and `successors(id)` return unique direct neighbors. Presentation
order follows Model entity encounter order (Entities then Assemblies), and System
Relationship order. Selector/set order does not determine output order. This is a
presentation convention, not additional schema or mathematical ordering.

`Hierarchy.from_relationships(view)` and `Hierarchy.from_membership(view, root=id)`
produce a pinned immutable tree with `root`, `kind` (`HierarchyKind`), `children(id)`, `parent(id)`,
`preorder()` and `postorder()`. `HierarchyError` carries a code and relevant UUIDs:
`empty`, `disconnected`, `cycle`, `multiple_parents`, `parallel_edges` or `root_mismatch`.
Traversal is iterative; valid deep trees do not consume the Python call stack.

## Explicit recorded-Value reduction

```python
from rangekeeper.model.system import Reduction
from rangekeeper.model.system.selection import select_value
from rangekeeper.model.system import reducers

reduction = Reduction(
    select=select_value("annual_rent", measure=rent_measure_id),
    reducer=reducers.sum,
    units="AUD/year",
    contributors=lambda entity: entity.classification == dwelling_classification_id,
    require_complete=True,
)

result = view.aggregate(reduction)  # validates a relationship hierarchy
# Or: result = reduction.execute(membership_tree)
quantity = result.value(parent_id)
coverage = result.coverage(parent_id)
available = result.available_value(parent_id)
```

The selector chooses one Value by its owner-local key. Optional `measure=` asserts
its Measure UUID; it never chooses the first Value sharing that Measure. Multiple
Values using one Measure remain independent. A supplied Measure must exist even
when the local key is missing. A custom selector must return a current Value owned
by that Entity; cross-owner, Formulation-local and stale quantities are rejected.

All selected quantities convert explicitly to `units` before reduction. The
`unit_system` parameter defaults to `None`: `execute` then uses
`Model.unit_system` of the hierarchy's Model ([units](units.md)). A supplied unit
system checks `units` when the Reduction is created; otherwise `execute` checks them. Results are immutable
schema Quantities. Custom reducers must return a compatible finite Quantity;
programming errors from callbacks propagate to the caller.

Built-in `reducers.sum`, `reducers.mean`, `reducers.min` and `reducers.max`
operate on nonempty tuples already normalized to identical unit spellings. Means
use raw contributors, avoiding the incorrect mean-of-subtree-means result. Overflow
is rejected. Empty populations remain unavailable rather than becoming zero.

`reducers.count` counts the contributors that have a value. It returns a
`Quantity` with `units="dimensionless"` and a whole-number magnitude. A count
`Reduction` takes no `units`; supplying them raises `TypeError`. Selected
quantities are not converted, so contributors can record different units.
Missing keys and unresolved quantities are missing contributors and are not
counted; a recorded zero is counted. Under `require_complete=True` an incomplete
population has no `value`, and `available_value` gives the count of measured
contributors. A population with no measured contributor has no count, as for the
other reducers; its `Coverage` still lists the selected and missing owners.

```python
units_with_price = Reduction(
    select=select_value("launch_price"),
    reducer=reducers.count,
    units=None,
    contributors=classified(model, two_bed_id),
)
```

`classified(model, classification_id, exclusive=False)` returns a contributor rule
for Entities in a Classification. It uses the same sub-type rule as `View.filter`:

```python
from rangekeeper.model.system import classified

two_bed_price = Reduction(
    select=select_value("launch_price"),
    reducer=reducers.sum,
    units="AUD",
    contributors=classified(model, two_bed_id),  # 2B, 2B+S, 2B Courtyard ...
)
```

Unclassified Entities never match. The UUID must exist in the Model.

The default contributor policy includes every selected Entity, including Assemblies.
The default requires complete coverage. If parents already record totals, select
leaves or a domain classification explicitly to avoid counting both parents and
children. The library does not infer which amounts are additive or certify physical
population completeness.

`Aggregation` exposes:

- `value(id)` / `result[id]`, and `root_value`: the result under the coverage policy.
- `coverage(id)`: selected, measured and missing owner UUIDs, with a
  `CoverageStatus` member: `EMPTY`, `COMPLETE` or `INCOMPLETE`.
- `available_value(id)`: reduction over measured contributors despite missing values,
  for every reducer, including wrapped and custom reducers.
- `entries`: one immutable `AggregateEntry(available, coverage)` per hierarchy node.
- `require_complete`: the policy used to derive `value` from each entry.
- `value_ids`: immutable owner-to-selected-Value IDs, including unresolved Values.
- `hierarchy`: the selection/revision that produced the derived results.

Missing keys and unresolved quantities count as missing; zero counts as measured.
A fully missing population has no available result. These operations do not revise a Model,
create provenance claims, assign solve roles, add governing mathematics, invoke a
solver or persist anything. Use `Model.revise` explicitly for authoring and the
scalar executor for mathematical investigation.

## Pivot over a Taxonomy

```python
from rangekeeper.model.system import Contributor, Reduction, reducers
from rangekeeper.model.system.selection import select_value

launch_price = Reduction(
    select=select_value("launch_price"),
    reducer=reducers.sum,
    units="AUD",
    contributors=Contributor.LEAVES,
)
pivot = launch_price.pivot(levels, by=apartment_id, depth=1, only=None)

pivot.value(level_id)               # the "All" column
pivot.value(level_id, two_bed_id)   # 2B, with its sub-types
pivot.cell(level_id, two_bed_id)    # AggregateEntry(available, coverage)
pivot.partition(level_id)           # do the 2B, 3B ... columns add up to All?
pivot.display()
```

`Reduction.pivot(hierarchy, *, by=None, depth=1, only=None, exclusive=False)`
returns a detached `Pivot` from `rangekeeper.model.system.pivot`. It runs
`Reduction.execute` once per column, so every cell is an `AggregateEntry` and the
pivot adds no arithmetic. Means stay correctly weighted: each cell reduces the raw
contributors of its subtree.

- The "All" column (`classification=None`) uses the Reduction's own contributors.
  With `only`, it also requires that Classification.
- `by` is a Classification. Its descendants down to `depth` levels become further
  columns, in Taxonomy preorder. `by` itself is not a column. Each column requires
  the Reduction's contributors, `only` and its own Classification.
- A Classification includes its sub-types, as in
  [`View.filter`](#selection-and-traversal). `exclusive=True` applies to `only` and
  to every column: each then matches only that Classification.
- `by=None`, or a `by` with no sub-types, gives the "All" column alone. Its
  Aggregation equals `execute(hierarchy)` when `only` is None.

An Entity has one Classification. When `only` and `by` come from different
Taxonomies, no Entity matches both, so the class columns are empty. Labels are not
read.

`PivotColumn(classification, parent, depth, aggregation)` describes one column.
The "All" column has depth 0 and no parent. A `parent` of None on a depth-1 column
means "All". `Pivot(rows, columns)` keeps column order and requires one "All"
column, unique Classifications, a parent column one level up for each column, and
Aggregations over `rows`. Unknown Classification UUIDs raise
`MissingReferenceError`; a malformed column set raises `AggregationError`.

A `Pivot` exposes:

- `columns`, `column(id)` and `children(id)`. `None` names the "All" column.
- `cell(row, column=None)`: the column's `AggregateEntry` for that row.
- `value`, `coverage` and `available_value`, as on `Aggregation`, for one column.
- `partition(row, column=None)`: a `Partition(complete, overlap, uncovered,
  outside)` that compares the column's `Coverage.selected` with its sub-columns'.
  `overlap` lists records in more than one sub-column, `uncovered` lists records
  in no sub-column, such as unclassified records, and `outside` lists sub-column
  records that the column does not select (possible with `exclusive=True`).
  `complete` is true when all three are empty. A partition compares populations,
  not values: a complete partition means sub-column sums add up to the column, and
  a missing Value does not change the partition. A column without sub-columns has
  every record uncovered.
- `to_table()`: a [Table](tables.md) in row preorder, with `name`, `parent_id`,
  `All` and one column per Classification code. Cells hold `value` results:
  a Quantity, a Flow or None. Row IDs are Entity UUIDs.
- `display(precision=2)`: a Polars table of scalar cells with rows indented by
  depth. "—" marks a cell with no contributor; "?" marks a cell with no value
  under its coverage policy. It needs the `calculations` extra.

## Table projection

`model.system.projection.to_table(source, columns=...)` accepts a `View` or `Hierarchy`.
A View keeps its entity order. A Hierarchy emits preorder rows and a reserved
`parent_id` column. `FieldColumn` takes an `EntityField` enum member. Column names,
units and optional Measure declarations are checked once before any cells are read,
including for an empty View. Selection still uses the owner-local Value key.

`Table` reuses a normalized `Row` when its columns already have the required order.
Raw mappings and reordered Rows are normalized once; immutable Row UUID lookup uses
an index. See [the consumer guide](tables.md) for examples and errors.

## Legacy boundary

`model.system.View` and `model.system.reduction` are Model-backed operations and reject old
Graph inputs. New records come from `rangekeeper.model`. See [tables](tables.md)
for projections of these views.

The old Graph domain, its View, table projection and JSON codec are removed.
No implicit Graph-to-Model conversion or compatibility constructors remain.
Consumers interpret their source data and create Models through public RK APIs.

## Flow hierarchy reduction

```python
from rangekeeper.model.system import Reduction, Contributor
from rangekeeper.calculations.series import ResamplingMethod

rollup = Reduction.flows(
    key="cashflow", periods=annual_periods,
    resampling=ResamplingMethod.SUM, contributors=Contributor.LEAVES,
)
result = rollup.execute(hierarchy)
portfolio = result.root_value
result.display()
```

The factory defaults to leaf contributors and SUM aggregation. `Contributor.ALL`
is explicit; it can include stored parent values, so select it only when those are
independent contributions. Scalar Reduction keeps its existing callable reducer.
Predicate contributors remain available for numerical work.

Flow reduction selects owner-local Values once, prepares/resamples the collection
once, and batches all subtree reductions over original contributors. Missing Flow
shapes appear in owner coverage. Unknown Movements and missing coordinates follow
`missing=` and `join=`. `entries[entity_id].period_coverage` records the known input
fraction at each coordinate. This is separate from selected/measured/missing owner
coverage. `value_ids` records the chosen source Values.

`rollup.formulate(hierarchy, id=..., aggregates={entity_id: flow_value_id})` returns
passive equations for the built-in SUM rule. It supports fixed SUM/MEAN/FIRST/LAST
resampling over original Movement references. Every selected source needs a shape,
but its amounts can be unknown. Aggregate Values must be owned by their named
entities. Self-contributions, incomplete source selection, callable symbolic
selection and unsupported methods fail explicitly. Results never mutate a Model.
