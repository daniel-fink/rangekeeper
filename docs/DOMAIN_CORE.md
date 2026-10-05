# Model and Specification APIs — Turn 2

**Flow semantics update, 2026-10-06:** Flows no longer carry semantic kinds or
basis. The overall model logic owns their meaning and selects operations; units,
dates, alignment and missingness remain checked. See the
[current contract](FULL_MIGRATION_TURN1.md#flow-semantics-and-explicit-operations)
and [verification](research/full-migration/flow-semantics/README.md).

Implemented 2026-10-02: work units **3A and 3B** from the
[migration map](DOMAIN_MIGRATION_MAP.md). The [record boundary](RECORD_BOUNDARY.md)
remains the field authority. Public imports now live in `rangekeeper.model` and
`rangekeeper.specification`; root aliases, the Run facade, codecs and stores
are now implemented in [Turn 3](RUN_AND_STORAGE.md). Graph consumers and execution have not been migrated.

## Factoring and documentation

Public methods have docstrings describing meaning, errors and side effects. Inline
comments explain the rules that are easy to break: opaque content is not a declaration,
partial contributions can retain external references, metadata identity changes alone
are not a meaningful revision, and unordered schema collections differ from ordered
mathematics. Generated records remain the only Python field definitions.

| Module | Implemented responsibility |
| --- | --- |
| `model/model.py`, `model/_index.py` | Immutable Model facade; schema-directed revision-local UUID/type/owner indexes. |
| `model/{entity,assembly,relationship,system,measure,expression,formulation}.py`, `metadata.py` | Explicit aliases of generated nested records, without handwritten field copies. |
| `model/{characteristics,definitions,provenance}.py` | Owner-local Value/Label lookup; catalogue UUID lookup versus code search; Fact and upstream Location traversal. |
| `model/{update,diff}.py`, `_comparison.py` | Atomic complete-section replacement and descriptive comparison, using generated ordering metadata. |
| `units.py`, `_currencies.json`, `model/_unit_validation.py` | Private lazy Pint registry, pinned currency catalogue and shared checks for declared/recorded units. |
| `specification/specification.py` | Immutable locally valid saved contribution or batch. |
| `specification/composition.py` | Immutable effective requirements, contributor identities/snapshots and source paths. |
| `specification/validation.py`, `references.py` | Complete investigation validation against an injected read-only resolver. |

Model owns the private index. Other public operations use its lookup methods or build
their own derived comparison data; they do not reach into another facade's private
state. The generic index walker uses generated slot metadata and present-field order,
visiting only embedded records. It does not follow UUID references or inspect opaque
Claim content. Domain behavior imports neither legacy Graph nor storage/solver modules.

## Composable validation

The 2026-10-02 [validation refactor](research/domain-migration/validation-refactor/README.md)
separates reusable invariants from domain rules while preserving the existing
acceptance/rejection contract. It is implemented before Turn 3.

| Module | Responsibility and operations |
| --- | --- |
| `validate.py` | Python argument guards: `require_uuid`, `require_text`, `require_code`. Invalid caller arguments raise `TypeError`/`ValueError`; these functions do not inspect documents. |
| `_validation.py` | Domain-independent `require`, `require_unique`, `require_acyclic`, `require_ownership`; structural preparation via `checked` and prerequisite gating/report conversion via `bounded`. |
| `model/_formulation.py` | `validate_formulation_names` is shared by complete Model and partial Specification checks. `validate_formulations` composes local naming, ownership, binding and mathematical checks. |
| `model/_expression.py` | `build_scope` builds lookup tables; `validate_function_signature`, `validate_domain_references`, `infer_expression_domain`, `infer_query_domain`, `matches_domain` and `validate_constraint_predicates` consume an explicit `scope`. |
| `{model,specification,run}/validation.py` | Public report-returning orchestration; domain-specific rules remain in their owning packages. |
| `diagnostics.py`, `errors.py` | `Issue`, `ValidationReport`, and `ContractError` with optional rule code and JSON Pointer. |

`Scope` contains lookup data only. Its tables and identity set are read-only, but
record values are borrowed from a prepared envelope: it is temporary analysis state,
not a new immutable document type. Functions do not mutate the supplied records.
The signature check is an explicit part of `build_scope`; individual signature and
expression checks can also be called with a previously built scope. No field schema
is handwritten here, and these checks remain bounded domain analysis, not execution.

Constraint codes are checked once per owning Formulation. Predicate validation
operates over the combined UUID scope, allowing multiple Constraints to refer to a
single expression node. There is no `check_codes` switch. Conformance expression
fixtures explicitly check their single code collection before predicate validation.

Generic helpers do not import Model, Specification, Run, or IO behavior. Domain
packages import them directly; errors are imported from `errors.py`. Argument guards
retain their existing runtime behavior; `is_text` now supplies a `TypeGuard[str]`
annotation so static checking understands the returned value type.

The extracted invariants and predicate checks retain specific issue codes and paths.
Formulation and combined Entity/Assembly positions are mapped back to canonical
Model storage paths. Some older domain checks still use `semantic.contract` without
a detailed path. `bounded` reports the first semantic error within a dependent stage
and skips the stage if structural/prerequisite issues already exist. Existing
structural and unit checks can collect multiple issues; this refactor does not claim
exhaustive semantic error collection. Programming exceptions are never converted to
ordinary invalid-document reports.

`require_ownership` operates on prepared dict/list envelopes and treats `id` as a
declaration. Callers must exclude opaque content first. The Model adapter retains
canonical containment for diagnostics while excluding `Claim.content`. The generated
record walker remains responsible for typed record traversal. Partial Specification
validation still permits unresolved external inputs; complete composition validation
still requires the pinned Model.

## Authoring, lookup and revisions

```python
from uuid import uuid4
from rangekeeper.metadata import Metadata
from rangekeeper.model import (
    Model, Entity, System, Definitions, Measure, Quantity,
    Characteristics, Value, Update,
)
from rangekeeper.model import characteristics
from rangekeeper.model.diff import between

area = Measure(id=uuid4(), code="area", name="Area", units="squaremeter")
gross = Value(id=uuid4(), key="gross", kind="measurement", measure=area.id,
              quantity=Quantity(magnitude=100, units="squaremeter"))
net = Value(id=uuid4(), key="net", kind="measurement", measure=area.id)
entity = Entity(id=uuid4(), code="A", characteristics=Characteristics(values=(gross, net)))
model = Model.create(
    metadata=Metadata(id=uuid4(), schema_version="0.4.0"),
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

UUID methods `entity`, `relationship`, `value`, `formulation` and `owner_of` require
actual UUID objects. Missing identities raise `MissingReferenceError`; wrong kinds
raise `ReferenceTypeError`. Entity lookup includes Assemblies stored canonically in
`System.assemblies`, without duplicating them into `System.entities`. Values can belong
to Entities, Relationships, Assemblies or nested Formulations. `owner_of` returns the
nearest identified container, or `None` for anonymous root ownership.

`find_entities` ANDs exact code/name/classification selectors and returns a tuple in
document encounter order. It does not expand classification descendants. Local
Characteristics lookup is case-sensitive and returns `None` for an absent key/container.
Catalogue helpers similarly separate UUID lookup from `find_*` searches. Multiple
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
from rangekeeper.errors import MissingReferenceError
from rangekeeper.specification import Specification, SpecificationRecord, compose, validate

shared = Specification(SpecificationRecord(
    metadata=Metadata(id=uuid4(), schema_version="0.4.0"),
    model=model.id, unknowns=(gross.id,),
))
investigation = Specification(SpecificationRecord(
    metadata=Metadata(id=uuid4(), schema_version="0.4.0"), includes=(shared.id,),
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

composition = compose(investigation, resolver=Inputs())
assert composition.sources[("unknowns", str(gross.id))] == shared.id
validate(composition, resolver=Inputs()).raise_if_invalid()
```

This example validates a request; it does not solve an equation. Recorded Values do
not become permanent assignments. A later investigation can assign or solve the same
Value differently while referring to the same pinned Model.

`compose` resolves each revision once. Diamond includes contribute once; independent
duplicate requirements conflict even if equal. Model pins must agree. Ordered objectives
belong to one contributor and retain order. Batches are locally valid saved records but
cannot be included or flattened into one Composition. Missing/wrong-kind/wrong-identity
resolver results and include/case cycles fail explicitly.

A Composition exposes `root_id`, optional `model_id`, contributor UUIDs, immutable
generated `requirements`, and a read-only `sources` map of semantic paths to contributor
UUIDs. `contributions` retains the exact immutable Specification snapshots for validation
and inspection. This is derived state with the root's existing metadata, not a new saved
Specification or an IO format. No UUID is minted during composition.

`specification.validate(composition, resolver=..., units=...)` checks completeness and
cross-document semantics against the exact Model pin. Resolution failures become
`ValidationReport` issues. `validate_records` is the explicitly lower-level catalogue
entrypoint from Turn 1, renamed to distinguish it from the public Composition operation.
Model validation still accepts a facade, generated record or serialized mapping.

`Specification.revise` requires a complete generated replacement with explicit new
identity/lineage and a meaningful content change. It does not inherit requirements or
resolve includes. A saved contribution is distinct from its effective Composition.

## Units and limits

`UnitSystem.compatible(left, right)` checks dimensions, not equal scale.
`convert(quantity, to=...)` returns a new finite Quantity. Invalid/unknown units and
incompatible conversions raise `UnitError`. The configuration is immutable; the registry
is private and imported lazily. Standard physical units and squaremeter/squarefoot
aliases are supported. Dwelling is an independent count dimension. Every bundled currency
has an independent dimension: AUD and USD are incompatible, with no exchange inference.

The bundled catalogue records 308 py-moneyed 3.0 codes, including historical codes;
it is not a claim that every code is currently in circulation. Pint 0.24.4 was tested.
The old `measure.Index.registry` is untouched. Importing domain APIs does not import
Pint; actual unit operations require the already-declared Pint runtime dependency.

Supported recorded units are checked in Model and Specification-local mathematics.
Equation unit inference, generic Fact/Claim-content agreement, imposed graph-query
evaluation, numerical feasibility and independent solution acceptance remain outside
the bounded validators. Nothing has executed the synthetic valuation Runs.

## Verification and continuation

See [Turn 2 evidence](research/domain-migration/turn2/README.md) for commands, environments,
tests and limits. Existing Graph/numerical consumers remain unchanged. Run factories,
strict JSON/YAML codecs, revision stores, root exports and installed-core acceptance
are now implemented in [Turn 3](RUN_AND_STORAGE.md) (work units 3C and 4). Execution and
consumer retirement remain later checkpoints. No commit, push or release was performed.
