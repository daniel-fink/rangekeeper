# Model-backed graph operations

Views select canonical Model objects. Membership and hierarchy are explicit projections; a graph operation does not define domain ownership or revise stored content.

## Architecture and ownership

```text
rangekeeper/
  model/                         canonical generated records, lookup and revisions
  graph/
    view.py                      View: immutable Model + selected UUIDs
    membership.py                entities_in, relationships_in, containing_assemblies
    hierarchy.py                 Hierarchy: validated relationship or membership tree
    selection.py                 select_value: explicit owner-local key selector
    reduction.py                 Reduction, Aggregation, Coverage
    reducers.py                  sum_quantities, mean_quantities, min_quantity, max_quantity
    errors.py                    SelectionError, HierarchyError, AggregationError
    legacy/
      view.py                    old Graph-only View for unmigrated consumers
      reduction.py               old Measure/Feature reductions
    projection.py                Model-backed FieldColumn/ValueColumn/LabelColumn tables
    table.py, adapter/json.py     remaining old Graph projection and persistence
  table.py, adapters/, workflow/  shared tables and Model-backed consumers
  io/                            canonical persistence, unchanged
  execution/                     scalar executor, unchanged
```

The new algorithms consume public Model lookup and generated records. They do not
read `Model._index`, call another class's private traversal methods, or construct a
second domain representation. A Hierarchy owns only derived UUID adjacency and
traversal order. It never fabricates Relationship records for Assembly membership.
Domain code does not import graph algorithms.

Importing `rangekeeper.graph` loads neither legacy Graph nor Pint, NetworkX, pandas,
plotting, service integrations or solvers. Unit-bearing reductions explicitly use
`UnitSystem`, which loads Pint when needed. Tree validation/traversal uses Python
collections and iterative traversal; no NetworkX dependency is needed for this slice.

## Selection and traversal

```python
from rangekeeper.graph import View, Hierarchy
from rangekeeper.graph.membership import entities_in, containing_assemblies

view = View(model, assembly=assembly_id)
children = view.successors(parent_id)   # selected Relationships only
members = entities_in(model, assembly_id, recursive=True)
parents = containing_assemblies(model, entity_id, recursive=True)

filtered = view.filter(entity_classification=classification_id)
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
raise `SelectionError`. `filter()` ANDs exact classification selectors and an
optional Boolean predicate; descendants are not implicitly included. Classification
UUIDs must exist. Code/name searching remains explicit through `Model.find_entities`.

`entities`, `relationships`, `roots` and `leaves` are immutable tuples.
`predecessors(id)` and `successors(id)` return unique direct neighbors. Presentation
order follows Model entity encounter order (Entities then Assemblies), and System
Relationship order. Selector/set order does not determine output order. This is a
presentation convention, not additional schema or mathematical ordering.

`Hierarchy.from_relationships(view)` and `Hierarchy.from_membership(view, root=id)`
produce a pinned immutable tree with `root`, `kind`, `children(id)`, `parent(id)`,
`preorder()` and `postorder()`. `HierarchyError` carries a code and relevant UUIDs:
`empty`, `disconnected`, `cycle`, `multiple_parents`, `parallel_edges` or `root_mismatch`.
Traversal is iterative; valid deep trees do not consume the Python call stack.

## Explicit recorded-Value reduction

```python
from rangekeeper.graph import Reduction
from rangekeeper.graph.selection import select_value
from rangekeeper.graph.reducers import sum_quantities

reduction = Reduction(
    select=select_value("annual_rent", measure=rent_measure_id),
    reducer=sum_quantities,
    units="AUD/year",
    contributors=lambda entity: entity.classification == dwelling_classification_id,
    require_complete=True,
)

result = view.aggregate(reduction)  # validates a relationship hierarchy
# Or: result = reduction.execute(membership_tree)
quantity = result.value(parent_id)
coverage = result.coverage(parent_id)
subtotal = result.known_subtotal(parent_id)
```

The selector chooses one Value by its owner-local key. Optional `measure=` asserts
its Measure UUID; it never chooses the first Value sharing that Measure. Multiple
Values using one Measure remain independent. A supplied Measure must exist even
when the local key is missing. A custom selector must return a current Value owned
by that Entity; cross-owner, Formulation-local and stale quantities are rejected.

All selected quantities convert explicitly to `units` before reduction. The
`unit_system` parameter defaults to the existing `default_units`; callers using a
custom Model unit policy should pass the same policy here. Results are immutable
schema Quantities. Custom reducers must return a compatible finite Quantity;
programming errors from callbacks propagate to the caller.

Built-in `sum_quantities`, `mean_quantities`, `min_quantity` and `max_quantity`
operate on nonempty tuples already normalized to identical unit spellings. Means
use raw contributors, avoiding the incorrect mean-of-subtree-means result. Overflow
is rejected. Empty populations remain unavailable rather than becoming zero.

The default contributor policy includes every selected Entity, including Assemblies.
The default requires complete coverage. If parents already record totals, select
leaves or a domain classification explicitly to avoid counting both parents and
children. The library does not infer which amounts are additive or certify physical
population completeness.

`Aggregation` exposes:

- `value(id)` / `result[id]`, and `root_value`: the result under the coverage policy.
- `coverage(id)`: selected, measured and missing owner UUIDs; status is `empty`,
  `complete` or `incomplete`.
- `available_value(id)`: reduction over measured contributors despite missing values.
- `known_subtotal(id)`: available sum, only for the explicit `sum_quantities` reducer.
- `value_ids`: immutable owner-to-selected-Value IDs, including unresolved Values.
- `hierarchy`: the selection/revision that produced the derived results.

Missing keys and unresolved quantities count as missing; zero counts as measured.
A fully missing population has no subtotal. These operations do not revise a Model,
create provenance claims, assign solve roles, add governing mathematics, invoke a
solver or persist anything. Use `Model.revise` explicitly for authoring and the
scalar executor for mathematical investigation.

## Intentional namespace transition

`graph.View` and `graph.reduction` mean Model-backed operations and reject old
Graph inputs. New records come from `rangekeeper.model`. Tables, presentation,
and source workflows have moved to the [6C/6D packages](CONSUMER_MIGRATION.md).

The old Graph domain, its View, table projection and JSON codec are isolated in
`rangekeeper.legacy.graph` for the Windows migration/retirement gate.
They do not sit behind the new constructors. No implicit Graph-to-Model conversion
exists. The new adapters and source workflows do not import the old domain.
