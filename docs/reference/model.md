# Model authoring, lookup and validation

`Model` owns one complete immutable snapshot of Definitions, System content and
Provenance, plus optional Geometry. It supplies revision-local lookup, authoring and validation. It does
not choose fixed or unknown Values or execute equations. The [three-root
concept](../concepts/model-specification-run.md) explains this boundary; [records](records.md)
and [identity](identity.md) define shared construction and reference rules.

## Ownership and preparation

| Owner | Responsibility |
| --- | --- |
| `model/model.py` | Model facade, construction, UUID lookup, Value and Label lookup by UUID or by owner and key (`Model.value`, `Model.label`), and revision |
| `model/draft.py` | `ModelDraft`, entity handles and value handles: the changes for the next revision and its single commit |
| `schema/index.py` | Schema-directed UUID, type and nearest-owner index with original paths |
| `model/{definitions,provenance}.py` | Catalogue lookup, Facts and upstream Locations |
| `model/{update,diff}.py` | Complete-section replacement and descriptive comparison |
| `model/system/validation.py` | Entity, Assembly, Relationship and membership invariants |
| `model/formulation/` | Located Formulations, owner-local codes and mathematical preparation |
| `model/_scope.py`, `model/expression/` | Declaration lookup and Value content checks over raw mappings, Function signatures and expression analysis |
| `model/targets.py` | Typed lookups of a Reference target: owning Value, units and recorded scalar |
| `model/validation.py` | Public validation report and coordination of domain checks |

The Model builds its `RecordIndex` once and reuses it for lookup, validation and
preparation. The schema-directed walker follows present embedded records and
retains original JSON pointers. It does not follow UUID references or enter
opaque Claim content. Standalone Definitions helpers build an index restricted
to the supplied catalogue; an identity outside that catalogue remains missing.

`Scope` is temporary lookup state. Its mappings and identity set are read-only;
record values are borrowed from a prepared document and are never mutated.
Preparation checks Value content and Function signatures before expression
analysis. It retains each node, inferred domain and source path for predicates
and objectives. Constraint codes are checked once per owning Formulation.
Multiple Constraints can use one expression node. The [expression reference](expressions.md)
defines the limits of this analysis.

Definitions, System and Provenance checks stay with their owners. Model validation
coordinates them and recorded-unit checks. A `UnitSystem` different from the
construction context rechecks recorded units before mathematical preparation is
reused. No cache spans revisions or independent validation operations.

## Make and change a Model

`rk.Model(*, name, namespace=None, description=None)` makes an empty Model: it
has Metadata and no Definitions or System. It takes no unit system and no
timeline. `model.unit_system` reads the unit system in use, the curated registry.

A Model never changes. `model.edit(*, name=None, description=None)` returns a
`ModelDraft`, which collects the changes for the next revision. The draft checks
each call when it is made. `commit()` validates the complete revision once and
returns it, with a new UUID and `previous=model.id`. `name` and `description`
replace those of the new revision; by default it keeps them.

```python
import rangekeeper as rk

model = rk.Model(name="Feasibility")
draft = model.edit()
project = draft.add_entity(code="project", classification="project")
project.value(key="land_cost", units="AUD")
project.value(key="works_cost", units="AUD")
total = project.value(key="total_cost", units="AUD")
project.equations("total_cost = land_cost + works_cost")
model = draft.commit()

draft = model.edit()
project = draft.entity(code="project")
project.value(key="fees", units="AUD")
assert project.ref(key="total_cost").id == total.id
model = draft.commit()
```

| Draft call | Result |
| --- | --- |
| `add_entity(code=, classification=None, name=None)` | An Entity; returns its `EntityHandle` |
| `add_assembly(code=, classification=None, name=None, entities=())` | An Assembly of entities given by code, UUID or handle; returns its handle |
| `add_relationship(source=, target=, classification=)` | A directed Relationship between two entities; returns the record |
| `add_measure(code=, name=, units=, definition=None)` | A Measure; returns the record |
| `add_classification(code=, name=None, parent=None, taxonomy="entity")` | A Classification under `parent` or the Taxonomy root; a missing Taxonomy is made with a root of the same code |
| `entity(id=None, *, code=None, name=None)` | The handle of one Entity or Assembly of the Model or the draft |
| `commit()` | The validated revision |

| Entity handle call | Result |
| --- | --- |
| `value(key=, units=, description=None)` | A measurement Value with no recorded quantity; returns its `ValueHandle` |
| `flow(key=, units=, periods=None, description=None)` | A Flow Value. With `periods`, it has one unresolved Movement in each Period; without, its Periods come from its equations |
| `date(key=, description=None)` | A date Value with no units and no recorded date; returns its `ValueHandle` ([value kinds](#value-kinds)) |
| `ref(key=)` | The handle of a Value of the entity, declared now or in an earlier revision |
| `equations(*equations)` | Adds equations to the entity's default Formulation: [equation text](expressions.md#equation-text), such as `"total_cost = land_cost + works_cost"`, or Boolean Expression records |
| `add_formulation(name=, description=None)` | A named Formulation of the entity, such as `"Funding"`; returns its `FormulationHandle` |
| `formulation(name=)` | The handle of a named Formulation of the entity, made in the draft or in an earlier revision |

A Formulation groups equations for displays and traces; it changes nothing in a
solve, and the values stay on the entity. Its handle's `equations(*equations)`
adds to it, with the rules of `equations` on the entity handle:

```python
draft = model.edit()
project = draft.entity(code="project")
project.value(key="loan", units="AUD")
project.value(key="loan_limit", units="AUD")
funding = project.add_formulation(name="Funding")
funding.equations("loan <= loan_limit")
model = draft.commit()

draft = model.edit()
funding = draft.entity(code="project").formulation(name="Funding")
funding.equations("loan <= total_cost")
```

A `ValueHandle` has the Value's `id`, `key`, `kind` (a `ValueKind`), `owner`
(the UUID of its entity) and declared `units`, or `None` for a date. A
`FormulationHandle` has the Formulation's `id`, `name` and `owner`; two handles
of one Formulation are equal. Only a draft makes handles: `ValueHandle(...)`,
`EntityHandle(...)` and `FormulationHandle(...)` raise `TypeError`. A handle
displays its kind, key, units and entity without UUIDs, such as
`<value land_cost [AUD] on project>`, `<entity project 'Project'>` or
`<formulation 'Funding' on project>`, so a notebook cell that ends with a
declaration shows a short line.

**Rules that each call checks.**

- An entity or Assembly code is unique in the Model, and a Value key is unique
  in its entity. A second declaration raises `ContractError` with code `UNIQUE`.
- A Value key is a Python identifier that is not a keyword or a reserved word of
  equation text (`rx`, `rk`, `NEVER`). Another key raises `ContractError`.
- Units must parse in the unit system of the Model; unknown units raise
  `UnitError` with suggestions. Values share one Measure for each units text: the
  draft uses a Measure with those units, or declares one whose code is the units.
- A classification given by code is found in any Taxonomy. A code that no
  Taxonomy has is declared under the root of the `entity` Taxonomy, or of the
  `relationship` Taxonomy for a Relationship; a code that several Taxonomies
  have raises `AmbiguousReferenceError`.
- An equation is equation text or an Expression record whose root is Boolean:
  an equality, a comparison, a logical operation, a Boolean literal or a call.
  Another Expression record raises `ContractError` with the code `PREDICATE`.
  Text names the keys of its entity, and `code.key` names a key of another
  entity. Every Value or Movement that it references must be in the Model or
  the draft. Text that does not make an equation raises `EquationError` with
  the position of the part that fails, and the call adds no equation
  ([equation text](expressions.md#equation-text)).
- The default Formulation of an entity is the root Formulation whose code is the
  entity's code (or its UUID when it has no code). The draft makes it when the
  entity's first equation or named Formulation is added.
- A named Formulation is a child of the entity's default Formulation, with the
  name as its `name`. Names are unique among the named Formulations of one
  entity: a second `add_formulation` with a name raises `ContractError` with
  code `UNIQUE`. `formulation(name=)` raises `MissingReferenceError` with the
  nearest names when the entity has no Formulation with that name.

A missing entity or key raises `MissingReferenceError` with the nearest codes or
keys. Its `where` names the owner that was searched, such as `"Entity project"`,
or `"ModelDraft"` for the draft. A handle of another draft raises
`ContractError`. A commit with no change raises `RevisionConflictError`. A failed commit
leaves the draft open to correct; after a commit, the draft and its handles raise
`RevisionConflictError` for any change.

With a `namespace` UUID, the Model UUID and every UUID that its drafts make
(entities, values, Movements, Measures, Classifications, Taxonomies,
Relationships, default and named Formulations and Constraints) are derived from the
namespace and the object's code path (UUID version 5), so the same calls make the
same records. Revision UUIDs and the UUIDs inside Expression records are not
derived yet. A revision keeps the namespace of the object it was made from; a
Model read from data has none.

## Records, lookup and revisions

`Model.create` and `Model.from_data` take complete records, for full control:

```python
from uuid import uuid4
from rangekeeper.model import (
    Metadata,
    Model,
    Entity,
    System,
    Definitions,
    Measure,
    Characteristics,
    Value,
    ValueKind,
    Update,
)
from rangekeeper.quantity import Quantity
from rangekeeper.model.diff import between

area = Measure(id=uuid4(), code="area", name="Area", units="sqm")
gross = Value(
    id=uuid4(),
    key="gross",
    kind=ValueKind.MEASUREMENT,
    measure=area.id,
    quantity=Quantity(magnitude=100, units="sqm"),
)
net = Value(id=uuid4(), key="net", kind=ValueKind.MEASUREMENT, measure=area.id)
entity = Entity(
    id=uuid4(), code="A", characteristics=Characteristics(values=(gross, net))
)
model = Model.create(
    metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
    definitions=Definitions(measures=(area,)),
    system=System(entities=(entity,)),
)
assert model.value(id=gross.id).quantity.magnitude == 100
assert model.owner_of(net.id) == entity.id
assert model.value(owner=entity.id, key="net").quantity is None

renamed = Entity(
    id=entity.id, code="Apartment-A", characteristics=entity.characteristics
)
revised = model.revise(Update(system=System(entities=(renamed,))))
assert revised.metadata.previous == model.id
assert model.entity(id=entity.id).code == "A"
assert entity.id in between(model, revised).modified
```

`Model.from_data` copies and validates a complete document. Structure, version,
ownership, references and supported recorded-unit compatibility must pass before
the facade is returned. `create` uses the same path with typed section arguments.
History is not loaded implicitly. `to_data` always exports detached mutable data.

UUID methods `entity`, `assembly`, `relationship`, `value`, `label`, `formulation` and `owner_of` require
actual UUID objects. `Model.movement(id)` looks up a Movement;
`Model.resolve(Reference(target=id))` looks up a Value or Movement in this revision.
A Movement's nearest identified owner is its containing Value. Missing identities raise `MissingReferenceError`; wrong kinds
raise `ReferenceTypeError`. Entity lookup includes Assemblies stored canonically in
`System.assemblies`, without duplicating them into `System.entities`. Values can belong
to Entities, Relationships, Assemblies or nested Formulations. `owner_of` returns the
nearest identified container, or `None` for anonymous root ownership.

`Model.entity` also takes one `code=` or `name=` instead of a UUID, and returns
the one Entity or Assembly that matches. No match raises `MissingReferenceError`
with the nearest codes or names in `candidates`; several matches raise
`AmbiguousReferenceError` ([lookups](errors.md#lookups)).

`find_entities` is a search: it ANDs exact code/name/classification selectors and returns a tuple in
document encounter order. It does not expand classification descendants; use
`Model.descendants(id)` for the sub-types of a Classification, or the inclusive
[View filter](system.md#selection-and-traversal).

`Model.value(owner=, key=)` and `Model.label(owner=, key=)` read one Value or
Label of an Entity, Assembly, Relationship or (for a Value) Formulation by its
exact, case-sensitive key. Generated records are plain data, so the Model reads
them ([ADR-011](../decisions/011-records-and-validation.md)). A missing key
raises `MissingReferenceError` with the owner in `where` and the nearest keys in
`candidates`; `Model.value(id=)` and `Model.label(id=)` still look up by UUID.

`Model.value(key=)` alone reads a Value by the key that names it in the whole
revision, and `Model.key_of(id)` is its inverse: `model.value(key=model.key_of(id))`
is the Value with that UUID. `fix`, `free`, `roles`, `outcome[key]`,
`free_unknowns` and the `unknowns` of a `nonaffine_unknowns` failure use the
same pair.

| `key_of` gives | When |
| --- | --- |
| The key, `"income"` | No other Value of the revision has the key |
| The dotted key, `"building_a.income"` | The owner is the one Entity or Assembly with that code |
| The text of the Value UUID | The owner has no code, or shares it, such as a Relationship or a Formulation |

`key_of` of a Movement gives the key of its Flow Value; another record raises
`ReferenceTypeError`. `value(key=)` takes all three forms. A key that several
Values have raises `AmbiguousReferenceError` with the `key_of` of each in
`candidates`, and a dotted key that names no Value raises
`MissingReferenceError` with `by="path"` ([lookups](errors.md#lookups)).
Catalogue helpers similarly separate UUID lookup from `find_*` searches. They reject duplicate declaration UUIDs across the entire supplied catalogue, even when the requested UUID is unrelated. `Model.assembly` rejects an ordinary Entity. Multiple
Values may share a Measure; Measure identity never chooses a unique Value implicitly.

`Update` replaces complete sections. Omitted sections retain their current content;
explicit empty sections clear content. The candidate is validated before publication
as a new in-memory Model. Deleting a referenced Measure fails without changing the
original Model. No cascading deletion or provenance repair occurs. Descriptive changes
are valid; an identity-only or schema-unordered-reordering-only update is rejected.

Automatic revisions receive a fresh UUID and `previous=current.id`. Explicit metadata
must preserve the schema version, point to the current revision, and not reuse either
the current UUID or its known predecessor. The facade cannot prove global historical
UUID uniqueness without a store; [revision stores](run-and-storage.md) now enforce conflicts.

`between` returns added/removed/modified declaration UUIDs and immutable path changes.
It does not require lineage or produce a patch. Paths refer to canonical comparison
order, while exports retain supplied order. Only schema-unordered collections are
sorted for comparison; mathematical order and every opaque-content list remain intact.
Missing/null/empty, bool/numeric and integer/float representations remain distinct.

## Exact record inspection

`Model.record_at(path: str)` and `Model.record_by_id(id: UUID)` return a frozen
`RecordLocation` from `rangekeeper.schema.index`. It contains `record`,
`owner_id` and `path`. The record is an immutable generated `Record`; its existing
`to_data()`, `field_names()` and `has_field()` APIs retain detached export and
field-presence behavior. `owner_id` is the nearest identified containing record,
or `None`. `path` is the original encounter-order path from the schema walker,
not a path in the sorted comparison representation.

```python
from rangekeeper.schema.index import RecordLocation

location: RecordLocation = model.record_at("/system/entities/0/characteristics")
assert location.owner_id == model.system.entities[0].id
assert model.record_by_id(model.id).path == "/metadata"
assert model.record_at("").owner_id is None
```

The empty path selects the generated Model root. The revision UUID selects its
Metadata record; it does not identify the anonymous root. Path lookup also selects
anonymous records such as Characteristics, Quantity, Location and Method. It
follows only schema-declared embedded record slots. UUID links, scalar fields,
keyed Location addresses and opaque Claim content are not traversed. Nested
PropertyContent records remain selectable through their declared embedded slots.

Use the exact walker path and canonical decimal collection indexes (`0`, `1`,
and so on). Non-string paths and non-UUID identities raise `TypeError`. A nonempty
path without an initial slash, malformed JSON Pointer escapes, or a noncanonical
array index raises `ValueError`. Negative indexes, leading zeros, signs, whitespace,
non-ASCII digits and the append token `-` are not aliases. Missing identities,
fields or indexes and paths into scalar, null, empty, keyed or opaque values raise
`MissingReferenceError`. A collection itself is not a record. An omitted or null
record field is not synthesized; an existing empty record can be selected.

These methods operate on an already fully validated immutable Model. Identity
lookup uses its existing revision-local index with constant lookup work. Path
lookup parses the supplied pointer in work proportional to its length and visits
only the selected embedded chain. It creates at most one borrowed record wrapper
per selected step, without wrapping siblings, walking unrelated records, building
another index or exporting a Model copy. Returning a location does not serialize
its subtree. A later `to_data()` call copies the selected subtree, which can still
be large. Applications retain responsibility for request and response limits.
Locations from an earlier Model keep that earlier revision's content after
`revise`; no lookup loads history or crosses into another Model.

## Value kinds

A Value's `kind` decides which content fields it can have. Absent content is
unresolved; a Specification fixes it or a solve finds it.

| `ValueKind` | Measure | Content |
| --- | --- | --- |
| `MEASUREMENT` | Required | `quantity`, in units compatible with the Measure |
| `FLOW` | Required | `flow`: dated Movements |
| `DATE` | None | `date`, a calendar date, or `never`, `rk.duration.NEVER`; not both |
| `PROPERTY` | None | `content`: inert typed data ([property content](#property-content)) |

A date Value with neither `date` nor `never` is unresolved; it is not NEVER.
Validation rejects a date Value with a Measure, a quantity, a Flow or property
content, and date content on any other kind. Equations compare date Values and
add calendar lengths to them ([dates and NEVER](expressions.md#dates-and-never)).

```python
from datetime import date
from uuid import uuid4

import rangekeeper as rk
from rangekeeper.model import Value, ValueKind

start = Value(id=uuid4(), key="start_date", kind=ValueKind.DATE, date=date(2027, 1, 1))
b_start = Value(id=uuid4(), key="b_start", kind=ValueKind.DATE, never=rk.duration.NEVER)
```

## Property content

`model.content.encode` and `decode` retain typed property data separately from
measurement quantities and Flow content. Supported content includes null, bool,
int, finite float, str, UUID, date, datetime, time, timedelta, list, tuple, set,
frozenset, dict and MappingProxyType, recursively. Lists, tuples, mapping order,
timezone/fold and negative zero retain their meaning. `decode` returns detached
data. Arbitrary classes, callbacks, cycles and nonfinite numbers fail.

A property timestamp does not become a Flow coordinate. A Pint object inside
legacy Feature content requires an explicit mapping; the one-off conversion tool
(`python -m tools.upgrade`, see [upgrading](../guides/upgrading.md)) reports
unsupported content rather than changing its type.

## Validation reports and failures

`model.validate(units=...)` and `model.check(units=...)` check a revision against
another unit system ([validate and check](records.md#validate-and-check-a-document)).
`model.validation.validate` accepts a facade, generated Model record or serialized
mapping and returns a `ValidationReport`. Shared argument guards reject invalid
Python arguments with `TypeError` or `ValueError`. They do not inspect documents.
Shared invariants report `ContractError` with a code from `rangekeeper.errors.Code`,
a JSON pointer where available, and structured targets, values and evidence. See
[errors and diagnostics](errors.md). `Issue` and `ValidationReport` live in
`shared.diagnostics`; errors live in `shared.errors`. None of these shared helpers
imports Model, Specification, Run or IO behavior.

Bounded dependent checks report the first semantic error in a stage and skip that
stage after a prerequisite failure. Structural and unit checks can collect several
issues. Some semantic checks still use `semantic.contract` without a detailed
path. A report is not a promise of exhaustive error collection. Programming errors
are not converted to invalid-document findings. See the [validation development
procedure](../contributing/verification.md) for checks and evidence limits.

## Units and limits

A Model validates its recorded units with its unit system. `Model.unit_system`
returns that system, and derived operations use it by default. The
[units reference](units.md) gives the curated registry, its errors and
suggestions, and the operations that use `Model.unit_system`. Every catalogue
currency has an independent dimension: AUD and USD are incompatible, with no
exchange inference.

Supported recorded units are checked in Model and Specification-local mathematics.
Equation unit inference, generic Fact/Claim-content agreement, imposed graph-query
evaluation, numerical feasibility and independent solution acceptance remain outside
the bounded validators. See [execution](execution.md) for numerical acceptance
and [source interpretation](../concepts/source-workflows.md) for source-to-Claim
responsibilities.

## Geometry

The optional provider-neutral Geometry field records exact native content and
Entity/Assembly mappings. See the [Bundle contract](bundle.md) for ownership,
validation and identity. Canonical source
provenance remains Source/Location/Claim/Fact, independently of these mappings.
