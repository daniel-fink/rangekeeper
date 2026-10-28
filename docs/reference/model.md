# Model authoring, lookup and validation

`Model` owns one complete immutable snapshot of Definitions, System content and
Provenance, plus optional Geometry. It supplies revision-local lookup, authoring and validation. It does
not choose fixed or unknown Values or execute equations. The [three-root
concept](../concepts/model-specification-run.md) explains this boundary; [records](records.md)
and [identity](identity.md) define shared construction and reference rules.

## Ownership and preparation

| Owner | Responsibility |
| --- | --- |
| `model/model.py` | Model facade, construction, UUID lookup and revision |
| `schema/index.py` | Schema-directed UUID, type and nearest-owner index with original paths |
| `model/{characteristics,definitions,provenance}.py` | Owner-local Value/Label lookup, catalogue lookup, Facts and upstream Locations |
| `model/{update,diff}.py` | Complete-section replacement and descriptive comparison |
| `model/system/validation.py` | Entity, Assembly, Relationship and membership invariants |
| `model/formulation/` | Located Formulations, owner-local codes and mathematical preparation |
| `model/scope.py`, `model/expression/` | Declaration/target lookup, Value content, Function signatures and expression analysis |
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

## Authoring, lookup and revisions

```python
from uuid import uuid4
from rangekeeper.schema import Metadata
from rangekeeper.model import Model, Entity, System, Definitions, Measure, Characteristics, Value, ValueKind, Update
from rangekeeper.quantity import Quantity
from rangekeeper.model import characteristics
from rangekeeper.model.diff import between

area = Measure(id=uuid4(), code="area", name="Area", units="sqm")
gross = Value(id=uuid4(), key="gross", kind=ValueKind.MEASUREMENT, measure=area.id,
              quantity=Quantity(magnitude=100, units="sqm"))
net = Value(id=uuid4(), key="net", kind=ValueKind.MEASUREMENT, measure=area.id)
entity = Entity(id=uuid4(), code="A", characteristics=Characteristics(values=(gross, net)))
model = Model.create(
    metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
    definitions=Definitions(measures=(area,)), system=System(entities=(entity,)),
)
assert model.value(gross.id).quantity.magnitude == 100
assert model.owner_of(net.id) == entity.id
assert characteristics.value(model.entity(entity.id).characteristics, "net").quantity is None

renamed = Entity(id=entity.id, code="Apartment-A", characteristics=entity.characteristics)
revised = model.revise(Update(system=System(entities=(renamed,))))
assert revised.metadata.previous == model.id
assert model.entity(entity.id).code == "A"
assert entity.id in between(model, revised).modified
```

`Model.from_data` copies and validates a complete document. Structure, version,
ownership, references and supported recorded-unit compatibility must pass before
the facade is returned. `create` uses the same path with typed section arguments.
History is not loaded implicitly. `to_data` always exports detached mutable data.

UUID methods `entity`, `assembly`, `relationship`, `value`, `formulation` and `owner_of` require
actual UUID objects. `Model.movement(id)` looks up a Movement;
`Model.resolve(Reference(target=id))` looks up a Value or Movement in this revision.
A Movement's nearest identified owner is its containing Value. Missing identities raise `MissingReferenceError`; wrong kinds
raise `ReferenceTypeError`. Entity lookup includes Assemblies stored canonically in
`System.assemblies`, without duplicating them into `System.entities`. Values can belong
to Entities, Relationships, Assemblies or nested Formulations. `owner_of` returns the
nearest identified container, or `None` for anonymous root ownership.

`find_entities` ANDs exact code/name/classification selectors and returns a tuple in
document encounter order. It does not expand classification descendants; use
`Model.descendants(id)` for the sub-types of a Classification, or the inclusive
[View filter](system.md#selection-and-traversal). Local
Characteristics lookup is case-sensitive and returns `None` for an absent key/container.
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

## Property content

`model.content.encode` and `decode` retain typed property data separately from
measurement quantities and Flow content. Supported content includes null, bool,
int, finite float, str, UUID, date, datetime, time, timedelta, list, tuple, set,
frozenset, dict and MappingProxyType, recursively. Lists, tuples, mapping order,
timezone/fold and negative zero retain their meaning. `decode` returns detached
data. Arbitrary classes, callbacks, cycles and nonfinite numbers fail.

A property timestamp does not become a Flow coordinate. A Pint object inside
legacy Feature content requires an explicit mapping; the migration converter
reports unsupported content rather than changing its type.

## Validation reports and failures

`model.validation.validate` accepts a facade, generated Model record or serialized
mapping and returns a `ValidationReport`. Shared argument guards reject invalid
Python arguments with `TypeError` or `ValueError`. They do not inspect documents.
Shared invariants report `ContractError` with a code from `rangekeeper.errors.Code`,
a JSON pointer where available, and structured targets, values and evidence. See
[diagnostics and codes](errors.md). `Issue` and `ValidationReport` live in
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
