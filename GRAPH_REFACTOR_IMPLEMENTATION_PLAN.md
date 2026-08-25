# Rangekeeper Graph Refactor Implementation Plan

## Execution handoff

This document is the authoritative implementation brief for a deliberate
breaking refactor of Rangekeeper's entity/relationship graph system. Portable
Python and C# work can be developed on **Daniel's Mac Studio**. Rhino 8,
Grasshopper, the official Speckle v3 connector, and end-to-end publication are
tested on a dedicated **Windows host**. See
[`grasshopper/WINDOWS_DEVELOPMENT.md`](grasshopper/WINDOWS_DEVELOPMENT.md) for
the reproducible Windows runbook.

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

Handoff update after the plan was created:

```text
HEAD:       abda45a chore: prepare graph refactor handoff
Remote:     origin/feat/entity-area-core at the same commit
State:      clean before this plan amendment
```

The previously uncommitted edits described below are now committed in
`abda45a`; the warning remains as historical context for understanding that
commit. The Assembly design was subsequently amended so an Assembly contains
explicit canonical Entity and Relationship sets rather than synthetic
`member_of` relationships.

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

## Current status

Status at `8502817` on 2026-08-22:

| Phase | Status | Result |
|---|---|---|
| 0 | Complete | Baseline and legacy behavior characterized. |
| 1 | Complete | Domain value objects and classifications implemented. |
| 2 | Complete | Model, registries, View, traversal, and validation implemented. |
| 3 | Complete | Graph aggregation implemented. |
| 4 | Complete | Snapshot, Record, Table, and arborescence materialization implemented. |
| 5 | Complete | JSON, pandas, CSV, Speckle, and visualization adapters implemented. |
| 6 | Next | Rebuild the Grasshopper authoring path, publish with Speckle v3 on Windows, and migrate the walkthroughs. |
| 7 | Pending | Remove all legacy implementation and conversion scaffolding. |
| 8 | Pending | Complete cross-platform verification and release commits. |

Phase 6 no longer republishes the legacy v2 object as the target deliverable.
The legacy object and saved notebook outputs are read-only regression evidence.
The new package is regenerated from `grasshopper/Tests/exampleDesign.3dm` and a
rewritten `exampleDesignConfig.ghx`, then published through the supported
Windows Speckle v3 connector.

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
- first-class membership records or a canonical `member_of` relationship;
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

Grasshopper follows the same boundary:

- Rangekeeper's C# domain model and Grasshopper components must not inherit
  from Speckle `Base` or reference connector-internal wrapper/Goo types.
- Rangekeeper components construct entities, relationships, taxonomies,
  assemblies, and a canonical Snapshot independently of Speckle.
- They expose Rhino geometry, stable Rangekeeper IDs, display metadata, and the
  canonical Snapshot envelope using ordinary Grasshopper-compatible values.
- The official Speckle v3 Grasshopper components own Data Object creation,
  Collection construction, Rhino geometry conversion, authentication, model
  selection, and publication.
- Speckle Data Objects carry stable entity association metadata. The root
  Collection carries the canonical Snapshot payload. Geometry/Collection
  structure is useful for Speckle viewing, but the Snapshot remains the sole
  source of truth for graph reconstruction.
- Do not create a Rangekeeper connector fork or make the Rangekeeper component
  assembly depend on Speckle connector implementation details.

The logical root envelope retains `packageKind = "rangekeeper.snapshot"`, an
explicit package schema version, and a deterministic Snapshot payload. The
short Windows integration spike in Phase 6 must freeze the exact supported v3
property layout in a sanitized fixture before the Python adapter is changed.

### 4. `Kind` becomes `Classification`

Rename the concept and implementation directly. Do not retain a public `Kind`
alias.

`Classification` represents one term owned by a `Taxonomy`. It retains:

- immutable code;
- name;
- optional definition;
- a read-only owning Taxonomy;
- thin hierarchy-query delegates.

`Taxonomy` owns the NetworkX hierarchy, enforces one root and taxonomy-local
code uniqueness, and freezes when registered by a Model. Classification
identity is `(taxonomy.code, classification.code)` so codes from unrelated
taxonomies cannot collide.

Classifications do **not** have `Characteristics`.

### 5. Entity and relationship classification

An Entity has a primary `Classification | None`.

A Relationship has a required Classification describing what the edge means,
for example:

```text
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
    labels: dict[str, tuple[Classification, ...]]
    measures: dict[Measure, pint.Quantity]
    features: dict[str, object]
```

- `labels` generalizes `use`, `tenure`, occupancy status, and occupant type.
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
entity.labels
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
@dataclass(eq=False)
class Relationship:
    relationship_id: str
    source_id: str
    target_id: str
    classification: Classification
    characteristics: Characteristics
    provenance: Provenance | None
```

The ergonomic `model.relationships.connect()` method accepts either Entity
instances or IDs, resolves and validates them, and stores IDs.

### 9. Assembly semantics

Assembly is an identifiable Entity subtype representing a durable named
subgraph. It contains sets of canonical Entity/Assembly and Relationship
instances. It does not own copies of those objects or a separate authoritative
NetworkX graph.

```python
@dataclass(eq=False)
class Assembly(Entity):
    _entities: set[Entity]
    _relationships: set[Relationship]

    @property
    def entities(self) -> frozenset[Entity]: ...

    @property
    def relationships(self) -> frozenset[Relationship]: ...
```

Assembly inclusion is structural metadata, not a domain Relationship. Do not
create synthetic `member_of` edges. Characteristics and Provenance belong to
the Assembly, its contained Entities, and its contained Relationships. There
is no separate membership object or per-membership metadata.

The sets contain the same object instances registered in Model. Snapshot and
adapter representations store their stable IDs rather than recursive copies.
This permits the same Entity or Relationship to appear in multiple Assemblies
without duplication.

The Assembly itself is implicit in its selected subgraph and is not included in
its own `entities` set. Every contained Relationship endpoint must be either:

- an Entity in the Assembly's `entities` set; or
- the Assembly itself.

An Assembly may contain another Assembly because Assembly is an Entity subtype.
Recursive Assembly containment cycles are rejected. Traversal of nested
Assemblies must still use a visited set as defensive protection.

Model is the mutation and validation boundary after registration. Assembly
constructor inputs are copied, public collection properties are read-only, and
the model-bound `model.assemblies` service updates registered Assembly contents
atomically. Direct collection mutation must not bypass Model validation.

`model.assemblies.add(assembly)` atomically registers the Assembly, recursively
registers any contained Assemblies and their contents, and registers its other
contained Entities and Relationships. An Assembly can also participate as an
endpoint in arbitrary classified Relationships; those Relationships describe
domain meaning such as spatial containment or service, not membership.

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

Expose aggregation on `View`, which already owns both the selected graph and its
Model. The public notebook-facing form should be concise, for example:

```python
spatial_containment.aggregate(
    feature="gfa",
    into="subtotal_gfa",
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
12. Assembly contents reference the exact canonical objects registered in the
    Model.
13. Every contained Relationship endpoint is contained by the Assembly or is
    the Assembly itself.
14. Recursive Assembly containment cycles are rejected.
15. Batch additions validate completely before mutating the Model.
16. Public filtered graph results are Views, not mutable NetworkX views.
17. NetworkX graph objects are never serialized directly.

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

### Taxonomy and Classification

Use NetworkX once, inside Taxonomy, rather than maintaining synchronized parent
and child references on every Classification.

```python
class Taxonomy:
    def __init__(
        self,
        code: str,
        name: str,
        definition: str | None = None,
    ) -> None:
        ...

    @property
    def code(self) -> str: ...
    def define(
        self,
        *,
        code: str,
        name: str,
        definition: str | None = None,
        parent: Classification | None = None,
    ) -> Classification: ...
    def classifications(self) -> tuple[Classification, ...]: ...
    def freeze(self) -> None: ...

class Classification:
    @property
    def taxonomy(self) -> Taxonomy: ...
    @property
    def code(self) -> str: ...
    @property
    def key(self) -> tuple[str, str]: ...
    @property
    def parent(self) -> Classification | None: ...
    @property
    def children(self) -> tuple[Classification, ...]: ...

    def ancestors(self) -> tuple[Classification, ...]: ...
    def descendants(self) -> tuple[Classification, ...]: ...
    def find(self, code: str) -> Classification | None: ...
```

Construct Classifications through `Taxonomy.define()`. Keep taxonomy and
classification codes immutable. Name/definition mutability may remain unless
tests establish otherwise. Materialization, not the domain classes, owns record
conversion.

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
    def labels(self) -> dict[str, tuple[Classification, ...]]:
        return self.characteristics.labels


@dataclass(eq=False)
class Assembly(Entity):
    _entities: set[Entity] = field(default_factory=set, repr=False)
    _relationships: set[Relationship] = field(default_factory=set, repr=False)

    @property
    def entities(self) -> frozenset[Entity]:
        return frozenset(self._entities)

    @property
    def relationships(self) -> frozenset[Relationship]:
        return frozenset(self._relationships)
```

A normal mutable dataclass cannot make only `entity_id` frozen. Implement a
write-once private `_entity_id` plus read-only property, a guarded `__setattr__`,
or a small custom initializer. Test mutation attempts explicitly.

The Assembly sketch illustrates contained object references, not the final
constructor mechanics. Copy incoming iterables before validation, detect
different objects sharing an ID before constructing the sets, and expose
read-only collection properties. Once an Assembly is registered, content
changes go through Model so its canonical registries and graph remain in sync.

### Relationship

```python
@dataclass(eq=False)
class Relationship:
    relationship_id: str = field(default_factory=new_relationship_id)
    source_id: str = ""
    target_id: str = ""
    classification: Classification | None = None
    characteristics: Characteristics = field(default_factory=Characteristics)
    provenance: Provenance | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Relationship):
            return NotImplemented
        return self.relationship_id == other.relationship_id

    def __hash__(self) -> int:
        return hash(self.relationship_id)
```

Prefer a constructor signature that makes invalid partially initialized
relationships impossible. The sketch above illustrates fields, not necessarily
the final parameter order. `classification` must be non-optional in the public
constructor.

Relationship identity should also be immutable. Relationship equality semantics
must be explicit and use relationship-ID equality so canonical Relationships
can participate in Assembly sets. Endpoint IDs and classification must also be
immutable after registration so Assembly and Model invariants cannot be changed
behind Model's back.

### Model

Model owns graph state and atomic transactions. Its public graph API is grouped
into stable, read-only service properties. Registry services do not own
independent dictionaries and cannot mutate state except through Model's private
transaction kernel.

```python
class Model:
    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()
        self._entities: dict[str, Entity] = {}
        self._relationships: dict[str, Relationship] = {}
        self._taxonomies: dict[str, Taxonomy] = {}
        self._classifications: dict[tuple[str, str], Classification] = {}

    @property
    def entities(self) -> EntityRegistry: ...

    @property
    def relationships(self) -> RelationshipRegistry: ...

    @property
    def assemblies(self) -> AssemblyRegistry: ...

    @property
    def taxonomies(self) -> TaxonomyRegistry: ...

    def validate(self) -> ValidationResult: ...
```

The public services use a small consistent vocabulary:

```python
model.entities.add(entity)
model.entities.add_all(entities)
model.entities[entity_id]
model.entities.get(entity_id)
model.entities.all()

model.relationships.add(relationship)
model.relationships.add_all(relationships)
model.relationships.connect(source, target, classification)

model.assemblies.add(assembly)
model.assemblies.include(assembly, entity, relationship)
model.assemblies.exclude(assembly, entity, relationship)
model.assemblies.containing(entity_or_relationship)

model.taxonomies.add(taxonomy)
View(model, ...)
```

`EntityRegistry`, `RelationshipRegistry`, `AssemblyRegistry`, and
`TaxonomyRegistry` are model-bound registry facades. Views are immutable derived
values constructed directly with `View(model, ...)`; they are not registered
objects and do not require a model-bound factory. No service exposes
`__setitem__`, `__delitem__`, or object deletion.

Assembly targets may be an Assembly or assembly ID. Positional members passed
to `include()` and `exclude()` must be Entity or Relationship instances;
strings are rejected because their registry is ambiguous. Exclusion removes
only membership and leaves the objects registered with Model.

Taxonomy registration adopts the complete Taxonomy, registers all of its
Classifications, and freezes it. Classifications are accessed through their
owning Taxonomy rather than a separate public Model registry.

Avoid an overly clever fluent query language in this refactor. Add only the
query arguments exercised by tests and notebooks.

`model.assemblies.add()` validates and registers the Assembly, its contained
Entities, and its contained Relationships as one atomic operation.
Assembly-scoped View selection includes the Assembly itself plus exactly its
contained entities and relationships. `include()` and `exclude()` validate the
complete proposed result before modifying either the Assembly or Model.

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
    def aggregate(
        self,
        *,
        feature: str,
        into: str | None = None,
        reduce: AggregationCallback | None = None,
    ) -> dict[str, object]: ...
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
4. Treat each Relationship's source-to-target direction as parent-to-child.
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
values. A reducer receives the current Entity and a tuple containing its own
non-None value followed by the already-aggregated values of its children.
Preserve meaningful names and frequencies when combining flux objects.

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
taxonomy
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
- each Assembly's contained entity and relationship ID sets;
- IDs;
- names;
- taxonomies, classifications, and hierarchy references;
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
- selected label keys;
- selected measures and target units;
- selected features;
- arborescence-derived parent columns;
- column names and order;
- handling of multiple classifications;
- tabular group-by aggregation.

CSV and pandas adapters consume Table. They do not query Model directly.

## Adapters

### Speckle

Final high-level API:

```python
load(base: specklepy.objects.Base) -> Model
dump(model_or_view: Model | View) -> specklepy.objects.Base
```

It is acceptable for these to use lower-level `decode() -> Snapshot` and
`encode(Snapshot) -> Base` functions internally.

In the final API, `load()` accepts only an explicit, versioned Rangekeeper
Snapshot package. Phase 5 may temporarily auto-detect and import the existing
demo design schema so that it can be converted, but that path is migration
scaffolding rather than supported backwards compatibility. Phase 7 removes the
fallback completely.

Temporary inbound conversion of the existing demo design:

```text
Speckle entityId          -> Entity.entity_id
Speckle name              -> Entity.name
Speckle entity type       -> Classification in a legacy entity-type Taxonomy
Speckle Assembly type     -> Assembly structural type
Speckle relationship type -> Classification in a legacy relationship Taxonomy
other dynamic members     -> Characteristics.features
known use/tenure members  -> Characteristics.labels when safe to interpret
applicationId/id/context  -> Provenance identifiers
```

Do not guess a sourced Taxonomy when the source supplies only a free string.
Use explicit adapter-owned legacy Taxonomy codes such as:

```text
legacy.entity_type
legacy.relationship_type
legacy.labels.use
legacy.labels.tenure
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

These legacy Taxonomies and reconciliation rules exist only to perform the
one-time conversion. They must not appear in the final package-only Speckle
adapter after Phase 7.

Outbound conversion must use explicit Base record types and reference endpoints
by stable IDs. Never attach an `nx.MultiDiGraph` to a Base.

Map Assembly contents to a standard Speckle Group proxy only where the proxy
semantics fit. Preserve each Assembly's exact entity and relationship references
in explicit Rangekeeper records so Group conversion is never the sole source of
truth. Preserve arbitrary classified relationships in explicit Rangekeeper
relationship records at the root. Do not force all graph edges into standard
proxies.

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

The initial CSV contract writes only `None`, string, Boolean, integer, and
finite floating-point cells, rejecting rich cells rather than stringifying
them. Both directions compose through the pandas adapter, so CSV reading uses
normal pandas type and missing-value inference. pandas conversion preserves
in-memory cell objects and deliberately ignores the DataFrame index.

### Visualization

This adapter is required because the two walkthroughs currently rely on:

- PyVis graph HTML;
- Plotly sunburst traces;
- Plotly treemap traces.

Suggested surface:

```python
adapter.visualization.graph_html(view, path, **layout_options)
adapter.visualization.sunburst(arborescence_table)
adapter.visualization.treemap(arborescence_table)
```

Visualization consumes View or materialized arborescence Table, but PyVis, Plotly,
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

The final migrated notebook loads the newly generated, versioned Rangekeeper
package published through the Windows Speckle v3 workflow:

```python
package = operations.receive(obj_id=published_object_id, remote_transport=transport)
design = rk.graph.adapter.speckle.load(package)

building_a = next(
    entity for entity in design.entities.all() if entity.name == "buildingA"
)

building_a_containment = design.entities.successors(
    building_a,
    relationship="spatiallyContains",
)
```

During Phase 6, use the temporary importer only to characterize the existing
`root["@property"]` and verify the regression baseline. Regenerate the supported
package from the Rhino/Grasshopper source and point both notebooks at that new
Speckle v3 package before Phase 7 begins. Do not retain legacy conversion code
in either final notebook.

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
| `rk.api.Speckle.parse()` | Phase 6 baseline characterization only; removed afterward |
| `rk.api.Speckle.to_rk()` | `graph.adapter.speckle.load()` on the newly generated package |
| `property.filter_by_type(...)` | `View(model, ...)` |
| `entity.get_relatives(...)` | `model.entities.successors()` / `model.entities.predecessors()` |
| `property.get_entities()` | `model.entities.all()` |
| `filtered.get_entities()` | `view.entities()` |
| `property.get_roots()` | `view.roots()` |
| `nx.is_arborescence(view.graph)` | `view.is_arborescence()` |
| `property.aggregate(...)` | `view.aggregate(...)` |
| `assembly.to_DataFrame()` | projection to Table, then pandas adapter |
| `assembly.plot()` | visualization adapter |
| `assembly.sunburst()` | arborescence Table plus visualization adapter |
| `assembly.treemap()` | arborescence Table plus visualization adapter |
| `entity["gfa"]` | `entity.features["gfa"]` |
| `entity["use"]` | label Classification code/name |

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
6. Update Characteristics to use `labels`, `measures`, and `features`.
7. Migrate current use/tenure tests to label classifications.
8. Implement Entity, Assembly, and Relationship without Speckle Base.
9. Add immutable ID, equality, default-isolation, and validation tests.

Gate: value objects and domain records pass without importing SpecklePy or
NetworkX from Entity/Relationship modules.

### Phase 2: Model and View

1. Implement Model with private `nx.MultiDiGraph`.
2. Implement validated atomic entity and relationship insertion.
3. Implement model-bound registry lookup and enumeration.
4. Implement `model.relationships.connect()` accepting instance or ID endpoints.
5. Implement atomic Assembly insertion from contained Entity and Relationship
   sets, plus validated Assembly content mutation.
6. Implement View selection by entity classification, relationship
   classification, assembly, and predicate.
7. Implement predecessor/successor, roots/leaves, traversal, and arborescence.
8. Implement `Model.validate()` and typed errors/results.
9. Add tests for collisions, dangling endpoints, duplicate edge IDs, overlapping
   assemblies, exact relationship inclusion, and nested Assembly containment.

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

### Phase 4: materialization (complete)

1. Implement Record and Snapshot.
2. Implement Snapshot creation from Model and View.
3. Implement restore with reference resolution and full validation.
4. Add JSON-compatible encoding for core fields, Classification,
   Characteristics, Provenance, Measure, and Pint quantities.
5. Define clear errors for unsupported rich feature values.
6. Implement Table and the projections required by the notebook DataFrame.
7. Implement `Table.from_arborescence()` including parent IDs, deterministic
   parent-before-child ordering, and projection of aggregate feature values.
8. Implement table grouping/aggregation only as exercised by tests.

Gate: a supported Model snapshot round-trips exactly; View projection produces
the expected table rows and parent links.

### Phase 5: adapters (complete)

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

#### 6A. Freeze the regression baseline

1. Treat the existing Speckle v2 model and saved notebook outputs as read-only
   regression evidence; do not publish a converted legacy object as the new
   canonical source.
2. Preserve the observed graph baseline: 50 canonical entity IDs and 63
   relationships, comprising 49 `spatiallyContains`, 3 `contains`, and 11
   `services` relationships.
3. Preserve the existing notebook numerical anchors and the documented
   `buildingA` traversal result.
4. Preserve the inspected source-model baseline: `exampleDesign.3dm` contains
   735 objects across 30 layers, including 12 semantically tagged mass objects.
   Confirm the intended source attributes used to create stable entity IDs and
   labels before changing the source file.
5. Preserve the inspected definition baseline: `exampleDesignConfig.ghx`
   contains 222 components and uses Speckle connector 2.17.1 components. These
   counts describe the legacy source; the rewritten definition need not retain
   its component count.
6. Store only sanitized fixtures and expected values. Never store Speckle
   tokens or private account configuration.

#### 6B. Rebuild the C# domain and Grasshopper components

1. Retarget the Grasshopper solution to Rhino 8 and a supported modern .NET
   target. Remove all Speckle v2 package references.
2. Keep a Speckle-independent C# domain assembly mirroring the canonical Python
   concepts: Entity, Relationship, Assembly, Taxonomy, Classification,
   Characteristics, Provenance, Record, and Snapshot.
3. Give the C# and Python implementations shared canonical JSON fixtures so
   each language can read the other's Snapshot output exactly.
4. Implement Grasshopper parameters/components for constructing and inspecting
   those domain values. Inputs must permit explicit stable IDs; Rhino object IDs
   may be used as source/application identifiers but must not be confused with
   Speckle content IDs.
5. Implement a single export-boundary component or small component group that
   emits geometry, names, stable IDs, ordinary metadata, and the canonical
   Snapshot envelope for the official connector nodes.
6. Add pure unit tests for domain validation, deterministic serialization,
   relationship endpoints, assembly contents, labels, and ID stability.
7. Add Grasshopper component tests for input validation, list/tree matching,
   null handling, and deterministic recomputation.

#### 6C. Rebuild the source definition

1. Rewrite `grasshopper/Tests/exampleDesignConfig.ghx` for Rhino 8.
2. Use native Rhino 8 model-object querying where practical. Remove EleFront,
   Speckle v2, and obsolete Rangekeeper component dependencies.
3. Preserve and clarify the source logic that selects geometry, assigns stable
   identities and classifications, and constructs containment and service
   relationships.
4. Keep the canvas staged and reviewable: source selection, metadata,
   Rangekeeper graph construction, validation, Speckle packaging, and explicit
   publication.
5. Publication must require an explicit user-controlled run input and must not
   occur merely because Grasshopper recomputes.

#### 6D. Establish the Windows acceptance host

1. Follow `grasshopper/WINDOWS_DEVELOPMENT.md` to provision native Windows,
   Rhino 8, the official Speckle v3 connector, Codex, SSH, .NET, Python, and Git.
2. Keep the repository on the native Windows filesystem in its own Git checkout.
   Do not use a VM-shared checkout.
3. Pin and record the exact Rhino, connector, .NET, and plugin build versions
   used for the first successful acceptance run.
4. Use SSH/Codex remote projects for builds and automated tests. Use an unlocked
   Windows desktop session for Rhino/Grasshopper UI work, connector login, and
   publication.

#### 6E. Publish and validate the v3 package

1. Run a narrow connector spike to freeze how ordinary component outputs map to
   Speckle Data Object properties and how the root Snapshot envelope is stored.
   Capture the result as a sanitized fixture and document the exact contract.
2. Build and install the Rangekeeper `.gha`, open the rewritten GHX with the
   associated 3dm, and confirm there are no missing or obsolete components.
3. Recompute without publishing and validate all graph diagnostics and baseline
   counts first.
4. Publish a new version to an explicitly authorized Speckle v3 model using the
   official connector.
5. Receive the published root with Python and update
   `graph.adapter.speckle` only as needed for the frozen v3 envelope.
6. Verify Snapshot round-trip equality, stable entity-to-geometry associations,
   assemblies, relationship counts/types, classifications, labels, features,
   and provenance.

#### 6F. Migrate and execute the walkthroughs

1. Update `load_design.ipynb` to load only the newly published explicit package
   and use Model queries plus the visualization adapter.
2. Add concise assertion cells for the imported structure, relationship counts,
   and `buildingA` traversal.
3. Update `drive_model_from_design.ipynb` to View, Model aggregation,
   Characteristics access, Table/pandas projection, and visualization adapter.
4. Preserve calculations and explanatory flow; replace direct NetworkX access
   with View methods.
5. Remove temporary conversion cells and legacy-source references from both
   notebooks.
6. Execute both notebooks top-to-bottom with local package code and `src/.env`.
7. Compare numerical outputs with every documented regression anchor.

Gate: the Rhino source regenerates and explicitly publishes a supported Speckle
v3 package on Windows; the received package matches the graph baseline and
round-trips through the canonical Snapshot; both notebooks execute successfully
with no Speckle v2 components, legacy graph calls, legacy-source imports, or
conversion code.

### Phase 7: remove legacy implementation

After new code and notebooks work:

1. Remove the temporary Speckle design importer, including
   `_LegacyImporter`, `_LegacyRepresentation`, auto-detection of unversioned
   objects, duplicate old-entity reconciliation, and legacy feature mapping.
2. Remove all `legacy.*` Taxonomy constants and construction.
3. Remove synthetic legacy-import fixtures and tests; retain package round-trip
   and malformed-package tests.
4. Make `graph.adapter.speckle.load()` reject every object that is not an
   explicit supported Rangekeeper package.
5. Remove `rk.api.Speckle.parse()` and `to_rk()`.
6. Remove Entity/Assembly inheritance from Speckle Base.
7. Remove `Kind` and all old naming.
8. Remove public Assembly NetworkX graph ownership and legacy graph mutation.
9. Remove `filter_by_type()`, `get_entities()`, `get_entity()`,
   `get_relatives()`, and old root/leaf methods.
10. Remove graph `to_dict()`/`to_DataFrame()` and visualization methods.
11. Remove heavy visualization/pandas/IPython imports from core graph modules.
12. Update `test_api.py`, `test_graph.py`, exports, README examples, and any
   other references found by `rg`.
13. Do not add compatibility aliases, fallback importers, or deprecation
   wrappers.

Gate: `rg` finds no unintended old API use, `legacy.*` Taxonomies, legacy
Speckle import machinery, or backwards-compatibility paths in source, tests, or
the two required notebooks.

### Phase 8: final verification and commits

1. Run formatting and linting configured by the repository.
2. Run focused graph/materialization/adapter tests.
3. Run all non-live tests.
4. Run C# domain and Grasshopper component tests.
5. Run the Windows Rhino/Grasshopper/Speckle v3 acceptance procedure and retain
   its sanitized result manifest.
6. Run live Python Speckle adapter tests against the newly published package.
7. Execute both notebooks top-to-bottom.
8. Inspect notebook output for errors, warnings, excessive raw output, and
   numerical regressions.
9. Run `git diff --check`.
10. Review the entire diff for unrelated changes and accidental secret/output
   inclusion.
11. Commit in coherent checkpoints. Do not mix the pre-existing user edits into
   a graph commit unless their intent is explicitly adopted and documented.
12. Push only if the user explicitly requests it in the executing task.

## Test plan

### Domain tests

- Classification code validation and immutability.
- Hierarchy parent/child consistency.
- Duplicate code rejection.
- Cycle rejection.
- Record round trip.
- Characteristics default isolation.
- Label type validation.
- Measure/quantity validation retained.
- Features accept rich runtime values.
- Provenance copies identifiers and validates strings.
- Entity ID immutability.
- Entity equality with Entity and unrelated objects.
- Assembly content input copying and default isolation.
- Assembly content properties are read-only.
- Relationship ID immutability and equality.
- Relationship endpoint and classification validation.

### Model tests

- Node key/attribute invariant.
- Edge key/attribute invariant.
- Duplicate entity ID conflict.
- Duplicate relationship ID conflict.
- Dangling endpoint rejection.
- Atomic batch insertion.
- Same Entity in multiple Assemblies.
- Same Relationship in multiple Assemblies.
- Assembly can be a relationship endpoint.
- Assembly relationship endpoint-closure validation.
- Assembly itself may be an endpoint of one of its contained Relationships.
- Nested Assembly traversal terminates.
- Recursive Assembly containment is rejected.
- Atomic addition and removal of Assembly contents.
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
- Assembly entity and relationship references preserved exactly.
- Relationship endpoint reference preservation.
- Classification hierarchy preservation.
- Provenance preservation.
- Labels, measures, features preservation for supported types.
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
- Official v3 root envelope reconstructs the exact Snapshot.
- Geometry Data Object metadata resolves to stable Entity IDs.
- Unsupported feature does not stringify silently.

Legacy import cases are removed in Phase 7. The explicit v3 package, malformed
package, and stable geometry-association tests remain.

## Cross-platform commands

These commands cover the Mac development host. Windows C# build, connector, and
acceptance commands are maintained in
`grasshopper/WINDOWS_DEVELOPMENT.md`.

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
  tests/test_classifications.py \
  tests/test_characteristics.py \
  tests/test_measures.py \
  tests/test_graph.py \
  -q
```

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
6. Assemblies preserve explicit Entity and Relationship sets and support
   overlapping contents without object duplication.
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
18. The rebuilt Rhino/Grasshopper source publishes through the official Speckle
    v3 connector on the pinned Windows acceptance host.
19. The published package reconstructs the canonical Snapshot and preserves the
    expected 50 entities and 63 classified relationships.

## Decisions to make only if implementation forces them

These questions are intentionally deferred and should not block initial work:

- whether relationship Classifications later gain formal cardinality/direction
  metadata;
- whether graph aggregation should support general DAGs and how shared
  descendants are counted;
- whether recursive Assembly containment ever has legitimate meaning;
- whether a future View can be defined by a saved serializable query;
- whether multiple Provenance records are needed for merged data;
- how every rich Rangekeeper financial object should be represented in a full
  Snapshot;
- the exact official-connector property nesting used for the Snapshot envelope;
  freeze it from the Phase 6 Windows spike rather than coupling to connector
  wrapper classes.

Use the simplest behavior documented above until a current test or notebook
demonstrates the need for expansion.
