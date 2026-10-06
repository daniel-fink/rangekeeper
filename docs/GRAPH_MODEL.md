# Model-backed graph operations

**Turn 3 update, 2026-10-06:** [Remaining consumers and design integrations](FULL_MIGRATION_TURN3.md)
implements the canonical workbench/layout port, all three Projects source builds,
Speckle mapping, both design walkthroughs and generated C# Rhino 8 authoring.
See [current acceptance](research/full-migration/turn3/BASELINE.md),
[consumer register](research/full-migration/turn3/CONSUMERS.md), and
[Turn 4 retirement gates](research/full-migration/turn3/RETIREMENT.md).
The Windows official connector gate remains open. Hypar support is retired;
the future Browser/outliner importer remains on hold. Dated checkpoints below
remain historical evidence and do not override this current scope.


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
Next is Turn 2: temporal mathematics, scenarios/policies, and their consumers.
Turns 3–4 finish remaining consumers and retire old modules. The six-checkpoint
history below remains the scalar/core work record; full migration is not complete.

Step 6A/6B are implemented locally, 2026-10-03. `rangekeeper.graph.View` now
selects immutable records from one canonical Model revision. Explicit hierarchy
construction and Value-based reduction work over that selection.
[Step 6C/6D](CONSUMER_MIGRATION.md) now adds tables, presentation adapters, and
source workflows. External consumer migration and retirement remain 6E/6F.
[Verification evidence](research/graph-migration/README.md) records this boundary.

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

The old Graph domain, `Graph.view()`, `graph.table` projection methods, Graph JSON,
and `graph.legacy` reductions remain for the external migration/retirement gates.
They do not sit behind the new constructors. No implicit Graph-to-Model conversion
exists. The new adapters and source workflows do not import the old domain.

## Remaining Step 6 implementation slices

The [full migration review](FULL_MIGRATION_REVIEW.md) expands the remaining scope
to numerical/temporal behavior and all supported consumers, including parallel
workbench/layout features. The four-turn sequence now governs implementation of that scope. The table
below retains the graph migration milestones; it is not the whole refactor plan.

| Slice | Work | Acceptance/removal condition |
| --- | --- | --- |
| 6A/6B — implemented | Model selections, membership, hierarchy, explicit Value reduction | New semantics, old consumer characterization, static/installed checks and scalar regressions pass. |
| 6C — implemented | Move shared Row/Table to `table.py`; add `graph/projection.py` with FieldColumn/ValueColumn/LabelColumn and `to_table`/`to_tree_table`; migrate CSV/pandas/viewer projections to `adapters/` | Stable identity/order, units/missingness, repeated viewer occurrences, packaged assets; retire old projection traversal. |
| 6D — implemented | Migrate source-building WorkflowSpec/runtime/composition to `workflow/`, producing `WorkflowResult.model`; preserve closed operation catalog, evidence/fingerprints and atomic validation | Supported source-to-Model-to-codec/store-to-executor example; no conflation with mathematical Specification/Run. |
| 6E — in progress | Migrate actual projects, notebooks and supported persisted formats in their own environments | Consumer-specific semantic equivalence, explicit key mapping, source/provenance preservation and declared unsupported content. |
| 6F | Remove superseded domain/codec/export implementations after their last supported consumer moves | Import/caller inventory, installed-package checks and documentation; no silent format or data loss. |

Mandarin/East Whisman Feature-rich content remains gated on an explicit supported
contract. No generic Feature is silently stringified, dropped or hidden in Claim
content. Speckle/Grasshopper need service/host acceptance; Hypar needs maintained
source discovery. These consumers were not executed in this slice. Numerical
modules, temporal Values and rich mathematical capabilities now have explicit
work in the expanded full migration. Turn 1 has delivered content and numerical
foundations; indexed mathematics and scenario/policy execution remain Turn 2.
