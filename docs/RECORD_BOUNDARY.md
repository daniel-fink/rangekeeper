# Generated records and shared validation — Turn 1

Implemented 2026-10-02. This completes work units **2A and 2B** in
the [migration map](DOMAIN_MIGRATION_MAP.md). The Python record
boundary was reviewed before Turn 2. [Model/Specification domain behavior](DOMAIN_CORE.md)
is now implemented; this page documents the underlying record layer. The root `rk.Model`, `rk.Specification`
and `rk.Run` facades are now available through [Turn 3](RUN_AND_STORAGE.md); imports below deliberately use the private
generated bundle to demonstrate what now works.

## Ownership and files

| Files | Responsibility |
| --- | --- |
| `tools/schema/bundle.yaml`, `generate.py`, `requirements.txt` | Shared Model/Specification/Run imports, pinned generation and nonmutating `--check`. |
| `src/rangekeeper/_schema/{records,native}.py` | Generated explicit immutable constructors/properties; stock mutable LinkML records used only for interoperability checks. Fifty LinkML classes are accounted for: 49 immutable classes and opaque `Content` represented as JSON data. |
| `_schema/{schema,slots,manifest}.json` | Closed structural definitions, schema-derived conversion information, source/output fingerprints and tool versions. |
| `_records.py` | Common strict JSON copying, recursive freezing, field presence, schema-directed UUID conversion and detached exports. No handwritten field inventory. |
| `_schema/validation.py`, `diagnostics.py`, `errors.py` | Packaged structural validation and immutable reports/errors. |
| `_validation.py`, `model/{_expression,_formulation,_validation}.py` | Shared semantic invariants plus bounded mathematical and Model rules. See the subsequent [validation refactor](DOMAIN_CORE.md#composable-validation) for current ownership. |
| `specification/{_composition,_validation}.py`, `run/_validation.py` | Existing additive-composition, investigation and finalized-Run checks, moved without changing their algorithms. |
| `{model,specification,run}/validation.py` | Typed report entrypoints: validate structure before invoking bounded semantics. |
| `schema/checks/_library.py` | Standalone script bootstrap, packaged-schema access and stale-source fingerprint detection. Conformance scripts call library checks. |

Generated records depend on the generic record mechanics and JSON Schema validation.
Domain validation consumes detached document data. Neither imports a solver, graph
implementation, filesystem store, plotting module or service adapter. `graph` and
`measure` now use the root package's existing lazy-import mechanism; their existing
names and implementations remain available. No graph consumer has been migrated.

Runtime structural dependencies are `jsonschema>=4.26,<5` and
`rfc3339-validator>=0.1.4,<0.2`. Explicit timestamp format checking prevents a minimal
installation from silently ignoring `date-time`. Generation uses the exact versions
in `tools/schema/requirements.txt`. LinkML is not a runtime dependency of these records.

## Working authoring and access

```python
from uuid import uuid4
from rangekeeper._schema.records import (
    Characteristics, Entity, Metadata, Model, Quantity, System, Value,
)
from rangekeeper.model.validation import validate

value = Value(
    id=uuid4(), key="rent", kind="measurement", measure=uuid4(),
    quantity=Quantity(magnitude=0, units="AUD/year"),
)
entity = Entity(id=uuid4(), characteristics=Characteristics(values=(value,)))
assert entity.characteristics.values[0].quantity.magnitude == 0

# A complete Model must declare every referenced Measure. Structural construction
# of the child above cannot establish that document-wide ownership/reference rule.
model = Model(metadata=Metadata(id=uuid4(), schema_version="0.3.0"))
validate(model).raise_if_invalid()
restored = Model.from_data(model.to_data())
assert restored.metadata.id == model.metadata.id
```

Constructors are keyword-only, with explicit required fields, enum Literal types,
unions, UUID references and inherited fields. `Assembly` subclasses `Entity`.
Type checking catches missing required arguments, unknown fields, wrong enum/record
types and writes to read-only properties. Python considers `bool` a subtype of `int`;
runtime structural checks still reject it for numerical fields.

The generated constructor and `from_data(data)` validate structure. They **do not**
certify cross-record semantics. `Model.from_data` here means the generated record,
not the separately implemented domain facade's factory. Call the appropriate validator explicitly.
The typed constructor surface prefers UUIDs and generated child records; `from_data`
accepts their serialized forms. Runtime construction also accepts schema-compatible
plain child data and UUID strings, without numeric coercion.

| Operation | Behavior and errors |
| --- | --- |
| `Record.from_data(data: Mapping[str, object]) -> Self` | Validate/copy/freeze. Invalid shape raises `ValidationError`; non-JSON objects, cycles and non-finite numbers raise `TypeError`/`ValueError`. |
| `Record.from_json(text: str) -> Self` | Same path, rejecting duplicate keys at every depth. Parsing/duplicate failures are `ValueError`; this is not yet the planned public codec package. |
| `record.to_data() -> dict[str, object]` | Detached JSON-compatible data; safe for callers to modify. No file IO. |
| `record.has_field(name: str) -> bool` | Distinguishes omission from explicit null/empty. Unknown names raise `KeyError`. |
| Generated properties | UUIDs, immutable embedded records, tuples, read-only mappings and JSON scalars. Assignment/deletion raises `AttributeError`; mapping mutation raises `TypeError`. |
| Equality | Same generated class and same serialized representation, ignoring object-key order. Array order, null/omission, booleans versus numbers, and integer/float representation remain distinct. This is not the future domain diff API. Records are unhashable. |

Absent optional scalar properties return `None`; absent collections return empty
tuples or read-only mappings. Explicit null returns `None` only when the schema permits
it. Export retains these distinctions. UUID normalization is limited to schema-declared
slots: an `id` string inside opaque Claim content is left untouched.

`Location.address` illustrates LinkML's keyed inline representation. Both
`{"line": "1"}` and `{"line": {"value": "1"}}` are allowed, as is an explicit
Entry key inside the latter form. Access exposes read-only mappings and scalar values;
export preserves the supplied form exactly. It does not invent an absent Entry key or
turn this dictionary into a tuple. Its generated annotation reflects the scalar/mapping
alternatives; validation supplies the reduced Entry field constraints.

## Shared validation entrypoints

These are bounded, in-memory entrypoints for the record stage. Turn 2 adds the
[facade/resolver interface](DOMAIN_CORE.md); its Composition operation is now named
`specification.validation.validate`, while the catalogue entrypoint below is named
`validate_records`. Both reuse the same bounded semantic implementation.

```python
from rangekeeper.model.validation import validate as validate_model
from rangekeeper.specification.validation import validate_records as validate_specification
from rangekeeper.run.validation import validate as validate_run

validate_model(model_record, history=())
validate_specification(spec_record, models=models_by_revision,
                       specifications=specifications_by_revision)
validate_run(run_record, runs=runs_by_revision,
             specifications=specifications_by_revision, models=models_by_revision)
```

Inputs may be generated records or serialized mappings. Catalogue keys are canonical
UUID strings. Results are `ValidationReport(issues: tuple[Issue, ...])` with `valid`
and `raise_if_invalid()`. Each `Issue` has `code`, `message`, optional UUID
`document_id`, and JSON pointer `path`. Structural diagnostics identify instance paths;
the migrated semantic checks currently report `semantic.contract` at document level.
They have not acquired fabricated field precision or specialized error classifications.

Specification validation handles concrete investigations and batches against pinned
Models. Partial contributions remain structurally constructible; validating a concrete
investigation requires its Model and complete roles. The internal composition result
remains private conformance state; Turn 2 exposes it through an immutable public
Composition with contributor snapshots and a read-only resolver.

Unit matching uses the bounded existing logic and an optional `units_compatible`
callback. Expression unit inference, graph query evaluation, arbitrary Fact/content
agreement, solver capability, numerical feasibility and independent solution acceptance
remain outside these checks. Run examples remain synthetic conformance evidence.

## Verification and next review

The [Turn 1 verification record](research/domain-migration/turn1/README.md) contains
commands, environments, fingerprints and logs. All seven existing schema suites pass;
new boundary tests and positive/negative static examples pass. The generated native
bundle is also checked separately. A wheel built in an isolated directory exercises
the record boundary in a fresh environment outside the checkout, without LinkML,
numerical packages or solver dependencies. This is not full installed consumer acceptance.

Review the explicit constructors, presence behavior, read-only access and separation
between structural construction and document validation. Turn 2 now supplies Model indexing/lookup, owner-local access, revision construction
and public Specification composition. Run, persistence and final public/package
acceptance are now implemented in [Turn 3](RUN_AND_STORAGE.md). Execution remains a later checkpoint. No commit, push or release is included.
