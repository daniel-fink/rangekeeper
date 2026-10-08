# Develop the schema

LinkML YAML under [`schema/`](../../schema) is the authority for persistent fields,
enums, structural constraints and record descriptions. The generators resolve its
imports into one bundle. Handwritten code owns semantic validation and operations;
it must not redeclare persistent fields. Read the
[architecture](../concepts/architecture.md) for dependency direction.

## Change and generate

Keep schema modules divided by domain responsibility. Change YAML descriptions
at their source so generated record/property docstrings change with the contract.
Python behaviors under `src/rangekeeper/schema/behaviors/` declare no fields. The
generator attaches those behaviors to selected records and generates typed
`replace()` methods.

| Material | Owner |
| --- | --- |
| Persistent field and enum definitions | `schema/*.yaml` |
| Resolved bundle and Python/C# generators | `tools/schema/` |
| Generated Python records, JSON Schemas, slots and manifest | `src/rangekeeper/schema/` |
| Generated C# records, transport metadata and manifest | `src/grasshopper/Model/Generated/` |
| Reusable wire examples | `examples/schema/` |
| Positive/negative conformance procedures | `schema/checks/` |

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

When a change affects wire compatibility, update its explicit migration,
version policy, fixtures and reference documentation together. Source-history
files are evidence; do not regenerate them to conceal a version change.

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
[C# build and round trips](../guides/grasshopper.md#build-and-round-trip), when
changing generated records or their boundaries. Valid typing fixtures must pass;
deliberately invalid fixtures must retain their expected errors.

## Contract owners

Use [records](../reference/records.md) for construction, presence, immutability
and intrinsic methods; use [identity](../reference/identity.md) for revision scope
and comparison. [Expressions](../reference/expressions.md),
[calculations](../reference/calculations.md) and
[scenarios and policies](../reference/scenarios-and-policies.md) own the domain
meaning of their fields. [Run and storage](../reference/run-and-storage.md) owns
publication and stored evidence.

Python is the complete semantic validation boundary for units, expressions,
composition and Run trees. C# serialization preserves presence, and C# authoring
validation checks embedded structure and local references. It does not duplicate
all Python semantic rules. Decisions and captured results remain in the
[decision index](../decisions/README.md) and [research](../research/README.md).
