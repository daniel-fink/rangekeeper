# Finalized Runs, codecs and revision stores

A Run records a finalized attempt. Strict codecs preserve field presence; stores publish immutable revisions. Resolver-backed validation checks references and publication evidence.

## Ownership and interfaces

| Package/module | Responsibility |
| --- | --- |
| `run/run.py` | Frozen Run facade over the generated `RunRecord`, with `from_data`, `id`, `metadata`, `record`, `report`, and detached `to_data`. No revise method. |
| `run/report.py`, `run/outputs.py` | Shared status/report rules and pure output conformance checks; no output helper owns traversal state. |
| `run/validation.py` | One operation-local owner resolves exact documents, caches matching preparation, and checks the Run tree; public `validate(run, *, resolver) -> ValidationReport`. Raw catalogue checks are explicitly named `validate_records`. |
| `references.py` | `SpecificationResolver` supplies Model/Specification reads; `DocumentResolver` extends it with Run reads. Domain code imports no IO implementation. |
| `io/store.py` | `Document` union and `RecordStore` protocol: three typed reads plus `put(document) -> UUID`. |
| `io/json.py`, `io/yaml.py` | Explicit-kind `loads`, `dumps`, `read`, and atomic create-only `write`. YAML is imported only when used. |
| `io/memory.py`, `io/directory.py` | `MemoryStore()` and `DirectoryStore(root)` implement immutable revision storage. |
| `io/_document.py`, `io/_atomic.py` | Small kind/envelope dispatch and filesystem publication helpers; no handwritten field schema. |

Methods and helpers have docstrings documenting validation, error, mutation, and IO
boundaries. Generated records remain the only field authority. Root imports expose
the three facades explicitly; legacy graph/numerical integrations remain lazy. No
solver backend is imported or newly required. Optional dependencies follow the [installation guide](../src/README.md).

## A complete in-memory and filesystem example

This deliberately records a **synthetic failed attempt**, not a claim that a solver ran.
Public construction is useful for authoring and testing records; the [execution layer](SCALAR_EXECUTION.md) generates authentic execution evidence.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import rangekeeper as rk
from rangekeeper.metadata import Metadata
from rangekeeper.specification import SpecificationRecord
from rangekeeper.run import RunRecord, Report, Status, Diagnostic, CompletionStatus, SolutionStatus, Severity, validate as validate_run
from rangekeeper.io import MemoryStore, DirectoryStore, json

model = rk.Model.create(metadata=Metadata(id=uuid4(), schema_version="0.7.0"))
specification = rk.Specification(SpecificationRecord(
    metadata=Metadata(id=uuid4(), schema_version="0.7.0"), model=model.id,
))
run = rk.Run(RunRecord(
    metadata=Metadata(id=uuid4(), schema_version="0.4.0", name="Synthetic example"),
    specification=specification.id,
    report=Report(
        status=Status(completion=CompletionStatus.FAILED, solution=SolutionStatus.NOT_ASSESSED),
        diagnostics=(Diagnostic(
            severity=Severity.ERROR, code="unsupported_capability",
            message="Synthetic example: no execution backend was invoked.",
        ),),
    ),
))

memory = MemoryStore()
memory.put(model)
memory.put(specification)
composition = specification.compose(resolver=memory)
composition.validate(resolver=memory).raise_if_invalid()
validate_run(run, resolver=memory).raise_if_invalid()
memory.put(run)
assert memory.load_run(run.id).report.status.completion is CompletionStatus.FAILED
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
by that adapter.

Historical Claims require exact, type-sensitive preservation: changing `0` to
`False`, changing a floating zero sign, or reordering an opaque list is a change.
Output checks apply their explicit numerical-field allowlist separately. Store
revision conflicts use schema equivalence; that does not relax historical evidence.

Policy evidence is stored as `Report.outcomes`, containing `DecisionOutcome` records
that name their declared `Decision`. Recorded controls cannot substitute for an
earlier outcome. Both output and no-output validation branches use the supplied
UnitSystem and independently check observations, actions and first matching rules.

A valid composed Model pin remains available for batch assertions after a later
mathematical failure. Child checks retain these pins for their parent; parent
accounting does not recompose each descendant. `completion_for` consumes canonical
CompletionStatus members and returns a member; empty input yields COMPLETED, while
actual batch validation still enforces complete case accounting.

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

IO failure after linking leaves a complete published record when directory sync
fails. The internal publication error identifies the visible path; callers can
inspect and retry idempotently. The same distinction applies to atomic pointer
replacement: visibility can be established while durability remains unconfirmed.
There is no multi-document transaction: execution publishes
outputs first, then its Run, and interruption can leave unreferenced complete outputs.
Direct filesystem edits/deletion are outside the store's immutability contract. Loading a
Run checks local consistency; explicit resolved validation can audit its references again.

## Verification

See [verification](VERIFICATION.md) for current commands and the distinction
between local report checks, resolver-backed validation and real execution.
The [executor](SCALAR_EXECUTION.md) uses these interfaces to persist accepted
outputs before their finalized Runs. [Graph consumers](GRAPH_MODEL.md) and
[source workflows](CONSUMER_MIGRATION.md) use the same canonical records.
