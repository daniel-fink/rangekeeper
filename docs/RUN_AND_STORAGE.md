# Finalized Runs, codecs and revision stores — Turn 3

**Turn 2 update, 2026-10-06:** [Temporal equations, scenarios and policies](FULL_MIGRATION_TURN2.md)
now use Model/Specification 0.5.0 and Run 0.2.0. `ValueReference` addresses scalar
Values or owner-local Movement keys. The canonical calendar package is `duration/`;
`temporal` has no public alias. Finite Flow formulations, captured scenario replay,
exogenous declarative policies and the four numerical walkthroughs are implemented.
See [verification](research/full-migration/turn2/README.md) and the
[upgrade guide](LEGACY_UPGRADE_GUIDE.md). Turn 3 completes remaining consumers and
integrations; Turn 4 retires obsolete code after their acceptance gates.
The dated checkpoint descriptions below remain historical context.

**Flow semantics update, 2026-10-06:** Flows no longer carry semantic kinds or
basis. The overall model logic owns their meaning and selects operations; units,
dates, alignment and missingness remain checked. See the
[current contract](FULL_MIGRATION_TURN1.md#flow-semantics-and-explicit-operations)
and [verification](research/full-migration/flow-semantics/README.md).

Implemented 2026-10-02: work units **3C and 4** in the
[migration map](DOMAIN_MIGRATION_MAP.md). `rangekeeper.Model`, `Specification` and
`Run` are now public root imports. The [Model/Specification guide](DOMAIN_CORE.md)
and [record boundary](RECORD_BOUNDARY.md) describe their foundations. Run construction,
reference validation, interchange and storage are implemented. The subsequent
[Step 5 scalar executor](SCALAR_EXECUTION.md) now produces authentic valuation outputs.
This branch checkpoint is unreleased.

## Ownership and interfaces

| Package/module | Responsibility |
| --- | --- |
| `run/run.py` | Frozen Run facade over the generated `RunRecord`, with `from_data`, `id`, `metadata`, `record`, `report`, and detached `to_data`. No revise method. |
| `run/_validation.py` | Shared local status/report checks and existing bounded tree/publication semantics; conformance scripts use the same checks. |
| `run/_resolve.py`, `run/validation.py` | Resolve exact document revisions; public `validate(run, *, resolver) -> ValidationReport`. Raw catalogue checks are explicitly named `validate_records`. |
| `references.py` | `SpecificationResolver` supplies Model/Specification reads; `DocumentResolver` extends it with Run reads. Domain code imports no IO implementation. |
| `io/store.py` | `Document` union and `RecordStore` protocol: three typed reads plus `put(document) -> UUID`. |
| `io/json.py`, `io/yaml.py` | Explicit-kind `loads`, `dumps`, `read`, and atomic create-only `write`. YAML is imported only when used. |
| `io/memory.py`, `io/directory.py` | `MemoryStore()` and `DirectoryStore(root)` implement immutable revision storage. |
| `io/_document.py`, `io/_atomic.py` | Small kind/envelope dispatch and filesystem publication helpers; no handwritten field schema. |

Methods and helpers have docstrings documenting validation, error, mutation, and IO
boundaries. Generated records remain the only field authority. Root imports expose
the three facades explicitly; legacy graph/numerical integrations remain lazy. No
solver backend is imported or newly required. Existing distribution dependencies
remain until their consumer migration; lightweight imports do not mean the package's
legacy dependency metadata has been removed.

## A complete in-memory and filesystem example

This deliberately records a **synthetic failed attempt**, not a claim that a solver ran.
Public construction is useful for authoring and testing records; only the future
execution layer will generate authentic execution evidence.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import rangekeeper as rk
from rangekeeper.metadata import Metadata
from rangekeeper.specification import SpecificationRecord, compose, validate as validate_specification
from rangekeeper.run import RunRecord, Report, Status, Diagnostic, validate as validate_run
from rangekeeper.io import MemoryStore, DirectoryStore, json

model = rk.Model.create(metadata=Metadata(id=uuid4(), schema_version="0.5.0"))
specification = rk.Specification(SpecificationRecord(
    metadata=Metadata(id=uuid4(), schema_version="0.5.0"), model=model.id,
))
run = rk.Run(RunRecord(
    metadata=Metadata(id=uuid4(), schema_version="0.2.0", name="Synthetic example"),
    specification=specification.id,
    report=Report(
        status=Status(completion="failed", solution="not_assessed"),
        diagnostics=(Diagnostic(
            severity="error", code="unsupported_capability",
            message="Synthetic example: no execution backend was invoked.",
        ),),
    ),
))

memory = MemoryStore()
memory.put(model)
memory.put(specification)
composition = compose(specification, resolver=memory)
validate_specification(composition, resolver=memory).raise_if_invalid()
validate_run(run, resolver=memory).raise_if_invalid()
memory.put(run)
assert memory.load_run(run.id).report.status.completion == "failed"
assert json.loads(json.dumps(run), kind=rk.Run).to_data() == run.to_data()

with TemporaryDirectory() as directory:
    root = Path(directory)
    disk = DirectoryStore(root / "revisions")
    assert not disk.root.exists()  # construction creates nothing
    for document in (model, specification, run):
        disk.put(document)
    assert disk.put(run) == run.id  # identical revision: no replacement
    assert disk.load_model(model.id).to_data() == model.to_data()
    json.write(run, root / "run.json")
    assert json.read(root / "run.json", kind=rk.Run).id == run.id
```

## Local Run checks and resolved validation

`Run(record)` and `Run.from_data(data)` check structure, supported schema version,
local completion/solution/output combinations, duplicate/self references, required
diagnostics/runtime, implementation uniqueness, finite settings/evidence, and timing
consistency. `not_applicable` declares an aggregate locally; resolving its Specification
must establish that it really is a batch. External references are not loaded during
construction or codec reads.

`run.validation.validate(run, resolver=...)` resolves the attempted Specification,
its includes/cases/Model pins, spawned Runs, output Models, and scoped report documents.
Successful resolutions are cached. Report references carry no kind discriminator;
resolving a previously unseen report document can require up to three typed lookups.
Every returned facade must match the requested UUID and kind. Missing or wrong-kind
references become diagnostic reports; errors in resolver implementations are not
silently swallowed. Historical predecessors are not required for current interpretation.

The shared bounded checks then enforce spawn ownership/cycles, batch accounting and
output unions, status evidence, exact report target scope, and scalar output lineage,
definition preservation and recorded assignments. Failed/cancelled/skipped attempts
may reference an incomplete or mathematically invalid saved Specification when they
report `not_assessed` with a `specification_invalid` diagnostic. Declared external
references must still resolve before store publication. Local Specification validity
is still required for every saved contribution.

These checks **do not prove equation satisfaction, optimality, numerical reproduction,
or that execution happened**. The public Run validator now converts physically
compatible assignments explicitly; the raw conformance entrypoint retains strict
unit-spelling defaults. [Scalar execution](SCALAR_EXECUTION.md) independently
evaluates original expressions on serialized candidates before publication.
Specification-local Value publication and structural interventions remain unsupported
by that adapter. No record schema was changed.

## Interchange contract

Both codecs accept an explicit facade class (`kind=rk.Model`, `rk.Specification`, or
`rk.Run`); they never infer kind or accept a Composition/generated root record as a
saved document. They export canonical document content without a storage envelope.
List encounter order, opaque-content order, omission/null/empty, false/zero, and integer
versus float representations survive round trips. Typed UUID normalization follows
generated slot metadata; arbitrary strings inside opaque content remain untouched.

- JSON rejects duplicate keys at every depth, NaN/Infinity and overflow to non-finite
  floats. Malformed/ambiguous text raises `DecodeError`; valid JSON with invalid
  document structure or semantics keeps its `ValidationError` or version/domain error.
- YAML uses a private SafeLoader subclass. It rejects duplicate/non-string keys,
  merge keys, executable/custom/non-JSON tags, cyclic aliases and non-finite values.
  Non-cyclic aliases are detached copies. Timestamp scalars stay strings, allowing
  typed schema fields to validate their meaning without converting opaque data.
  PyYAML's global loader behavior is unchanged.
- YAML support is the optional `yaml` extra (`PyYAML>=6.0.2,<7`). For this checkout,
  install with `pip install './src[yaml]'` from the repository root. Importing `rk`
  or `rangekeeper.io.yaml` does not import PyYAML. Calling a YAML operation without
  the dependency raises an explanatory `ImportError`.
- `read` uses UTF-8 and performs local document validation. `write` requires an
  existing parent and an absent destination; it never overwrites. Filesystem errors
  remain `OSError` subclasses, while invalid UTF-8 raises `DecodeError`.
- Old Graph JSON is not new Model JSON. No implicit migration/conversion is provided.

## Revision publication and failures

Stores revalidate detached document content. Partial Specifications may be stored
before their external references exist. A Run additionally undergoes resolved validation
against the store; its attempted Specification, referenced contributions/Models, children,
outputs and report documents must be available first. Even an identical Run put is
rechecked against current stored references. A failed validation publishes nothing.

A UUID identifies one immutable revision and kind. Identical content is idempotent;
a different kind or changed content raises `RevisionConflictError`. Equivalence uses
schema-derived ordering annotations: mapping keys and unordered collections are
canonicalized for comparison, while mathematics, objectives, trace, opaque lists,
duplicate multiplicity, presence and numerical representation retain their meaning.
The first stored encounter order is preserved. There is no update/delete API.

`MemoryStore` protects checking/publication with a reentrant lock and returns immutable
snapshots. `DirectoryStore` uses `<UUID>.json` with a closed `{kind, document}` envelope.
Every disk read checks the envelope, document validity, UUID, kind and version. Missing
IDs raise `MissingReferenceError`; wrong kinds `ReferenceTypeError`; filename/content
identity disagreement `IdentityConflictError`; malformed envelopes `DecodeError`.

Directory construction performs no writes. A successful put creates storage as needed,
writes a same-directory temporary file, flushes/fsyncs it, publishes an atomic hard link
only if the UUID filename is absent, removes the temporary name, and fsyncs the directory
where supported. Concurrent identical writes succeed; conflicts never replace the winner.
A process crash before the final link can leave an ignored temporary file, never a partial
final revision. This implementation requires local filesystem support for those primitives;
it does not silently substitute an overwrite operation.

IO failure after linking may leave a complete published record; callers can inspect and
retry idempotently. There is no multi-document transaction: later execution publishes
outputs first, then its Run, and interruption can leave unreferenced complete outputs.
Direct filesystem edits/deletion are outside the store's immutability contract. Loading a
Run checks local consistency; explicit resolved validation can audit its references again.

## Verification and next checkpoint

The [Turn 3 verification](research/domain-migration/turn3/README.md) retains commands,
input fingerprints, local acceptance, conformance and installed-wheel evidence. The
installed tests exercise the core with only the needed declared domain dependencies,
first without YAML/Pint for unit-free operations, then with Pint and the YAML extra
for every document fixture. They do not claim that all legacy integration dependencies
or external service consumers have been exercised. Remote CI and other platforms remain
unverified; two known legacy baseline tests still fail.

The three domain implementation turns are complete. **Step 5 is also implemented**:
[scalar execution](SCALAR_EXECUTION.md) prepares declared equations and roles, solves
both directions with pinned Pyomo/HiGHS, independently checks candidates, and publishes
authentic immutable outputs and finalized Runs through these interfaces. See its
[separate evidence](research/scalar-execution/README.md) for 11,000,000 AUD forward,
27,500 AUD/dwelling/year inverse, genuine output reuse, failures, limits and batches.
[Step 6A/6B graph operations](GRAPH_MODEL.md) are now implemented; Step 6C
tables and presentation adapters are next.
