# Specification contributions, composition and validation

A `Specification` records an investigation against one exact input Model revision.
It can declare assignments, unknowns, estimates, bounds, objectives and policy
requirements. Saved partial contributions and batches are valid document shapes;
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
| `specification/policy/` | Dated declarations, causal observation and independent outcome validation |
| `shared/references.py` | Resolver protocols without a storage dependency |

## Contributions, composition and validation

The Specification facade contains a generated `SpecificationRecord`. `.id` and
`.metadata` expose revision identity; `.record` supplies typed access to every schema
field without another handwritten field facade. `from_data` validates local ownership,
known local reference kinds, duplicate requirements, roles, settings and header rules.
External references and incomplete solve roles are permitted in a saved contribution.

The short example below uses `model` and `gross` from the
[Model authoring example](model.md#authoring-lookup-and-revisions).

```python
from uuid import uuid4
from rangekeeper.schema import Metadata
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

Composition permits one policy contribution. Its controls cannot also be assigned
or unknown, and policy outcomes must follow the declared information availability.
See [policies](scenarios-and-policies.md#policy-declarations-and-evidence).

Pass the caller's `UnitSystem` through validation and execution. Public validation
uses explicit compatibility checks; raw conformance entrypoints retain their
strict spelling defaults unless a unit adapter is supplied. The [Model unit
contract](model.md#units-and-limits) owns conversion and currency rules.

Complete validation prepares the exact resolved Model, combined Scope and
ExpressionAnalysis once for that operation. It checks declaration ownership,
references, domains and solve roles. It does not execute queries, certify numerical
feasibility or establish backend support. A structurally valid objective or
Function can still be unsupported by the selected executor.

## Lock and unlock quantities

`specification.lock(target, quantity, id=..., model=...)` returns a new revision
with explicit assignments. `unlock(target, id=..., model=...)` removes matching
local assignments and declares unknowns. Both retain the equations and unrelated
Specification content. The new metadata records `previous=specification.id`.
Neither method saves or executes the revision.

A target can be a scalar Reference, Movement UUID or Flow Value UUID. For a Flow,
`ids=` selects Movement UUIDs; omission selects all its declared Movements. One
Quantity applies to every selected target, or a mapping supplies a Quantity per
selected UUID. Use `recorded=True` instead of quantity to copy recorded values
explicitly; unresolved amounts fail. An omitted quantity never means reuse.

A lock removes matching local unknowns and estimates. Role editing requires the
pinned Model. Included contributions require `resolver=`; inherited roles and
policy-controlled targets must be edited at their owner. Composition is checked
after editing, and normal execution still performs full effective validation.
Annual totals alone do not determine monthly allocations; an underdetermined
investigation returns a feasible candidate with a rank diagnostic.
