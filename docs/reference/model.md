# Model authoring, lookup and validation

`Model` owns one complete immutable snapshot of Definitions, System content and
Provenance. It supplies revision-local lookup, authoring and validation. It does
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
from rangekeeper.model import (
    Model, Entity, System, Definitions, Measure, Quantity,
    Characteristics, Value, ValueKind, Update,
)
from rangekeeper.model import characteristics
from rangekeeper.model.diff import between

area = Measure(id=uuid4(), code="area", name="Area", units="squaremeter")
gross = Value(id=uuid4(), key="gross", kind=ValueKind.MEASUREMENT, measure=area.id,
              quantity=Quantity(magnitude=100, units="squaremeter"))
net = Value(id=uuid4(), key="net", kind=ValueKind.MEASUREMENT, measure=area.id)
entity = Entity(id=uuid4(), code="A", characteristics=Characteristics(values=(gross, net)))
model = Model.create(
    metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
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
document encounter order. It does not expand classification descendants. Local
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
Shared invariants report `ContractError` with a rule code and JSON pointer where
available. `Issue` and `ValidationReport` live in `shared.diagnostics`; errors live
in `shared.errors`. None of these shared helpers imports Model, Specification,
Run or IO behavior.

Bounded dependent checks report the first semantic error in a stage and skip that
stage after a prerequisite failure. Structural and unit checks can collect several
issues. Some semantic checks still use `semantic.contract` without a detailed
path. A report is not a promise of exhaustive error collection. Programming errors
are not converted to invalid-document findings. See the [validation development
procedure](../contributing/verification.md) for checks and evidence limits.

## Units and limits

`UnitSystem.compatible(left, right)` checks dimensions, not equal scale.
`convert(quantity, to=...)` returns a new finite Quantity. Invalid/unknown units and
incompatible conversions raise `UnitError`. The configuration is immutable; the registry
is private and imported lazily. Standard physical units and squaremeter/squarefoot
aliases are supported. Dwelling is an independent count dimension. Every catalogue currency
has an independent dimension: AUD and USD are incompatible, with no exchange inference.

Currency codes come directly from the declared py-moneyed dependency, including
historical codes. This is not a claim that each code is currently in circulation.
`UnitSystem.validate_units(text)` parses one spelling without comparing it to itself. Importing domain APIs does not import
Pint; actual unit operations require the already-declared Pint runtime dependency.

Supported recorded units are checked in Model and Specification-local mathematics.
Equation unit inference, generic Fact/Claim-content agreement, imposed graph-query
evaluation, numerical feasibility and independent solution acceptance remain outside
the bounded validators. See [execution](execution.md) for numerical acceptance
and [workflow evidence](evidence.md) for source cell-to-Claim agreement.
