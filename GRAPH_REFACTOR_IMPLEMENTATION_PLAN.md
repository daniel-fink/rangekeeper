# Rangekeeper Graph Refactor Implementation Plan

## Execution handoff

This document is the implementation brief for a deliberate breaking refactor of
Rangekeeper's entity/relationship graph system. It is intended to be executable
by another Codex instance on **Daniel's Mac Studio**, which has the same absolute
filesystem layout as the machine on which the plan was written.

Source Codex tasks:

- Current design task: `codex://threads/01a01836-b087-7011-bfff-04172ba2d304`
- Earlier Rangekeeper design/history task: `codex://threads/019ffb06-6c47-7ec1-9c86-890bffb9485e`

Repository and branch at plan creation:

```text
Repository: /Volumes/Data/Projects/Rangekeeper
Branch:     feat/entity-area-core
HEAD:       35ebfd3 refactor: simplify kind provenance
Remote:     origin/feat/entity-area-core at the same commit
```

The repository had these **pre-existing, uncommitted user changes** when this
plan was written:

```text
M src/pyproject.toml
M src/rangekeeper/graph/entity.py
M src/rangekeeper/graph/kind.py
M src/uv.lock
```

Their observed intent was:

- remove a large obsolete commented-out `Type` implementation from
  `graph/entity.py`;
- rename the private `Kind._walk_preorder()` helper to `Kind._traverse()`;
- constrain `pandas-stubs` to `~=2.3.2` and update the lockfile.

These edits belong to the user. **Do not reset, discard, overwrite, or silently
fold them into an unrelated commit.** Reinspect the working tree before starting
because the Mac Studio copy may have advanced.

The focused baseline at plan creation was:

```text
37 passed in 0.07s
```

using:

```bash
cd /Volumes/Data/Projects/Rangekeeper/src
uv run pytest \
  tests/test_kinds.py \
  tests/test_characteristics.py \
  tests/test_measures.py \
  tests/test_graph.py \
  -q
```

Speckle credentials already exist at:

```text
/Volumes/Data/Projects/Rangekeeper/src/.env
```

The file contains `SPECKLE_TOKEN` and is ignored by `src/.gitignore`. Never print,
copy into a fixture, commit, or include the token in command output.

## Goal

Replace the current Speckle-`Base`-derived `Entity`/`Assembly` implementation
with a small domain-first graph engine that:

1. has explicit and immutable entity and relationship identity;
2. treats relationships as first-class classified records;
3. supports loose, overlapping conceptual assemblies;
4. keeps NetworkX as the private runtime graph engine;
5. separates graph behavior from persistence, projection, and transport;
6. converts to and from Speckle through an adapter rather than inheritance;
7. materializes graph-preserving snapshots and tabular projections;
8. retains the calculations and narrative of the two critical walkthroughs;
9. removes the old public graph API rather than maintaining compatibility
   shims.

Critical walkthroughs:

```text
/Volumes/Data/Projects/Rangekeeper/walkthrough/load_design.ipynb
/Volumes/Data/Projects/Rangekeeper/walkthrough/drive_model_from_design.ipynb
```

Both notebooks must be migrated to the new API and executed top-to-bottom as
release gates.

## Explicit non-goals

Do not add these unless a concrete implementation blocker proves they are
needed:

- compatibility aliases such as `Kind = Classification`;
- wrappers that preserve `Assembly.graph`, `filter_by_type()`,
  `get_entities()`, `get_relatives()`, `to_DataFrame()`, or legacy plotting
  methods;
- a generic repository framework or graph-database abstraction;
- a formal query language;
- saved dynamic assembly predicates;
- multiple-provenance support;
- separate Entity- and Relationship-Characteristics subclasses;
- automatic serialization of every arbitrary object stored in `features`;
- a rewrite of unrelated Rangekeeper finance, duration, flux, projection, or
  model APIs.

There are very few library users. Prefer a clear new API, update the two named
notebooks, and remove the old API in the same workstream.

## Locked design decisions

### 1. Core namespace

The intended public surface is:

```text
rangekeeper.graph
    Entity
    Assembly
    Relationship
    Classification
    Characteristics
    Provenance
    Model
    View
    traversal, validation, query, and graph aggregation operations

rangekeeper.graph.materialization
    Record
    Snapshot
    Table
    projection, grouping, and table aggregation operations

rangekeeper.graph.adapter
    speckle
    json
    csv
    pandas
    visualization
```

Use the singular package name `adapter`, matching this approved design.

### 2. Dependency direction

```text
graph <- materialization <- adapter
```

- `rangekeeper.graph` must not import SpecklePy, pandas, Plotly, PyVis, Jupyter,
  CSV writers, or materialization modules.
- `materialization` may import graph domain types.
- adapters may import materialization, graph types, and their external library.
- NetworkX is permitted inside the graph engine, but raw NetworkX objects must
  not be persisted or exposed as the primary public API.

### 3. Speckle boundary

`Entity`, `Assembly`, `Relationship`, `Classification`, `Characteristics`, and
`Provenance` must not inherit from `specklepy.objects.Base`.

Speckle `Base` is an interchange representation owned by
`rangekeeper.graph.adapter.speckle`.

Maintain the distinction among:

```text
Rangekeeper entity_id      stable domain identity
Speckle applicationId      stable source/application identity
Speckle id                 content hash for one serialized state
```

Do not use Speckle `id` as the Rangekeeper entity identity.

### 4. `Kind` becomes `Classification`

Rename the concept and implementation directly. Do not retain a public `Kind`
alias.

The class represents one classification term in a hierarchy. It retains:

- immutable code;
- name;
- optional definition;
- optional scheme;
- parent/child hierarchy behavior;
- cycle prevention;
- hierarchy-local code uniqueness;
- record conversion.

Classification identity must be scheme-aware or use namespaced codes so that
codes from unrelated schemes cannot collide.

Classifications do **not** have `Characteristics`.

### 5. Entity and relationship classification

An Entity has a primary `Classification | None`.

A Relationship has a required Classification describing what the edge means,
for example:

```text
relationship.member_of
relationship.spatially_contains
relationship.services
relationship.connected_to
relationship.measures
```

The Relationship instance, rather than the Classification definition, may have
Characteristics.

### 6. Characteristics

Use:

```python
@dataclass
class Characteristics:
    occupancy: dict[str, tuple[Classification, ...]]
    measures: dict[Measure, pint.Quantity]
    features: dict[str, object]
```

- `occupancy` generalizes `use`, `tenure`, occupancy status, and occupant type.
- `measures` retains the existing validated `Measure -> Quantity` behavior.
- call the remaining dictionary `features`, not `properties` or `utility`.
- keep `features` open-ended in the engine. The notebooks attach `Flow`,
  `Stream`, parameter dictionaries, event dictionaries, and calculated results
  to entities. Portability is enforced when a value is materialized, not when
  it is used inside the engine.

Provide deliberate convenience properties on Entity:

```python
entity.features
entity.measures
entity.occupancy
```

Do not preserve Base-style arbitrary `entity["..."]` lookup as a compatibility
shim. Migrate notebook usage to explicit domain fields.

### 7. Provenance

Use the approved minimal shape:

```python
@dataclass
class Provenance:
    source: str
    identifiers: dict[str, str] = field(default_factory=dict)
```

Initial owning fields are `Provenance | None`, not a tuple of provenances.

Rules:

- `source` must be a non-empty stable source code;
- identifier keys and values must be non-empty strings;
- copy the incoming identifier dictionary during construction;
- source adapters own the semantics of identifier keys.

Example Speckle provenance:

```python
Provenance(
    source="speckle",
    identifiers={
        "project_id": project_id,
        "model_id": model_id,
        "version_id": version_id,
        "application_id": base.applicationId,
        "object_id": base.id,
    },
)
```

### 8. Relationship endpoints

Relationship stores endpoint IDs, not Entity instances:

```python
@dataclass
class Relationship:
    relationship_id: str
    source_id: str
    target_id: str
    classification: Classification
    characteristics: Characteristics
    provenance: Provenance | None
```

The ergonomic `Model.relate()` method accepts either Entity instances or IDs,
resolves and validates them, and stores IDs.

### 9. Assembly semantics

Assembly is an identifiable Entity subtype representing a durable conceptual
group. It is not the exclusive owner of a separate graph and it does not store
an authoritative member list.

```python
@dataclass(eq=False)
class Assembly(Entity):
    pass
```

Membership is canonical as classified Relationships:

```text
AHU --member_of--> Apartment Assembly
AHU --member_of--> HVAC System Assembly
```

This permits overlapping assemblies without duplicating entities.

`Model.add_assembly(assembly, members=[...])` is a convenience that adds the
Assembly node and creates `member_of` relationships. Membership is a set unless
ordering becomes a demonstrated domain requirement.

Distinguish:

```text
member_of   loose conceptual membership
contains    spatial, compositional, or physical containment
```

An Assembly can participate as an endpoint in arbitrary relationships and can
be a member of another Assembly. Recursive membership traversal must use a
visited set. Whether membership cycles are allowed must be an explicit
validation policy; default to rejecting cycles until a real use case requires
them.

### 10. Model

`Model` is the complete domain graph. It contains, but does not inherit from, an
`nx.MultiDiGraph`.

Canonical NetworkX representation:

```text
node key                         entity.entity_id
node attribute "entity"         exact Entity/Assembly instance
edge key                         relationship.relationship_id
edge attribute "relationship"   exact Relationship instance
```

No public mutation path may bypass Model validation.

### 11. View

Call the transient selected subgraph `View`, not `Selection` or `ModelView`.

```python
@dataclass(frozen=True)
class View:
    model: Model
    entity_ids: frozenset[str]
    relationship_ids: frozenset[str]
```

An Assembly is persisted domain meaning. A View is a temporary read-only window
used for querying, traversal, calculation, materialization, and export.

A View may be deliberately persisted as a new Assembly, but filtering must
never create an Assembly implicitly.

### 12. Graph aggregation

Call the hierarchical graph operation `aggregate`, not `rollup`.

Use either `Model.aggregate(...)` or a namespaced `rangekeeper.graph.aggregate`
service consistently. The public notebook-facing form should be concise, for
example:

```python
model.aggregate(
    view=spatial_containment,
    feature="gfa",
    into="subtotal_gfa",
    function=sum,
)
```

This is distinct from table-style group-by aggregation in materialization.

## Core invariants

Enforce these at every Model mutation boundary:

1. Entity IDs are non-empty strings and immutable after construction.
2. Entity equality and hashing are based on immutable entity ID.
3. Equality with an unrelated object returns `NotImplemented`.
4. No two different entity objects may occupy one entity ID.
5. A graph node key always equals `entity.entity_id`.
6. Every graph node has an Entity/Assembly in its `entity` attribute.
7. Relationship IDs are non-empty and unique within a Model.
8. Relationship endpoint IDs must already exist in the Model.
9. An edge key always equals `relationship.relationship_id`.
10. Every edge has a Relationship in its `relationship` attribute.
11. Relationship classification is required.
12. `member_of` targets must be Assemblies.
13. Batch additions validate completely before mutating the Model.
14. Public filtered graph results are Views, not mutable NetworkX views.
15. NetworkX graph objects are never serialized directly.

Add a full `Model.validate()` that reports all invariant violations, while
normal mutation methods fail fast on the first invalid operation.

## Proposed file layout

```text
src/rangekeeper/graph/
    __init__.py
    entity.py
    assembly.py
    relationship.py
    classification.py
    characteristics.py
    provenance.py
    model.py
    view.py
    traversal.py
    aggregation.py
    validation.py

    materialization/
        __init__.py
        record.py
        snapshot.py
        table.py
        projection.py
        aggregation.py

    adapter/
        __init__.py
        speckle.py
        json.py
        csv.py
        pandas.py
        visualization.py
```

It is acceptable to consolidate small modules initially if doing so improves
clarity. Preserve the namespace and dependency boundaries even if the physical
module count is reduced.

## Domain pseudocode

### Classification

Adapt the current well-tested `Kind` implementation rather than rewriting its
hierarchy algorithms from scratch.

```python
class Classification:
    def __init__(
        self,
        code: str,
        name: str,
        definition: str | None = None,
        *,
        scheme: str | None = None,
        parent: Classification | None = None,
        children: Iterable[Classification] | None = None,
    ) -> None:
        ...

    @property
    def code(self) -> str: ...
    @property
    def scheme(self) -> str | None: ...
    @property
    def parent(self) -> Classification | None: ...
    @property
    def children(self) -> tuple[Classification, ...]: ...

    def ancestors(self) -> tuple[Classification, ...]: ...
    def descendants(self) -> tuple[Classification, ...]: ...
    def find(self, code: str) -> Classification | None: ...
    def to_record(self) -> dict[str, object]: ...
    @classmethod
    def from_records(cls, records: Iterable[Mapping[str, object]]) -> tuple[Classification, ...]: ...
```

Keep code immutable. Name/definition mutability may remain as currently
designed unless tests establish otherwise.

### Entity and Assembly

```python
@dataclass(eq=False)
class Entity:
    entity_id: str = field(default_factory=new_entity_id)
    name: str | None = None
    classification: Classification | None = None
    characteristics: Characteristics = field(default_factory=Characteristics)
    provenance: Provenance | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.entity_id == other.entity_id

    def __hash__(self) -> int:
        return hash(self.entity_id)

    @property
    def features(self) -> dict[str, object]:
        return self.characteristics.features

    @property
    def measures(self) -> dict[Measure, pint.Quantity]:
        return self.characteristics.measures

    @property
    def occupancy(self) -> dict[str, tuple[Classification, ...]]:
        return self.characteristics.occupancy


@dataclass(eq=False)
class Assembly(Entity):
    pass
```

A normal mutable dataclass cannot make only `entity_id` frozen. Implement a
write-once private `_entity_id` plus read-only property, a guarded `__setattr__`,
or a small custom initializer. Test mutation attempts explicitly.

### Relationship

```python
@dataclass
class Relationship:
    relationship_id: str = field(default_factory=new_relationship_id)
    source_id: str = ""
    target_id: str = ""
    classification: Classification | None = None
    characteristics: Characteristics = field(default_factory=Characteristics)
    provenance: Provenance | None = None
```

Prefer a constructor signature that makes invalid partially initialized
relationships impossible. The sketch above illustrates fields, not necessarily
the final parameter order. `classification` must be non-optional in the public
constructor.

Relationship identity should also be immutable. Relationship equality semantics
must be explicit; default to relationship-ID equality.

### Model

```python
class Model:
    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()
        self._classifications: dict[str, Classification] = {}

    def add_entity(self, entity: Entity) -> None: ...
    def add_entities(self, entities: Iterable[Entity]) -> None: ...

    def add_relationship(self, relationship: Relationship) -> None: ...
    def add_relationships(self, relationships: Iterable[Relationship]) -> None: ...

    def relate(
        self,
        source: Entity | str,
        target: Entity | str,
        classification: Classification,
        *,
        characteristics: Characteristics | None = None,
        provenance: Provenance | None = None,
        relationship_id: str | None = None,
    ) -> Relationship: ...

    def add_assembly(
        self,
        assembly: Assembly,
        *,
        members: Iterable[Entity | str] = (),
    ) -> None: ...

    def entity(self, entity_id: str) -> Entity: ...
    def relationship(self, relationship_id: str) -> Relationship: ...
    def entities(self) -> tuple[Entity, ...]: ...
    def relationships(self) -> tuple[Relationship, ...]: ...
    def assemblies(self) -> tuple[Assembly, ...]: ...

    def members(self, assembly: Assembly | str) -> tuple[Entity, ...]: ...
    def assemblies_of(self, entity: Entity | str) -> tuple[Assembly, ...]: ...

    def predecessors(
        self,
        entity: Entity | str,
        relationship: Classification | str | None = None,
    ) -> tuple[Entity, ...]: ...

    def successors(
        self,
        entity: Entity | str,
        relationship: Classification | str | None = None,
    ) -> tuple[Entity, ...]: ...

    def view(
        self,
        *,
        entity_classification: Classification | str | None = None,
        relationship_classification: Classification | str | None = None,
        assembly: Assembly | str | None = None,
        predicate: Callable[[Entity], bool] | None = None,
    ) -> View: ...

    def aggregate(
        self,
        *,
        view: View,
        feature: str,
        into: str | None = None,
        function: Callable[..., object] | None = None,
        outgoing: bool = True,
    ) -> dict[str, object]: ...

    def validate(self) -> ValidationResult: ...
```

Avoid an overly clever fluent query language in this refactor. Add only the
query arguments exercised by tests and notebooks.

### View

```python
@dataclass(frozen=True)
class View:
    model: Model
    entity_ids: frozenset[str]
    relationship_ids: frozenset[str]

    def entities(self) -> tuple[Entity, ...]: ...
    def relationships(self) -> tuple[Relationship, ...]: ...
    def filter(self, ...) -> View: ...
    def expand(self, ...) -> View: ...
    def predecessors(self, entity, relationship=None) -> tuple[Entity, ...]: ...
    def successors(self, entity, relationship=None) -> tuple[Entity, ...]: ...
    def roots(self) -> tuple[Entity, ...]: ...
    def leaves(self) -> tuple[Entity, ...]: ...
    def is_arborescence(self) -> bool: ...
```

If a NetworkX representation is required for an advanced external algorithm,
provide an explicit frozen copy such as `view.to_networkx()`. Do not expose the
Model's mutable internal graph.

## Graph aggregation requirements

The existing `Assembly.aggregate()` is recursive and mutates values with `+=`.
The replacement must be deterministic and idempotent.

Algorithm:

1. Confirm the View contains the intended relationship overlay.
2. Reject an empty View with a clear error.
3. For the initial implementation, require an arborescence. Supporting a DAG
   can follow only with an explicit shared-descendant counting policy.
4. Determine edge direction from `outgoing`.
5. Obtain a topological order and process it in reverse.
6. For each entity, combine its own feature value with already-computed child
   aggregate values.
7. Store results in a new `dict[entity_id, value]`.
8. If `into` is supplied, assign the result to each entity's features after the
   entire calculation succeeds.
9. Never use `+=` on a pre-existing destination feature.
10. Re-running the same aggregation must produce the same result.

Default numeric behavior should include zero rather than filtering all falsey
values. Missing values and explicit `None` need a documented policy.

Custom aggregation must support the existing notebook's `Flow` and `Stream`
values. Prefer a callback receiving explicit values rather than the current
opaque `aggregation` dictionary if that improves clarity. Preserve meaningful
names and frequencies when combining flux objects.

## Materialization

### Record

Use a neutral record rather than a Speckle Base:

```python
@dataclass(frozen=True)
class Record:
    record_type: str
    identifier: str
    values: Mapping[str, object]
```

Initial record types:

```text
classification
entity
assembly
relationship
```

If a generic Record becomes too weak to validate round trips, introduce typed
record subclasses inside materialization. Do not move transport-specific types
into the domain layer.

### Snapshot

```python
@dataclass(frozen=True)
class Snapshot:
    schema_version: int
    records: tuple[Record, ...]
```

Provide:

```python
snapshot(model: Model) -> Snapshot
snapshot(view: View) -> Snapshot
restore(snapshot: Snapshot) -> Model
```

Snapshot must preserve:

- Entity versus Assembly structural type;
- IDs;
- names;
- classifications and hierarchy references;
- Characteristics;
- Relationship endpoints;
- Provenance;
- reference integrity.

NetworkX objects are reconstructed from records and never stored in Snapshot.

Arbitrary rich feature values require an explicit value encoder. Initially,
either support known Rangekeeper types or raise a precise
`MaterializationError` naming the entity, feature, and unsupported type. Never
silently call `str()` as SpecklePy currently does for unsupported objects.

### Table

```python
@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    rows: tuple[Mapping[str, object], ...]
```

Projection owns:

- row grain;
- selected entity fields;
- selected occupancy facets;
- selected measures and target units;
- selected features;
- relationship-derived parent/child columns;
- column names and order;
- handling of multiple classifications;
- tabular group-by aggregation.

CSV and pandas adapters consume Table. They do not query Model directly.

## Adapters

### Speckle

Required high-level API:

```python
load(base: specklepy.objects.Base, *, context: Mapping[str, str] | None = None) -> Model
dump(model_or_view: Model | View) -> specklepy.objects.Base
```

It is acceptable for these to use lower-level `decode() -> Snapshot` and
`encode(Snapshot) -> Base` functions internally.

Inbound conversion of the existing demo design:

```text
Speckle entityId          -> Entity.entity_id
Speckle name              -> Entity.name
Speckle entity type       -> Classification in a legacy entity-type scheme
Speckle Assembly type     -> Assembly structural type
Speckle relationship type -> Classification in a legacy relationship scheme
other dynamic members     -> Characteristics.features
known use/tenure members  -> Characteristics.occupancy when safe to interpret
applicationId/id/context  -> Provenance identifiers
```

Do not guess a sourced Classification scheme when the source supplies only a
free string. Use explicit adapter-owned legacy schemes such as:

```text
legacy.entity_type
legacy.relationship_type
legacy.occupancy.use
legacy.occupancy.tenure
```

The current Speckle data contains repeated logical entities where an Assembly
representation and a non-Assembly representation share an `entityId`. The old
parser prints warnings and keeps the Assembly. Replace this with an explicit,
tested merge rule:

1. identical IDs refer to one logical entity;
2. prefer Assembly structural information when one representation is Assembly;
3. merge only non-conflicting feature values;
4. raise a typed conflict error for incompatible values;
5. do not print warnings from library code; return diagnostics or use logging.

Outbound conversion must use explicit Base record types and reference endpoints
by stable IDs. Never attach an `nx.MultiDiGraph` to a Base.

Map assembly membership to a standard Speckle Group proxy only where the proxy
semantics fit. Preserve arbitrary classified relationships in explicit
Rangekeeper relationship records at the root. Do not force all graph edges into
standard proxies.

### JSON

JSON consumes and produces Snapshot. Include `schema_version`. Preserve IDs and
references. Reject unsupported rich feature values rather than stringifying.

### CSV and pandas

CSV and pandas consume Table:

```python
adapter.csv.write(table, path)
adapter.csv.read(path) -> Table
adapter.pandas.to_dataframe(table) -> pd.DataFrame
adapter.pandas.from_dataframe(frame) -> Table
```

A normal CSV is a lossy table projection, not full graph persistence. A future
multi-file graph CSV bundle is out of scope.

### Visualization

This adapter is required because the two walkthroughs currently rely on:

- PyVis graph HTML;
- Plotly sunburst traces;
- Plotly treemap traces.

Suggested surface:

```python
adapter.visualization.graph_html(view, path, **layout_options)
adapter.visualization.sunburst(hierarchy_table)
adapter.visualization.treemap(hierarchy_table)
```

Visualization consumes View or materialized hierarchy Table, but PyVis, Plotly,
pandas, and IPython must not remain imports of the core graph domain modules.

## Notebook compatibility inventory

### `walkthrough/load_design.ipynb`

The notebook currently exercises:

- Speckle authentication and object receive;
- `rk.api.Speckle.parse()`;
- `rk.api.Speckle.to_rk()`;
- checking the result is an Assembly;
- enumerating all entities;
- finding `buildingA` by name;
- outgoing `spatiallyContains` traversal;
- finding `buildingAresidential`;
- PyVis graph HTML output.

Migrate it to:

```python
design = rk.graph.adapter.speckle.load(
    root["@property"],
    context={
        "project_id": project.id,
        "model_id": model.id,
        "version_id": version.id,
    },
)

building_a = next(
    entity for entity in design.entities() if entity.name == "buildingA"
)

building_a_containment = design.successors(
    building_a,
    relationship="spatiallyContains",
)
```

Do not preserve the old synthetic root Assembly merely because the old parser
returned an Assembly that owned the entire graph. The imported object graph is
now the Model. Preserve actual source Assemblies as Assembly entities.

Use the visualization adapter for the HTML graph.

### `walkthrough/drive_model_from_design.ipynb`

The notebook additionally exercises:

- filtering by relationship type;
- filtering by entity type and Entity versus Assembly;
- testing whether a selected relationship overlay is an arborescence;
- scalar GFA and facade-area hierarchical aggregation;
- custom `Flow` and `Stream` hierarchical aggregation;
- entity table/DataFrame projection including parent IDs;
- roots and predecessor lookup;
- sunburst and treemap visualizations;
- attaching rich runtime features (`params`, `events`, `pgi`, `egi`, `opex`,
  `capex`, `noi`, `nacf`, and aggregate forms) to entities.

Direct migration map:

| Old API | New API |
|---|---|
| `rk.api.Speckle.parse()` | internal to `graph.adapter.speckle.load()` |
| `rk.api.Speckle.to_rk()` | `graph.adapter.speckle.load()` |
| `property.filter_by_type(...)` | `model.view(...)` |
| `entity.get_relatives(...)` | `model.successors()` / `model.predecessors()` |
| `property.get_entities()` | `model.entities()` |
| `filtered.get_entities()` | `view.entities()` |
| `property.get_roots()` | `view.roots()` |
| `nx.is_arborescence(view.graph)` | `view.is_arborescence()` |
| `property.aggregate(...)` | `model.aggregate(...)` |
| `assembly.to_DataFrame()` | projection to Table, then pandas adapter |
| `assembly.plot()` | visualization adapter |
| `assembly.sunburst()` | hierarchy Table plus visualization adapter |
| `assembly.treemap()` | hierarchy Table plus visualization adapter |
| `entity["gfa"]` | `entity.features["gfa"]` |
| `entity["use"]` | occupancy Classification code/name, or a documented legacy feature during import |

Preserve the notebooks' teaching narrative and cell order where practical.
Edit notebooks through `nbformat` or Jupyter tooling, not raw global JSON
rewrites. Clear stale outputs before the first execution, then keep the final
executed outputs bounded and useful.

## Existing notebook results to preserve

The saved output in `drive_model_from_design.ipynb` provides these regression
anchors. Allow only explained numerical differences caused by a corrected bug:

```text
Spatial containment is an arborescence: True
Property subtotal GFA:                 42,786.259115
Property average periodic OPEX:        $-7,488,734.31
Property average periodic CAPEX:       $-2,007,558.91
Property average periodic PGI:         $18,918,012.54
Property OPEX / PGI:                   39.59%
Property CAPEX / PGI:                  10.61%
Property PV:                           $212,735,036
```

The saved `load_design.ipynb` output also establishes:

- project `RangekeeperDemo`, ID `c0f66c35e3`;
- model `main`, ID `119ad04487`;
- version `9a9670946f`;
- referenced object `e7acaac21ae7e9369339900a4aaeb827`;
- root contains `@property`;
- `buildingA` has six outgoing `spatiallyContains` relatives in the saved
  result;
- `buildingAresidential` is discovered among them.

Add explicit assertion/check cells for the most important invariants instead of
relying only on visible output.

## Implementation phases

### Phase 0: preflight and characterization

1. Navigate to `/Volumes/Data/Projects/Rangekeeper`.
2. Read this plan and both linked Codex task histories.
3. Inspect `git status`, branch, HEAD, and all diffs.
4. Preserve the pre-existing dirty edits described above.
5. Run the focused 37-test baseline.
6. Confirm `src/.env` exists and contains a non-empty `SPECKLE_TOKEN` without
   printing it.
7. Read both notebooks using `nbformat`/`jq` and capture their current API use.
8. If practical, run the current notebooks before changing code and save the
   regression values above.
9. Add or obtain a sanitized Speckle test fixture for deterministic adapter
   tests. Never include credentials. If the received object contains sensitive
   project data, use a purpose-built synthetic fixture instead of committing it.

Gate: current behavior and dirty state are understood; no user work has been
lost.

### Phase 1: domain value objects

1. Rename `kind.py` to `classification.py` and `Kind` to `Classification`.
2. Update public exports and all internal/test imports directly.
3. Rename `test_kinds.py` to `test_classifications.py`.
4. Preserve and expand hierarchy tests.
5. Implement minimal Provenance and tests.
6. Update Characteristics to use `occupancy`, `measures`, and `features`.
7. Migrate current use/tenure tests to occupancy classifications.
8. Implement Entity, Assembly, and Relationship without Speckle Base.
9. Add immutable ID, equality, default-isolation, and validation tests.

Gate: value objects and domain records pass without importing SpecklePy or
NetworkX from Entity/Relationship modules.

### Phase 2: Model and View

1. Implement Model with private `nx.MultiDiGraph`.
2. Implement validated atomic entity and relationship insertion.
3. Implement direct lookup and enumeration.
4. Implement `relate()` accepting instance or ID endpoints.
5. Implement Assembly insertion and member relationships.
6. Implement View selection by entity classification, relationship
   classification, assembly, and predicate.
7. Implement predecessor/successor, roots/leaves, traversal, and arborescence.
8. Implement `Model.validate()` and typed errors/results.
9. Add tests for collisions, dangling endpoints, duplicate edge IDs, overlapping
   assemblies, and nested membership.

Gate: the graph model cannot reach an invalid state through its public API.

### Phase 3: graph aggregation

1. Implement reverse-topological aggregation for arborescences.
2. Make it pure by default and optionally assign through `into` only after
   success.
3. Add numeric tests including zero and missing values.
4. Add idempotence tests.
5. Add custom aggregation tests for existing `Flow` and `Stream` objects.
6. Add cycle and multi-parent failure tests with precise errors.

Gate: GFA and flux aggregation behavior is deterministic and notebook-ready.

### Phase 4: materialization

1. Implement Record and Snapshot.
2. Implement Snapshot creation from Model and View.
3. Implement restore with reference resolution and full validation.
4. Add JSON-compatible encoding for core fields, Classification,
   Characteristics, Provenance, Measure, and Pint quantities.
5. Define clear errors for unsupported rich feature values.
6. Implement Table and the projections required by the notebook DataFrame.
7. Implement hierarchy Table including parent IDs and aggregate values.
8. Implement table grouping/aggregation only as exercised by tests.

Gate: a supported Model snapshot round-trips exactly; View projection produces
the expected table rows and parent links.

### Phase 5: adapters

1. Implement JSON Snapshot round trip.
2. Implement pandas Table conversion.
3. Implement CSV Table conversion.
4. Implement Speckle inbound conversion first, including duplicate logical
   entity reconciliation.
5. Implement explicit outbound Speckle records and graph package root.
6. Confirm no adapter silently stringifies unsupported objects.
7. Implement visualization adapter for graph HTML, sunburst, and treemap.

Gate: the sanitized/synthetic Speckle fixture imports into the expected Model;
supported Snapshot data round-trips through Speckle and JSON; Table round-trips
through pandas/CSV as defined.

### Phase 6: migrate walkthroughs

1. Update `load_design.ipynb` to the new Speckle adapter, Model queries, and
   visualization adapter.
2. Add concise assertion cells for imported structure and `buildingA` traversal.
3. Update `drive_model_from_design.ipynb` to View, Model aggregation,
   Characteristics access, Table/pandas projection, and visualization adapter.
4. Preserve calculations and explanatory flow.
5. Replace direct NetworkX access with View methods.
6. Execute both notebooks top-to-bottom with local package code and
   `src/.env`.
7. Compare numerical outputs with the regression anchors.

Gate: both notebooks execute successfully with no legacy graph calls.

### Phase 7: remove legacy implementation

After new code and notebooks work:

1. Remove `rk.api.Speckle.parse()` and `to_rk()`.
2. Remove Entity/Assembly inheritance from Speckle Base.
3. Remove `Kind` and all old naming.
4. Remove public Assembly graph ownership and mutation.
5. Remove `filter_by_type()`, `get_entities()`, `get_entity()`,
   `get_relatives()`, and old root/leaf methods.
6. Remove graph `to_dict()`/`to_DataFrame()` and visualization methods.
7. Remove heavy visualization/pandas/IPython imports from core graph modules.
8. Update `test_api.py`, `test_graph.py`, exports, README examples, and any
   other references found by `rg`.
9. Do not add compatibility aliases or deprecation wrappers.

Gate: `rg` finds no unintended old API use in source, tests, or the two required
notebooks.

### Phase 8: final verification and commits

1. Run formatting and linting configured by the repository.
2. Run focused graph/materialization/adapter tests.
3. Run all non-live tests.
4. Run live Speckle adapter tests.
5. Execute both notebooks top-to-bottom.
6. Inspect notebook output for errors, warnings, excessive raw output, and
   numerical regressions.
7. Run `git diff --check`.
8. Review the entire diff for unrelated changes and accidental secret/output
   inclusion.
9. Commit in coherent checkpoints. Do not mix the pre-existing user edits into
   a graph commit unless their intent is explicitly adopted and documented.
10. Push only if the user explicitly requests it in the executing task.

## Test plan

### Domain tests

- Classification code validation and immutability.
- Hierarchy parent/child consistency.
- Duplicate code rejection.
- Cycle rejection.
- Record round trip.
- Characteristics default isolation.
- Occupancy type validation.
- Measure/quantity validation retained.
- Features accept rich runtime values.
- Provenance copies identifiers and validates strings.
- Entity ID immutability.
- Entity equality with Entity and unrelated objects.
- Relationship ID immutability and equality.
- Relationship endpoint and classification validation.

### Model tests

- Node key/attribute invariant.
- Edge key/attribute invariant.
- Duplicate entity ID conflict.
- Duplicate relationship ID conflict.
- Dangling endpoint rejection.
- Atomic batch insertion.
- Same entity in multiple Assemblies.
- Assembly can be a relationship endpoint.
- `member_of` target must be Assembly.
- Nested assembly traversal terminates.
- Membership-cycle default policy.
- Classification-filtered View.
- Relationship-filtered View.
- Assembly View.
- Roots, leaves, predecessor, successor.
- View immutability/read-only behavior.
- Complete `Model.validate()` diagnostics.

### Aggregation tests

- Single-node tree.
- Multi-level numeric tree.
- Zero values.
- Missing/None values.
- Incoming/outgoing orientation.
- Idempotence with `into`.
- Destination assignment occurs only after success.
- Cycle rejection.
- Multi-parent/DAG policy rejection.
- Flow aggregation.
- Stream aggregation.

### Materialization tests

- Entity/Assembly structural type preservation.
- Relationship endpoint reference preservation.
- Classification hierarchy preservation.
- Provenance preservation.
- Occupancy, measures, features preservation for supported types.
- Unsupported feature produces precise error.
- Model Snapshot round trip.
- View Snapshot includes required endpoints/classifications.
- Entity Table projection.
- Parent column projection.
- Measure unit conversion.
- Multiple-classification table policy.
- pandas conversion.
- CSV conversion.

### Speckle adapter tests

- Plain Entity import.
- Assembly import.
- Relationship import.
- Duplicate Entity/Assembly reconciliation.
- Conflict rejection.
- Provenance identifiers.
- Unknown dynamic members become features.
- Legacy type strings become adapter-owned Classifications.
- No NetworkX serialization.
- Explicit relationship records round-trip.
- Standard Group proxy mapping for compatible membership.
- Unsupported feature does not stringify silently.

## Commands for Daniel's Mac Studio

### Preflight

```bash
cd /Volumes/Data/Projects/Rangekeeper
git branch --show-current
git log -1 --oneline --decorate
git status --short
git diff --stat
```

### Focused baseline

```bash
cd /Volumes/Data/Projects/Rangekeeper/src
uv run pytest \
  tests/test_kinds.py \
  tests/test_characteristics.py \
  tests/test_measures.py \
  tests/test_graph.py \
  -q
```

Adjust filenames after `Kind` becomes `Classification`.

### Full library tests

```bash
cd /Volumes/Data/Projects/Rangekeeper/src
uv run pytest tests -q
```

If live Speckle tests are separated with a marker, run both the default suite and
the explicit live suite.

### Notebook execution with local package and credentials

Run from the repository root. `uv --env-file` loads the ignored token without
relying on `dotenv.find_dotenv()` discovering a sibling directory.

```bash
cd /Volumes/Data/Projects/Rangekeeper

uv run \
  --project walkthrough \
  --with-editable src \
  --env-file src/.env \
  python -m jupyter nbconvert \
  --execute \
  --to notebook \
  --inplace \
  walkthrough/load_design.ipynb

uv run \
  --project walkthrough \
  --with-editable src \
  --env-file src/.env \
  python -m jupyter nbconvert \
  --execute \
  --to notebook \
  --inplace \
  walkthrough/drive_model_from_design.ipynb
```

If notebook execution requires a timeout, pass an explicit large timeout through
nbconvert rather than allowing cells to hang indefinitely.

### Search for legacy graph use

```bash
cd /Volumes/Data/Projects/Rangekeeper
rg -n \
  'rk\.graph\.Kind|filter_by_type|get_relatives|get_entities|to_DataFrame|\.graph\b|rk\.api\.Speckle\.(parse|to_rk)' \
  src walkthrough/load_design.ipynb walkthrough/drive_model_from_design.ipynb
```

Review matches individually; `.graph` may legitimately appear in the package
namespace or internal Model implementation.

## Completion criteria

The implementation is complete only when all of these are true:

1. Core Entity/Assembly/Relationship classes no longer inherit Speckle Base.
2. `Classification` fully replaces `Kind` in the supported API.
3. Entity and relationship IDs are immutable.
4. Model is the sole owner of the mutable NetworkX graph.
5. Relationship endpoints are stored as IDs.
6. Assemblies support overlapping membership without entity duplication.
7. View is the transient selected-subgraph concept.
8. Graph aggregation is named `aggregate`, is topological, and is idempotent.
9. Snapshot round-trips all supported core graph state.
10. Table projection supplies the notebook DataFrame use case.
11. Speckle conversion is adapter-based and does not stringify unsupported
    objects.
12. Visualization is outside core graph modules.
13. No compatibility shims preserve the deleted graph API.
14. All automated tests pass.
15. Both required notebooks execute successfully top-to-bottom with local code.
16. The saved financial outputs match the documented regression anchors or any
    difference is explained by an intentional bug fix and accepted by the user.
17. No credential or sensitive `.env` content appears in Git history, fixtures,
    notebook outputs, or logs.

## Decisions to make only if implementation forces them

These questions are intentionally deferred and should not block initial work:

- whether relationship Classifications later gain formal cardinality/direction
  metadata;
- whether graph aggregation should support general DAGs and how shared
  descendants are counted;
- whether Assembly membership cycles ever have legitimate meaning;
- whether a future View can be defined by a saved serializable query;
- whether multiple Provenance records are needed for merged data;
- how every rich Rangekeeper financial object should be represented in a full
  Snapshot;
- whether a standard Speckle proxy can represent each specialized Rangekeeper
  relationship.

Use the simplest behavior documented above until a current test or notebook
demonstrates the need for expansion.

