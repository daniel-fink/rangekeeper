# Develop the schema

LinkML YAML under [`schema/`](../../schema) is the authority for persistent fields,
enums, structural constraints and record descriptions. The generators resolve its
imports into one bundle. Handwritten code owns semantic validation and operations;
it must not redeclare persistent fields. Read the
[architecture](../concepts/architecture.md) for dependency direction.

## Change and generate

Keep schema modules divided by domain responsibility. Change YAML descriptions
at their source so generated record/property docstrings change with the contract.
Every class and every slot needs a description: one sentence that states the
meaning, and the units or presence rules when they matter. The generator stops
on a missing description; it does not write a placeholder docstring.
Generated records contain data only. The owner of a value type adds behaviour
with a subclass that it registers in `rangekeeper.schema.kinds`; the subclass
declares no fields. `OWNERS` in the generator names the owner module of each
value type.

| Material | Owner |
| --- | --- |
| Persistent field and enum definitions | `schema/*.yaml` |
| Resolved bundle and Python/C# generators | `tools/schema/` |
| Generated Python records, JSON Schemas, slots and manifest | `src/rangekeeper/schema/` |
| Generated C# records, transport metadata and manifest | `examples/grasshopper/Model/Generated/` |
| Reusable wire examples | `examples/schema/` |
| Positive/negative conformance procedures | `schema/checks/` |

The generator is a set of small functions: it loads the bundle, derives the
slot metadata, checks it, emits the records and writes the manifest. It stops
when a slot name is a Python keyword or shadows a record method,
when one slot has more than one record type, or when a class or slot has no
description.

A boolean LinkML slot annotation becomes a key of every slot in `slots.json`.
`ANNOTATIONS` in the generator names the permitted annotations. `lineage` marks the
revision identity and lineage slots, `Metadata.id` and `Metadata.previous`. Revision
comparison ignores them, and the Bundle reference index does not list them. The
generator stops at an unknown or non-boolean annotation.

Hand-written code reads field lists from the slot metadata (`slots_for`), not from
literals. Examples are the Polars Movement columns, the Model sections of `Update`
and the closed Specification fields.

Do not edit generated files by hand. Create a separate environment with
[`tools/schema/requirements.txt`](../../tools/schema/requirements.txt). From the
repository root, with that environment active:

```sh
python -m pip install -r tools/schema/requirements.txt
python tools/schema/generate.py
python tools/schema/generate_csharp.py
python tools/schema/generate.py --check
python tools/schema/generate_csharp.py --check
```

Every schema module and every document format is at 1.0.0
([ADR-017](../decisions/017-api-and-formats.md)). The generator writes the
document versions to `manifest.json`; readers get them from there, not from
literals. A change that a 1.x reader cannot read needs a new major format
version. When a change affects wire compatibility, update the version policy,
fixtures and reference documentation together. Source-history
files are evidence; do not regenerate them to conceal a version change.

## Geometry vocabulary and Bundle mapping

[ADR-008](../decisions/008-rangekeeper-bundle-contract.md#provider-neutral-schema-vocabulary)
owns the agreed Rangekeeper Bundle contract. Use **Geometry** as the canonical
concept and provider-neutral type and field names for its descriptor, pin and
mappings. Keep provider, format/schema version, exact specification pin and source
address in metadata. Do not introduce a canonical `SpeckleBundle` type or
`speckle_*` fields. Provider-specific names belong in the corresponding adapter.

The first provider profile uses Speckle's 2026.9 object-model/bundle schema.
That release label does not replace its exact specification version/hash or source
content digest. Future providers must fit the same Geometry boundary; unsupported
formats require an explicit result, not an implicit Speckle fallback.

The [Entity mapping contract](../decisions/008-rangekeeper-bundle-contract.md#entity-to-source-element-mappings)
limits RK endpoints to Entities, including Assemblies, and source endpoints to
objects or permitted structural groups. Keep property/relation evidence in the
existing provenance structure. The new Parquet mapping must derive from this
schema and preserve complete Model content; query engines and user interfaces do
not define a second canonical schema. Shared reconstruction/query fixtures belong
with the reader contract.

The Model has optional provider-neutral Geometry, with Python/C# records generated
from `schema/geometry.yaml`. The [Bundle reference](../reference/bundle.md) defines
the Parquet mapping and publication marker.

The [Bundle acceptance matrix](../decisions/008-rangekeeper-bundle-contract.md#bundle-acceptance-criteria)
records the required conformance checks. A merge into `develop` does not make the
format stable; [ADR-017](../decisions/017-api-and-formats.md) sets that milestone.

## Schema presentation

The [offline schema presentation](../schema-presentation.html) uses the same
resolved LinkML imports, with original descriptions, notes, rules, and source
text. Rebuild it after changing the schema:

```sh
python tools/schema/presentation.py
python tools/schema/presentation.py --check
```

The [presentation guide](../guides/schema-presentation.md) explains its notation,
focused views, and source files. Presentation captions and layouts are curated;
field requirements, collection shapes, and reference modes come from LinkML.

## Conformance

Run all seven suites from the repository root in the pinned schema environment:

```sh
python schema/checks/validate.py
python schema/checks/native_roundtrip.py
python schema/checks/expressions.py
python schema/checks/formulations.py
python schema/checks/models.py
python schema/checks/specifications.py
python schema/checks/runs.py
```

These checks distinguish structural conformance, stock LinkML loader behavior
and bounded domain rules. Generated production records and semantic validators
define the runtime contract. A wire fixture is not a solver result or proof of
external-host execution. See [wire examples](../guides/examples.md#wire-examples-and-fixtures)
for complete documents versus fragments.

Run [typing and distribution checks](verification.md), and the
[C# build and round trips](../../examples/grasshopper/README.md#build-and-round-trip), when
changing generated records or their boundaries. Valid typing fixtures must pass;
deliberately invalid fixtures must retain their expected errors.

## Contract owners

Use [records](../reference/records.md) for construction, presence, immutability
and intrinsic methods; use [identity](../reference/identity.md) for revision scope
and comparison. [Expressions](../reference/expressions.md),
[calculations](../reference/calculations.md) and
[market paths and rules](../reference/market-paths-and-rules.md) own the domain
meaning of their fields. [Run and storage](../reference/run-and-storage.md) owns
publication and stored evidence.

Python is the complete semantic validation boundary for units, expressions,
composition and Run trees. C# serialization preserves presence, and C# authoring
validation checks embedded structure and local references. It does not duplicate
all Python semantic rules. Decisions and captured results remain in the
[decision index](../decisions/README.md) and [research](../research/README.md).
