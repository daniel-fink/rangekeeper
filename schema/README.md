# Rangekeeper schema

LinkML is the authoritative definition of persistent fields, enums and structural
constraints. Python and C# records and JSON Schemas are generated from its resolved
bundle. Handwritten code owns semantic validation and operations; it does not
redeclare the fields. The [architecture](../docs/LIBRARY_ARCHITECTURE.md) explains
why these boundaries exist.

## Contracts

The document roots are Model and Specification version `0.5.0`, and Run version
`0.2.0`. Each contains Metadata with a revision UUID. Model holds Definitions,
System and Provenance. Specification describes an investigation over exact
revisions. Run records a finalized attempt and accepted outputs.

- [Object model](../docs/MODEL_SPECIFICATION_RUN.md): root ownership and rationale.
- [Record boundary](../docs/RECORD_BOUNDARY.md): immutable access and field presence.
- [Expression contract](../docs/EXPRESSION_CONTRACT.md): syntax and mathematical meaning.
- [Calculations](../docs/CALCULATIONS.md): dates, Movements and units.
- [Scenarios and policies](../docs/SCENARIOS_AND_POLICIES.md): ValueReference and causal replay.
- [Run and storage](../docs/RUN_AND_STORAGE.md): status, publication and exact revisions.

Use native UUID references in Python and UUID strings on the wire. Owned records
are embedded once; references do not duplicate ownership. Ordered mathematics,
Movements and execution traces retain their order. Absent fields, explicit null,
empty lists, zero and false are distinct where the schema permits them. Opaque
Content is not traversed as a domain declaration.

See [validated wire examples](../docs/SCHEMA_EXAMPLES.md) for record ownership
and mathematical syntax.

## Sources and generated outputs

The YAML files in this directory divide the schema by domain responsibility.
`rk.yaml` aggregates the root imports. Examples and conformance cases are in
`examples/` and `checks/`. Generated Python records, schemas, slots and a source
manifest are packaged under `src/rangekeeper/_schema`. Generated C# records and
transport metadata are under `grasshopper/Model/Generated`.

Do not edit generated files. From the repository root, in the pinned schema tool
environment specified by [tools/schema/requirements.txt](../tools/schema/requirements.txt):

```sh
python tools/schema/generate.py
python tools/schema/generate_csharp.py
python tools/schema/generate.py --check
python tools/schema/generate_csharp.py --check
```

Python mixins under `_behaviors` declare no fields. The generator attaches them to
selected records and generates typed `replace()` methods. Schema descriptions
supply record and property docstrings. C# serialization preserves field presence;
its authoring Validator checks embedded structure and local references.

## Verification and limits

```sh
python schema/checks/validate.py
python schema/checks/native_roundtrip.py
python schema/checks/expressions.py
python schema/checks/formulations.py
python schema/checks/models.py
python schema/checks/specifications.py
python schema/checks/runs.py
```

Run from the repository root with the pinned schema environment. The checks
separate structural conformance, native loader behavior and bounded domain rules.
The stock LinkML loader has a known limitation for terminal policy Action shapes;
the generated production records and semantic validators define supported runtime
behavior. A conformance fixture is not proof of solver or external-host execution.

Python is the complete semantic validation boundary for units, expressions,
composition and Run trees. The C# authoring subset does not duplicate all those
rules. See [verification](../docs/VERIFICATION.md) for typing, package, solver,
notebook and host checks. Earlier design choices and captured results remain in
[history](../docs/history/README.md) and [research](../docs/research/README.md).
