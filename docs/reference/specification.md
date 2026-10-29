# Specification contributions, composition and validation

A `Specification` records an investigation against one exact input Model revision.
It can declare assignments, unknowns, estimates, bounds, objectives and rules.
Saved partial contributions and batches are valid document shapes;
an effective leaf investigation is a derived `Composition`. Composition does not
solve equations or change its contributors.

Use the [three-root concept](../concepts/model-specification-run.md) for the reasons for this
boundary, [identity](identity.md) for reference scope, and [execution](execution.md)
for the supported numerical subset.

## Ownership

| Owner | Responsibility |
| --- | --- |
| `specification/specification.py` | Immutable saved contribution/batch, local checks and explicit revision |
| `specification/composition.py` | Additive requirements, exact contributor snapshots and original source locations |
| `specification/validation.py` | Complete investigation validation using a supplied read-only resolver |
| `specification/targets.py` | Explicit expansion of Flow assignments and unknown roles |
| `specification/rule/` | Dated declarations, causal observation and independent evidence validation |
| `shared/references.py` | Resolver protocols without a storage dependency |

## Contributions, composition and validation

The Specification facade contains a generated `SpecificationRecord`. `.id` and
`.metadata` expose revision identity; `.record` supplies typed access to every schema
field without another handwritten field facade. `from_data` validates local ownership,
known local reference kinds, duplicate requirements, roles, settings and header rules.
External references and incomplete solve roles are permitted in a saved contribution.

The short example below uses `model` and `gross` from the
[Model authoring example](model.md#records-lookup-and-revisions).

```python
from uuid import uuid4
from rangekeeper.errors import MissingReferenceError
from rangekeeper.model import Metadata, Reference
from rangekeeper.specification import Specification, SpecificationRecord

shared = Specification(
    SpecificationRecord(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        model=model.id,
        unknowns=(Reference(target=gross.id),),
    )
)
investigation = Specification(
    SpecificationRecord(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        includes=(shared.id,),
    )
)


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

`specification.validate(resolver=...)` and `specification.check(resolver=...)`
compose every concrete case and check each one
([validate and check](records.md#validate-and-check-a-document)).
`composition.validate(resolver=..., units=None)` checks the existing view directly.
Without `units`, it uses the [unit system](units.md) of the input Model.
It does not export and recompose contributors. Internal preparation retains the
exact resolved Model, combined Scope and ExpressionAnalysis for execution.
Independent public calls establish fresh resolver and unit contexts. Invalid
mathematics does not erase a successfully composed Model pin.

`validate_records` is the raw catalogue entry point. It still checks supplied extra
records and gates semantic work after structural errors. Partial construction does
not resolve external references; intrinsic settings checks include
`0 < relative_tolerance < 1` when supplied.

`Specification.revise` requires a complete generated replacement with explicit new
identity/lineage and a meaningful content change. It does not inherit requirements or
resolve includes. A saved contribution is distinct from its effective Composition.

## Roles and unit context

`Reference(target=uuid)` selects a Value or Movement in the composed scope.
`assign_flow(model, value, ids=...)` explicitly copies resolved amounts into
assignments; `unknown_flow(model, value, ids=...)` declares selected Movements
unknown. Omitting `ids` selects all entries. Recorded quantities and estimates
never supply omitted assignments. A Measure identifies meaning, not a unique
Value. Duplicate or conflicting roles fail.

Composition permits one rule set contribution. Its controls cannot also be assigned
or unknown, and rule evidence must follow the declared information availability.
See [rules](market-paths-and-rules.md#rule-declarations-and-evidence).

Pass the caller's `UnitSystem` through validation and execution. Public validation
uses explicit compatibility checks; raw conformance entrypoints retain their
strict spelling defaults unless a unit adapter is supplied. The [Model unit
contract](model.md#units-and-limits) owns conversion and currency rules.

Complete validation prepares the exact resolved Model, combined Scope and
ExpressionAnalysis once for that operation. It checks declaration ownership,
references, domains and solve roles. It does not execute queries, certify numerical
feasibility or establish backend support. A structurally valid objective or
Function can still be unsupported by the selected executor.

## Fix and free quantities

`model.specify(*, name=None, description=None)` returns a new Specification of
that Model revision. Its Metadata has a new UUID, the schema version, the name
and the description. Each chained call returns a new Specification; the
Specification that it is called on does not change. The new Metadata has a new
UUID and `previous=specification.id`, and keeps the name and description. No
call saves or executes the revision. `model_id` is the UUID of the pinned Model
revision.

A value that is not fixed is free: the solve finds it. `specify` and each chained
call record as unknowns the Values and Movements that the equations use and that
no fix or rule controls. The equations are the Constraints of the Model and of
the Specification's own Formulations. A record that you make yourself has only
the roles that it declares, until a chained call adds the free values.

```python
front = (
    model.specify(name="Front door")
    .fix(land_cost="20e6 AUD", works_cost=works)
    .fix(leverage="65 %", coverage=1.25)
)
back = front.fix(rent_factor=1).free("land_cost")
back.roles  # each value: fixed with its Quantity, free or decided
```

`fix(**values)` fixes each named value, and `free(*targets)` releases a value
that was fixed before. A fix or free replaces an earlier fix or free of the same
target in this Specification. `fix` also removes the estimate of its target;
`free` keeps it. Both retain the equations and unrelated Specification content.
When no role changes, such as a free of a free value, the call returns the same
Specification, with its estimates.

| Target | Meaning |
| --- | --- |
| A key, `fix(land_cost=...)` or `free("land_cost")` | The one Value of the Model with that key. Several Values with the key raise `AmbiguousReferenceError`; its `candidates` are the key of each, as `Model.key_of` gives it |
| A dotted key, `fix({"building_a.income": ...})` or `free("building_a.income")` | The Value with that key on the Entity or Assembly with that code. A dotted key that names no Value raises `MissingReferenceError` with `by="path"`, the whole dotted key in `requested` and the nearest dotted keys in `candidates` |
| The text of a Value UUID, `fix({"6f1c…": ...})` | That Value. `Model.key_of` gives it for a Value whose key is not unique and whose owner has no code, such as a Relationship |
| A Value or Movement UUID, or a Reference | That Value or Movement |

| Value given to `fix` | Meaning |
| --- | --- |
| A Quantity | That Quantity |
| Text, `"20e6 AUD"` or `"65 %"` | The Quantity that the text gives; text without units raises `UnitError` |
| A number, `coverage=1.25` | A ratio. A target with units that are not dimensionless raises `UnitError` |

`fix` takes the targets that are not keywords, such as dotted keys and UUIDs, in
a mapping as its first argument. One value fixes a scalar Value, or each
Movement of a Flow Value; a mapping from Movement UUIDs to values fixes those
Movements only. A Flow target of `free` frees each of its Movements. Each value
must convert to the units of its target (`UnitError`). A boolean or another type
raises `TypeError`. A Movement UUID that is not in the Flow raises
`MissingReferenceError` (`kind="Movement"`), and a target given twice raises
`ContractError` with the code `UNIQUE`. A target that a rule decides, or that an
included Specification gives a role, raises `ContractError`: change it at its
owner.

`roles` returns a [Table](tables.md) with one row for each value that has a
role, in Model order. Each Row's `id` is the UUID of its target.

| Column | Content |
| --- | --- |
| `key` | The key that `fix` takes, from `Model.key_of`: the bare key; the dotted key when several Values have the key; or the text of the Value UUID when the owner has no code. For a Movement, the key of its Flow Value |
| `movement` | The Movement UUID, or None for a scalar Value |
| `role` | `rk.specification.Role`: `FIXED`, `FREE` or `DECIDED` (a rule controls the value) |
| `quantity` | The fixed Quantity, or None |

A Specification with includes reads its roles from its Composition, so it needs
its resolver. A batch has no roles.

| Failure | Error |
| --- | --- |
| A batch, for `roles`, `fix`, `free`, `cases` and `on` | `ContractError` with the code `BATCH_UNSUPPORTED`: use one case |
| `case` of a concrete Specification | `ContractError` with the code `BATCH_REQUIRED` |
| No pinned Model, for a key | `ContractError` with the code `MODEL_MISSING` |
| Includes, or the cases of a batch read from data, without a resolver | `ContractError` with the code `RESOLVER_MISSING` |
| A Model that is not the revision that the record pins | `ContractError` with the code `IDENTITY` |

## Move to another Model revision

`on(model=)` returns a new Specification of another Model revision, with the
same fixes, rules and estimates of free values; the Specification that it is
called on does not change. Its Metadata has a new UUID and `previous=specification.id`. The free
values are those that the equations of the new revision use and that nothing
fixes or decides, so a value that the revision adds is free.

```python
moved = front.on(model=revised)
lean = front.free("operating_cost").on(model=without_operating_cost)
```

Each fixed or decided target must be a Value or Movement that the new revision
declares. Otherwise `on` raises `ContractError` with the code
`REFERENCE_MISSING`, the target UUIDs in `targets` and their keys in
`values["keys"]`: free the value first, then call `on`. Each fixed Quantity must
convert to the units of its target in the new revision (`UnitError`). An
estimate stays only when its target is free in the new revision, and then its
Quantity must convert too; `on` drops the estimate of a value that the revision
does not declare or that a fix or rule controls. `on` keeps a target by its
UUID, so it follows a Value that a draft of the earlier revision kept, or that a
Model with the same namespace derives. A batch, or a Specification with
includes, raises `ContractError`. When the Model is the pinned revision, `on`
returns the same Specification.

## Cases

`cases(cases=)` returns a batch Specification with one named case for each key.
Each case is a new revision of the Specification that it is called on: its
Metadata name is the case key, `previous` is that Specification, and it fixes the
values that its mapping gives, as `fix` does. A value that a case gives replaces
the fix of the base; an empty mapping keeps the base values. The batch keeps the
base's name, pins the same Model and lists the cases in mapping order. It holds
only `metadata`, `model` and `cases`.

```python
cases = {
    "weak": {"rent_growth": "1 % pa", "exit_cap_rate": "6 %"},
    "reference": {},
    "strong": {"rent_growth": "5 % pa", "exit_cap_rate": "4.5 %"},
}
batch = base.cases(cases=cases)
batch.case(key="weak")  # the case Specification
```

The batch keeps its case Specifications, so `solve` resolves them without a store,
and `execute` puts them in its store before the batch. `case(key=)` returns the
case with that Metadata name; a batch read from data loads its cases with its
resolver. No case with the key raises `MissingReferenceError` with
`kind="Specification"`, `by="key"` and the keys that exist. `cases` of a batch
raises `ContractError` with the code `BATCH_UNSUPPORTED`, and `case` of a
concrete Specification with the code `BATCH_REQUIRED`. Each case Outcome has the case key as its `key`; see
[reading an Outcome](execution.md#read-an-outcome).

## Model and resolver

Key lookup needs the pinned Model. A Specification from `model.specify()` keeps
it, and so does each Specification that a chained call returns. The `model` and
`resolver` properties return them, or None. For a record,
pass it: `Specification(record, model=model)`; a record that pins another revision
raises `ContractError` with the code `IDENTITY`. A Specification with includes also needs
`Specification(record, model=model, resolver=store)`. The Model and resolver are
not saved with the document. Inherited roles and rule-controlled targets must be
edited at their owner. Composition is checked after each edit, and normal
execution still performs full effective validation. Annual totals alone do not
determine monthly allocations; an underdetermined investigation returns a
feasible candidate with a rank diagnostic.
