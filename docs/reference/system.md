# Model-backed graph operations

Views select canonical Model objects. Membership and hierarchy are explicit projections; a graph operation does not define domain ownership or revise stored content.

## Architecture and ownership

The [architecture map](../concepts/architecture.md) places these operations under
`rangekeeper.model.system`. `View` owns selection, `Hierarchy` owns explicit tree
projection, `QuantityRollup` and `FlowRollup` own rollups of recorded Values, and
`Pivot` holds one rollup result per column of a Taxonomy. `membership` provides
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
children = view.successors(parent_id)  # selected Relationships only
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

## Declarative filters

A `Filter` (`rangekeeper.model.Filter`) is a selection stored as data, not code
([ADR-017](../decisions/017-api-and-formats.md)). It can be part of a query
Expression, and `View.match` and `View.where` apply it to a View. All its tests
must hold:

- `classification`: the Entity's Classification, with its sub-types in its
  Taxonomy, as in [`View.filter`](#selection-and-traversal). `exclusive=True`
  matches only that Classification.
- `labels`: `Criterion(key=, classification=, exclusive=)` records. The
  Entity's Label with that key must include the Classification or, unless
  `exclusive`, one of its sub-types.
- `tests`: `ValueTest(key=, relation=, quantity=, minimum=, maximum=)` records
  on the Entity's Value with that key. A `ValueRelation` names the test:
  `EQUAL`, `NOT_EQUAL`, `LESS_THAN`, `LESS_THAN_OR_EQUAL`, `GREATER_THAN` and
  `GREATER_THAN_OR_EQUAL` compare with `quantity`, with the words of the
  expression `Operator`; `BETWEEN` includes `minimum` and `maximum`; `PRESENT`
  and `MISSING` test whether the Value has recorded content.

`exclusive` is `True` or absent. Absent means that sub-types match, and the
stored form has no `exclusive: false`, so one meaning has one encoding. A
`Filter` with `exclusive` needs a `classification`. Construction and validation
refuse `exclusive=False`, `exclusive=None` and an `exclusive` Filter with no
`classification` ([#386](https://github.com/daniel-fink/rangekeeper/issues/386)).

```python
from rangekeeper.model import Criterion, Filter, ValueRelation, ValueTest
from rangekeeper.quantity import Quantity

large_hotel_floors = Filter(
    classification=floor_id,  # and its sub-types
    labels=(Criterion(key="use", classification=hotel_id),),
    tests=(
        ValueTest(
            key="gfa",
            relation=ValueRelation.GREATER_THAN_OR_EQUAL,
            quantity=Quantity(text="1500 m^2"),
        ),
    ),
)
match = view.match(condition=large_hotel_floors)
match.passed, match.failed, match.undecided  # Entity UUIDs, in View order
floors = view.where(condition=large_hotel_floors)  # a View of the passed Entities
```

A comparison converts the recorded Quantity to the units of the test with the
Model's unit system, so 16 000 ft² is less than 1 500 m². Equality and the
inclusive bounds use the relative tolerance of `rangekeeper.quantity.isclose`
(1e-9). Incompatible or unknown units raise `UnitError`. A comparison on a Flow
or property Value raises `SelectionError`; raw-text properties have no tests.

A test passes, fails, or cannot be decided because its value is missing. A
missing value is an absent Value, a measurement with no recorded Quantity, or an
absent Label. It never counts as zero
([ADR-016](../decisions/016-safety-defaults.md#missing-values)). The `Match`
partitions the tested Entities:

- `passed`: every test passed;
- `failed`: at least one test failed;
- `undecided`: no test failed, but at least one has a missing value. These
  Entities do not pass, and `Match.complete` is false. A rollup lists the same
  Entities in `Coverage.undecided`.

Only `MISSING` passes an Entity whose value is missing. An Entity without a
classification fails a `classification` test. `View.where(condition=)` keeps
the passed Entities and the selected Relationships between them. Unknown
Classification UUIDs raise `MissingReferenceError`. An empty `Filter()` passes
every Entity.

## Rollups of recorded Values

```python
from rangekeeper.model.system import QuantityRollup, Reducer

rent = QuantityRollup(
    key="annual_rent",
    units="AUD/year",
    reducer=Reducer.SUM,  # the default
    measure=rent_measure_id,  # optional: asserts each Value's Measure
    contributors=lambda entity: entity.classification == dwelling_classification_id,
    require_complete=True,  # the default
)

result = view.rollup(definition=rent)  # validates a relationship hierarchy
# Or: result = rent.execute(membership_tree)
quantity = result.value(parent_id)
coverage = result.coverage(parent_id)
available = result.available_value(parent_id)
```

A rollup selects one Value for each contributor by its owner-local `key`.
Optional `measure=` asserts its Measure UUID; it never chooses the first Value
sharing that Measure, and a different Measure raises `SelectionError`. A supplied
Measure must exist even when no owner has the key. A Value of the wrong kind (a
Flow for a `QuantityRollup`) raises `RollupError`.

`QuantityRollup` and `FlowRollup` share their fields and their contributor rules,
and both return a `RollupResult`:

| Field | Meaning | Default |
| --- | --- | --- |
| `key` | Owner-local Value key | required |
| `reducer` | A `Reducer`: `SUM`, `MEAN`, `MIN`, `MAX` or `COUNT` | `Reducer.SUM` |
| `units` | Units of the results | required for a `QuantityRollup`, except `COUNT` |
| `measure` | Measure UUID that each selected Value must use | none |
| `contributors` | `Contributor.LEAVES`, `Contributor.ALL`, a `Filter`, or a callable that returns bool | `Contributor.LEAVES` |
| `require_complete` | Whether `value` needs complete coverage | `True` |

Both rollups select leaf contributors by default, so a parent that records a total
is not counted with its children. `Contributor.ALL` includes every node, also
Assemblies; select it only when parent Values are independent contributions. A
callable contributor rule selects any node for which it returns True. The library
does not infer which amounts are additive or certify physical population
completeness.

### Filter contributors

A [declarative `Filter`](#declarative-filters) selects the nodes that pass it, at
any depth:

```python
from rangekeeper.model import Filter, ValueRelation, ValueTest

large_floors = Filter(
    classification=floor_id,
    tests=(
        ValueTest(
            key="gfa",
            relation=ValueRelation.GREATER_THAN_OR_EQUAL,
            quantity=Quantity(text="1500 m^2"),
        ),
    ),
)
nla = QuantityRollup(key="nla", units="m^2", contributors=large_floors)
result = nla.execute(hierarchy)
result.coverage(building_id).undecided  # floors with no recorded gfa
```

A node that the Filter cannot decide, because a tested value is missing, is
**undecided**. It is not a contributor, but its contribution is unknown, so
`Coverage.undecided` lists it and the coverage is incomplete
([ADR-016](../decisions/016-safety-defaults.md#missing-values)). A missing gfa
never passes `gfa < 100 m^2` as if it were zero. A node that fails the Filter is
decided: it is simply not a contributor. Pivot columns keep the undecided nodes
of their rows; a node outside a column is not undecided in that column.

### Quantity rollups

All selected quantities convert explicitly to `units` before the reducer combines
them. The `unit_system` field defaults to `None`: `execute` then uses
`Model.unit_system` of the hierarchy's Model ([units](units.md)). The same unit
system converts the Value tests of a `Filter` contributor rule, so the Filter and
the reducer read a unit in one way. A supplied unit system checks `units` when
the rollup is created; otherwise `execute` checks them.
Results are immutable schema Quantities.

The reducers operate on the raw contributors of each subtree. A mean is never a
mean of sub-tree means. Overflow and non-finite results raise `RollupError`.
Empty populations remain unavailable rather than becoming zero.

`Reducer.COUNT` counts the contributors that have a value. It returns a
`Quantity` with `units="dimensionless"` and a whole-number magnitude. A count
rollup takes no `units`; supplying them raises `TypeError`. Selected quantities
are not converted, so contributors can record different units. Missing keys and
unresolved quantities are missing contributors and are not counted; a recorded
zero is counted. Under `require_complete=True` an incomplete population has no
`value`, and `available_value` gives the count of measured contributors. A
population with no measured contributor has no count, as for the other reducers;
its `Coverage` still lists the selected and missing owners.

```python
units_with_price = QuantityRollup(
    key="launch_price",
    reducer=Reducer.COUNT,
    contributors=classified(model, two_bed_id),
)
```

`classified(model, classification_id, exclusive=False)` returns a contributor rule
for Entities in a Classification. It uses the same sub-type rule as `View.filter`:

```python
from rangekeeper.model.system import classified

two_bed_price = QuantityRollup(
    key="launch_price",
    units="AUD",
    contributors=classified(model, two_bed_id),  # 2B, 2B+S, 2B Courtyard ...
)
```

Unclassified Entities never match. The UUID must exist in the Model.

### Results

`RollupResult` exposes:

- `value(id)` / `result[id]`, and `root_value`: the result under the coverage policy.
- `coverage(id)`: a `Coverage(selected, measured, missing, undecided)` of owner
  UUIDs. `measured` and `missing` partition `selected`; `undecided` holds the
  owners that a Filter could not decide. `complete` needs a nonempty selection
  with no missing and no undecided owner. `status` is a `CoverageStatus`:
  `EMPTY` (nothing selected or undecided), `COMPLETE` or `INCOMPLETE`.
- `available_value(id)`: the result over measured contributors despite missing
  values, for every reducer.
- `entries`: one immutable `RollupEntry(available, coverage, period_coverage)`
  per hierarchy node.
- `require_complete`: the policy used to derive `value` from each entry.
- `value_ids`: immutable owner-to-selected-Value IDs, including unresolved Values.
- `hierarchy`: the selection/revision that produced the derived results.

Missing keys and unresolved quantities count as missing; zero counts as measured.
No reducer reads a missing value as zero: a sum or a count leaves it out, a mean
divides by the measured contributors only, and the coverage is incomplete. A
fully missing population has no available result. These operations do not revise a Model,
create provenance claims, assign solve roles, add governing mathematics, invoke a
solver or persist anything. Use `Model.revise` explicitly for authoring and the
scalar executor for mathematical investigation.

## Pivot over a Taxonomy

```python
from rangekeeper.model.system import QuantityRollup

launch_price = QuantityRollup(key="launch_price", units="AUD")
pivot = launch_price.pivot(levels, by=apartment_id, depth=1, only=None)

pivot.value(level_id)  # the "All" column
pivot.value(level_id, two_bed_id)  # 2B, with its sub-types
pivot.cell(level_id, two_bed_id)  # RollupEntry(available, coverage)
pivot.partition(level_id)  # do the 2B, 3B ... columns add up to All?
pivot.display()
```

`QuantityRollup.pivot(hierarchy, *, by=None, depth=1, only=None, exclusive=False)`,
and `FlowRollup.pivot` with the same arguments, return a detached `Pivot` from
`rangekeeper.model.system.pivot`. It runs the rollup's `execute` once per column,
so every cell is a `RollupEntry` and the
pivot adds no arithmetic. Means stay correctly weighted: each cell reduces the raw
contributors of its subtree.

- The "All" column (`classification=None`) uses the rollup's own contributors.
  With `only`, it also requires that Classification.
- `by` is a Classification. Its descendants down to `depth` levels become further
  columns, in Taxonomy preorder. `by` itself is not a column. Each column requires
  the rollup's contributors, `only` and its own Classification.
- A Classification includes its sub-types, as in
  [`View.filter`](#selection-and-traversal). `exclusive=True` applies to `only` and
  to every column: each then matches only that Classification.
- `by=None`, or a `by` with no sub-types, gives the "All" column alone. Its
  RollupResult equals `execute(hierarchy)` when `only` is None.

An Entity has one Classification. When `only` and `by` come from different
Taxonomies, no Entity matches both, so the class columns are empty.

### Columns by a label key

`label="use"` splits the columns by a Label key instead of the Entity's
Classification ([ADR-017](../decisions/017-api-and-formats.md)):

```python
gfa = QuantityRollup(key="gfa", units="m^2")
by_use = gfa.pivot(buildings, label="use")  # columns: residential, hotel, retail
by_use.value(building_a_id, hotel_id)
by_use.partition(building_a_id)  # overlap, uncovered, outside
```

- A column holds the Entities whose Label with that key includes the column's
  Classification or, unless `exclusive`, one of its sub-types.
- A Label can include several Classifications, so an Entity can be in several
  sibling columns. `partition` reports it in `overlap`. An Entity without the
  Label is in no column: `partition` reports it in `uncovered`.
- Without `by`, the columns start at the root of the one Taxonomy whose
  Classifications the rows' Labels with that key use. Labels that use several
  Taxonomies raise `RollupError`; pass `by` to choose. When no row has the
  Label, the pivot has the "All" column alone.
- `only` still tests the Entity's Classification. `Pivot.label` records the key;
  it is None for Classification columns.

`PivotColumn(classification, parent, depth, result)` describes one column.
The "All" column has depth 0 and no parent. A `parent` of None on a depth-1 column
means "All". `Pivot(rows, columns)` keeps column order and requires one "All"
column, unique Classifications, a parent column one level up for each column, and
RollupResults over `rows`. Unknown Classification UUIDs raise
`MissingReferenceError`; a malformed column set raises `RollupError`.

A `Pivot` exposes:

- `columns`, `column(id)` and `children(id)`. `None` names the "All" column.
- `cell(row, column=None)`: the column's `RollupEntry` for that row.
- `value`, `coverage` and `available_value`, as on `RollupResult`, for one column.
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

`model.system.table.to_table(source, columns=...)` accepts a `View` or `Hierarchy`.
A View keeps its entity order. A Hierarchy emits preorder rows and a reserved
`parent_id` column. `FieldColumn` takes an `EntityField` enum member. Column names,
units and optional Measure declarations are checked once before any cells are read,
including for an empty View. Selection still uses the owner-local Value key.

`Table` reuses a normalized `Row` when its columns already have the required order.
Raw mappings and reordered Rows are normalized once; immutable Row UUID lookup uses
an index. See [the consumer guide](tables.md) for examples and errors.

## Legacy boundary

`model.system.View` and `model.system.rollup` are Model-backed operations and reject old
Graph inputs. New records come from `rangekeeper.model`. See [tables](tables.md)
for projections of these views.

The old Graph domain, its View, table projection and JSON codec are removed.
No implicit Graph-to-Model conversion or compatibility constructors remain.
Consumers interpret their source data and create Models through public RK APIs.

## Flow rollups

```python
from rangekeeper.flow import ResampleMethod
from rangekeeper.model.system import FlowRollup

cashflow = FlowRollup(
    key="cashflow",
    periods=annual_periods,
    resampling=ResampleMethod.SUM,
)
result = cashflow.execute(hierarchy)
portfolio = result.root_value
result.display()
```

A `FlowRollup` takes `Reducer.SUM` (the default), `MIN` or `MAX`; `MEAN` and
`COUNT` raise `ValueError`. It selects leaf contributors by default, as a
`QuantityRollup` does. `periods` and `resampling` go together: each Flow is
resampled before the rollup with one `ResampleMethod`. `units` converts the
results; without it the Flows keep their units. Contributors without a Flow appear
as missing in owner coverage. `missing=MissingValueHandling.ZERO` raises
`ValueError`: a rollup never reads a missing Movement or coordinate as zero. Use
`ERROR` (the default), `PROPAGATE` or `SKIP`.

A Flow rollup selects owner-local Values once, prepares/resamples the collection
once, and batches all subtree results over original contributors. Unknown
Movements and missing coordinates follow `missing=` and `join=`.
`entries[entity_id].period_coverage` records the known input fraction at each
coordinate. This is separate from selected/measured/missing owner coverage.
`value_ids` records the chosen source Values.

`cashflow.formulate(hierarchy, id=..., aggregates={entity_id: flow_value_id})`
returns passive equations for `Reducer.SUM`. It supports `SUM`, `MEAN`,
`ELAPSED_MEAN`, `FIRST` and `LAST` resampling over original Movement references. Every selected source needs a shape,
but its amounts can be unknown. Aggregate Values must be owned by their named
entities. Self-contributions, incomplete source selection, callable symbolic
selection and unsupported methods fail explicitly. Results never mutate a Model.
