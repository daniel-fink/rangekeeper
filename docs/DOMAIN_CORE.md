# Model and Specification operations

Model owns lookup and revision over canonical records. Specification owns partial requirements; composition combines contributions without solving. See [record methods](RECORD_BOUNDARY.md).

## Factoring and documentation

Public methods have docstrings describing meaning, errors and side effects. Inline
comments explain the rules that are easy to break: opaque content is not a declaration,
partial contributions can retain external references, metadata identity changes alone
are not a meaningful revision, and unordered schema collections differ from ordered
mathematics. Generated records remain the only Python field definitions.

| Module | Implemented responsibility |
| --- | --- |
| `model/model.py`, `schema/index.py` | Immutable Model facade; schema-directed revision-local UUID/type/owner indexes with original declaration paths. |
| `model/{entity,assembly,relationship,measure}.py`, `model/{system,expression,formulation}/`, `schema/` | Explicit aliases of generated nested records, without handwritten field copies. |
| `model/{characteristics,definitions,provenance}.py` | Owner-local Value/Label lookup; catalogue UUID lookup versus code search; Fact and upstream Location traversal. |
| `model/{update,diff}.py`, `schema/runtime.py`, `schema/revision.py` | Atomic complete-section replacement and descriptive comparison, using generated ordering metadata. |
| `shared/units.py`, `model/validation.py` | Private lazy Pint registry, declared py-moneyed currency catalogue and shared checks for declared/recorded units. |
| `specification/specification.py` | Immutable locally valid saved contribution or batch. |
| `specification/composition.py` | Immutable effective requirements, contributor identities/snapshots and source paths. |
| `specification/validation.py`, `shared/references.py` | Complete investigation validation against an injected read-only resolver. |

Model owns its revision-local index. Lookup, diff and internal preparation reuse
that index. Standalone Definitions helpers build a catalogue-scoped index, so a
UUID outside the supplied catalogue remains missing. The generic index walker uses generated slot metadata and present-field order,
visiting only embedded records. It does not follow UUID references or inspect opaque
Claim content. Domain behavior imports neither legacy Graph nor storage/solver modules.

## Composable validation

The 2026-10-02 [validation refactor](research/domain-migration/validation-refactor/README.md)
separates reusable invariants from domain rules while preserving the existing
acceptance/rejection contract.

| Module | Responsibility and operations |
| --- | --- |
| `shared/arguments.py` | Python argument guards: `require_uuid`, `require_text`, `require_code`. Invalid caller arguments raise `TypeError`/`ValueError`; these functions do not inspect documents. |
| `shared/validation.py` | Domain-independent `require`, `require_unique`, `require_acyclic`, `require_ownership`; single record preparation via `checked_record` and its mapping boundary `checked` and prerequisite gating/report conversion via `bounded`. |
| `model/formulation/` | Owner-local naming rules, ordered declaration locations and `prepare_formulations`, which returns Scope, ExpressionAnalysis and located Formulations. |
| `model/scope.py`, `model/expression/` | UUID-keyed declaration and target lookup; separate content/signature checks; one expression analysis; directional domain comparison and predicate checks. |
| `{model,specification,run}/validation.py` | Public report-returning orchestration; domain-specific rules remain in their owning packages. |
| `shared/diagnostics.py`, `shared/errors.py` | `Issue`, `ValidationReport`, and `ContractError` with optional rule code and JSON Pointer. |

`Scope` contains lookup data only. Its tables and identity set are read-only, but
record values are borrowed from a prepared envelope: it is temporary analysis state,
not a new immutable document type. Functions do not mutate the supplied records.
`build_scope` indexes declarations. The coordinator then checks Value content and
Function signatures before expression analysis. Analysis retains each node, inferred
domain and original path; predicates and objectives reuse those results. No field schema
is handwritten here, and these checks remain bounded domain analysis, not execution.

Constraint codes are checked once per owning Formulation. Predicate validation
operates over the combined UUID scope, allowing multiple Constraints to refer to a
single expression node. There is no `check_codes` switch. Conformance expression
fixtures explicitly check their single code collection before predicate validation.

Generic helpers do not import Model, Specification, Run, or IO behavior. Domain
packages import them directly; errors are imported from `shared/errors.py`. Argument guards
retain their existing runtime behavior; `is_text` now supplies a `TypeGuard[str]`
annotation so static checking understands the returned value type.

The extracted invariants and predicate checks retain specific issue codes and paths.
Formulation and combined Entity/Assembly checks retain their original canonical
Model locations. Some older domain checks still use `semantic.contract` without
a detailed path. `bounded` reports the first semantic error within a dependent stage
and skips the stage if structural/prerequisite issues already exist. Existing
structural and unit checks can collect multiple issues; this refactor does not claim
exhaustive semantic error collection. Programming exceptions are never converted to
ordinary invalid-document reports.

`require_declarations` uses schema-directed traversal, so opaque Claim content never
becomes a declaration. Model checks use the existing index when available. The narrow
`require_ownership` helper remains for explicit conformance envelopes and treats `id`
as a declaration; its callers must provide only declaration data. Partial Specification
validation permits unresolved external inputs; complete composition validation
requires the pinned Model.

Definitions, System and Provenance checks live with those domain owners. Model
validation coordinates them and recorded-unit checks. A requested UnitSystem that
differs from the Model's construction context rechecks the recorded units before
reusing mathematical preparation.

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
UUID uniqueness without a store; [revision stores](RUN_AND_STORAGE.md) now enforce conflicts.

`between` returns added/removed/modified declaration UUIDs and immutable path changes.
It does not require lineage or produce a patch. Paths refer to canonical comparison
order, while exports retain supplied order. Only schema-unordered collections are
sorted for comparison; mathematical order and every opaque-content list remain intact.
Missing/null/empty, bool/numeric and integer/float representations remain distinct.

## Contributions, composition and validation

The Specification facade contains a generated `SpecificationRecord`. `.id` and
`.metadata` expose revision identity; `.record` supplies typed access to every schema
field without another handwritten field facade. `from_data` validates local ownership,
known local reference kinds, duplicate requirements, roles, settings and header rules.
External references and incomplete solve roles are permitted in a saved contribution.

```python
from rangekeeper.shared.errors import MissingReferenceError
from rangekeeper.specification import Specification, SpecificationRecord
from rangekeeper.model.expression import Reference

shared = Specification(SpecificationRecord(
    metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
    model=model.id, unknowns=(Reference(target=gross.id),),
))
investigation = Specification(SpecificationRecord(
    metadata=Metadata(id=uuid4(), schema_version="0.7.0"), includes=(shared.id,),
))

class Inputs:
    # A read-only dependency supplied by the caller; no store implementation needed.
    def load_model(self, id):
        if id != model.id:
            raise MissingReferenceError(str(id))
        return model

    def load_specification(self, id):
        if id != shared.id:
            raise MissingReferenceError(str(id))
        return shared

composition = investigation.compose(resolver=Inputs())
assert composition.sources[("unknowns", str(gross.id))].document_id == shared.id
composition.validate(resolver=Inputs()).raise_if_invalid()
```

This example validates a request; it does not solve an equation. Recorded Values do
not become permanent assignments. A later investigation can assign or solve the same
Value differently while referring to the same pinned Model.

`Specification.compose` resolves each revision once. Diamond includes contribute once; independent
duplicate requirements conflict even if equal. Model pins must agree. Ordered objectives
belong to one contributor and retain order. Batches are locally valid saved records but
cannot be included or flattened into one Composition. Missing/wrong-kind/wrong-identity
resolver results and include/case cycles fail explicitly.

A Composition exposes derived `root_id` and `model_id`, immutable generated
`requirements`, exact contributor snapshots in `contributors`, and derived
`contributor_ids`. Its read-only `sources` map contains `Source(document_id, path)`
values with original document pointers. It is not a saved revision and creates no UUID.

`composition.validate(resolver=..., units=...)` checks the existing view directly.
It does not export and recompose contributors. Internal preparation retains the
exact resolved Model, combined Scope and ExpressionAnalysis for execution.
Independent public calls establish fresh resolver and unit contexts. Invalid
mathematics does not erase a successfully composed Model pin.

`validate_records` is the raw catalogue entry point. It still checks supplied extra
records and gates semantic work after structural errors. Partial construction does
not resolve external references; intrinsic settings checks include
`0 < relative_tolerance < 1` when supplied.
Model validation still accepts a facade, generated record or serialized mapping.

`Specification.revise` requires a complete generated replacement with explicit new
identity/lineage and a meaningful content change. It does not inherit requirements or
resolve includes. A saved contribution is distinct from its effective Composition.

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
the bounded validators. Nothing has executed the synthetic valuation Runs.
