# Finalized Runs, codecs and revision stores

A Run records a finalized attempt. Strict codecs preserve field presence; stores publish immutable revisions. Resolver-backed validation checks references and publication evidence.

## Ownership and interfaces

| Package/module | Responsibility |
| --- | --- |
| `run/run.py` | Frozen Run facade over the generated `RunRecord`, with `from_data`, `id`, `metadata`, `record`, `report`, `paths` (the UUID of the market paths whose series fix its cases, or None) and detached `to_data`. No revise method. |
| `run/report.py`, `run/outputs.py` | Shared status/report rules and pure output conformance checks; no output helper owns traversal state. |
| `run/validation.py` | One operation-local owner resolves exact documents, caches matching preparation, and checks the Run tree; public `validate(*, run, resolver) -> ValidationReport`. Raw catalogue checks are explicitly named `validate_records`. |
| `run/documents.py` | For internal use by `run`, `execution` and `io`: `Documents`, a read-only resolver of its own documents first, else a fallback resolver; `dependencies(document)`, the one list of the documents that a document needs; and `closure(roots, resolver=)`, which resolves them once each. Run validation, `Overlay`, `Cases` and the Bundle use them. |
| `shared/references.py` | `SpecificationResolver` supplies Model/Specification reads; `DocumentResolver` extends it with Run reads. `require_revision` checks the UUID and kind of a document that a lookup read. Domain code imports no IO implementation. |
| `shared/store.py` | `RecordStore` protocol: the typed reads `load_model`, `load_specification`, `load_run` and `load_paths` (market paths), `find_runs(*, specification) -> tuple[Run, ...]` and `put(document) -> UUID`. `execution` depends on this protocol, not on `io`. Import it from `rangekeeper.io`. |
| `io/files.py` | `load(*, path)` and `save(*, document, path, resolver=None)`: one [document file](#document-files) with the documents that it depends on, read with no kind. |
| `io/json.py`, `io/yaml.py` | Explicit-kind `loads`, `dumps`, `read`, and atomic create-only `write`. YAML is imported only when used. |
| `io/memory.py`, `io/directory.py` | `MemoryStore()` and `DirectoryStore(path)` implement immutable revision storage of Models, Specifications, Runs and market paths (`rk.market.Paths`). |
| `io/_runs.py` | The [search for Runs](#find-runs) that both stores use. |
| `io/_document.py`, `io/_atomic.py` | The `Document` union, small kind/envelope dispatch and filesystem publication helpers; no handwritten field schema. |

Methods and helpers have docstrings documenting validation, error, mutation, and IO
boundaries. Generated records remain the only field authority. Root imports expose
the three facades explicitly; optional adapter and calculation packages remain lazy. No
solver backend is imported or newly required. Optional dependencies follow the [installation guide](../guides/installation.md).

## A complete in-memory and filesystem example

This deliberately records a **synthetic failed attempt**, not a claim that a solver ran.
Public construction is useful for authoring and testing records; the [execution layer](execution.md) generates authentic execution evidence.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import rangekeeper as rk
from rangekeeper.model import Metadata
from rangekeeper.specification import SpecificationRecord
from rangekeeper.run import (
    RunRecord,
    Report,
    RunStatus,
    Diagnostic,
    CompletionStatus,
    SolutionStatus,
    Severity,
    validate as validate_run,
)
from rangekeeper.io import MemoryStore, DirectoryStore, json

model = rk.Model.create(metadata=Metadata(id=uuid4(), schema_version="1.0.0"))
specification = rk.Specification(
    record=SpecificationRecord(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        model=model.id,
    )
)
run = rk.Run(
    RunRecord(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0", name="Synthetic example"),
        specification=specification.id,
        report=Report(
            status=RunStatus(
                completion=CompletionStatus.FAILED, solution=SolutionStatus.NOT_ASSESSED
            ),
            diagnostics=(
                Diagnostic(
                    severity=Severity.ERROR,
                    code="unsupported_capability",
                    message="Synthetic example: no execution backend was invoked.",
                ),
            ),
        ),
    )
)

memory = MemoryStore()
memory.put(model)
memory.put(specification)
composition = specification.compose(resolver=memory)
composition.validate(resolver=memory).raise_if_invalid()
validate_run(run=run, resolver=memory).raise_if_invalid()
memory.put(run)
assert memory.load_run(run.id).report.status.completion is CompletionStatus.FAILED
assert json.loads(text=json.dumps(run), kind=rk.Run).to_data() == run.to_data()

with TemporaryDirectory() as directory:
    root = Path(directory)
    disk = DirectoryStore(root / "revisions")
    assert not disk.root.exists()  # construction creates nothing
    for document in (model, specification, run):
        disk.put(document)
    assert disk.put(run) == run.id  # identical revision: no replacement
    assert disk.load_model(model.id).to_data() == model.to_data()
    json.write(document=run, path=root / "run.json")
    assert json.read(path=root / "run.json", kind=rk.Run).id == run.id
```

## Local Run checks and resolved validation

`Run(record)` and `Run.from_data(data)` check structure, supported schema version,
local completion/solution/output combinations, duplicate/self references, required
diagnostics/runtime, implementation uniqueness, finite settings/evidence, and timing
consistency. A `feasible` conclusion has outputs. An `underdetermined` conclusion has an
`underdetermined` or `uniqueness_not_assessed` diagnostic, and outputs only when the
execution published its candidate on request
([`allow_underdetermined`](execution.md#configuration)); other conclusions have none.
`not_applicable` declares an aggregate locally; resolving its Specification
must establish that it really is a batch. External references are not loaded during
construction or codec reads.

`run.validate(resolver=...)`, `run.check(resolver=...)` and
`rangekeeper.run.validate(run=..., resolver=..., units=None)` resolve the attempted Specification,
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

To validate the Run of an Outcome before its outputs are stored, lay them over the
resolver with `rangekeeper.execution.Overlay(resolver=, models=, runs=)`.
Execution validates its Runs this way, and it reuses the compositions and
Specification checks that it already ran; that reuse is internal to execution.

These checks **do not prove equation satisfaction, optimality, numerical reproduction,
or that execution happened**. The public Run validator now converts physically
compatible assignments explicitly; the raw conformance entrypoint retains strict
unit-spelling defaults. [Scalar execution](execution.md) independently
evaluates original expressions on serialized candidates before publication.
Specification-local Value publication and structural interventions remain unsupported
by that adapter.

Historical Claims require exact, type-sensitive preservation: changing `0` to
`False`, changing a floating zero sign, or reordering an opaque list is a change.
Output checks apply their explicit numerical-field allowlist separately. Store
revision conflicts use schema equivalence; that does not relax historical evidence.
See the [comparison rules](identity.md#comparison-rules).

A case with rules stores [its decision trace](market-paths-and-rules.md#the-decision-trace)
as one `RuleEvidence` in `Report.rule_evidence`. An output needs a verified trace, and
resolver-backed validation checks the trace again against the path data and the
output, with no solve.

A valid composed Model pin remains available for batch assertions after a later
mathematical failure. Child checks retain these pins for their parent; parent
accounting does not recompose each descendant. `completion_for` consumes canonical
CompletionStatus members and returns a member; empty input yields COMPLETED, while
actual batch validation still enforces complete case accounting.

## Document files

`rk.io.save(document=, path=)` writes one document to a JSON file, with the
documents that it depends on, and `rk.io.load(path=)` reads it back. A
document is a Model, a Specification, a Run or market paths (`rk.market.Paths`).
The file gives the kind, so `load` takes none:

```python
import rangekeeper as rk

rk.io.save(document=back, path="data/02_back_door.specification.json")
lesson_02 = rk.io.load(path="data/02_back_door.specification.json")
lesson_02.roles  # the loaded Specification keeps its Model
outcome = rk.execution.solve(specification=lesson_02)  # no resolver needed
```

A file is one JSON object: the `kind` and the `document`, as the codecs write
it, and `documents`, a list of the other documents with their kind and content.
`documents` is absent when the document depends on none, as for a Model or
market paths; the file is then the envelope of a
[`DirectoryStore`](#revision-publication-and-failures) file, so `load` reads
that file too.

```json
{
  "kind": "Specification",
  "document": {"metadata": {"id": "...", "schema_version": "1.0.0"}, "model": "..."},
  "documents": [{"kind": "Model", "document": {"metadata": {"id": "...", "schema_version": "1.0.0"}}}]
}
```

- **Dependencies.** The file holds the closure of the document: a
  Specification's Model, includes and cases, and a Run's Specification,
  outputs, spawned Runs and report documents, at any depth. A Specification
  brings the documents that it keeps: the Model of `model.specify()` and the
  cases that `cases` made, with their Models. Its own resolver gives the
  others, or `resolver=` when it is given. Another document takes its
  dependencies from `resolver=`. A dependency that cannot be found raises
  `MissingReferenceError` and writes nothing.
- **Publication.** `save` makes missing parent folders and writes atomically.
  It never replaces a file: when the path holds the same document already, it
  returns the path, and another document there raises
  `RevisionConflictError`. It returns the path.
- **Loading.** Each document is validated as `rk.io.json.read` validates it. A
  loaded Specification keeps its Model and the other documents of the file as
  its resolver, so `fix`, `roles` and `rk.execution.solve` find them. The other
  documents are read as a store reads them, with no Model kept. Text that is
  not a document file raises `DecodeError`; a document that the file's
  document needs and the file lacks raises `MissingReferenceError`; and a
  document that it does not need raises `DecodeError`.

A document file is for one document and the exact revisions that it needs. A
[Bundle](bundle.md) delivers several roots with Geometry in Parquet tables;
stores hold any number of revisions.

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
  install with `pip install '.[yaml]'` from the repository root. Importing `rk`
  or `rangekeeper.io.yaml` does not import PyYAML. Calling a YAML operation without
  the dependency raises an explanatory `ImportError`.
- `read` uses UTF-8 and performs local document validation. `write` requires an
  existing parent and an absent destination; it never overwrites. Filesystem errors
  remain `OSError` subclasses, while invalid UTF-8 raises `DecodeError`.
- Old Graph JSON is not new Model JSON. No implicit migration/conversion is provided.

## Find Runs

`store.find_runs(specification=name)` returns the stored Runs whose attempted
Specification has the name `name`, as a tuple that can be empty
([#294](https://github.com/daniel-fink/rangekeeper/issues/294)). It is a search,
like `Model.find_entities`: it does not select one Run. The Runs come in the
order of their recorded finish times (`report.runtime.finished_at`), earliest
first, so `[-1]` is the Run that finished last:

```python
store = rk.io.DirectoryStore(path="runs/03")
run = store.find_runs(specification="Base case")[-1]
```

A batch Run records no time of its own: it takes the latest finish time of its
case Runs. A Run without a time comes first. Runs with the same time keep the
order of their puts in a `MemoryStore`, and UUID order in a `DirectoryStore`.
The order does not depend on the store or on file times, so a copied folder
gives the same order. A batch Specification that `Specification.cases` made
has the name of its base, and each case has its case key: in the example,
`"Base case"` finds the batch Runs and `"weak"` the Runs of one case.

`DirectoryStore` reads and validates each stored Run, and the Specification of
each, so the search reads every Run of the folder. A file whose name is not
`<UUID>.json`, such as the temporary file of an interrupted put, is not a
revision. The `name` is exact and case-sensitive; text that is not a string
raises `TypeError`, and empty text `ContractError`. Use the Run with
[`rk.execution.replay`](execution.md#replay-a-stored-run). The
[store layering](https://github.com/daniel-fink/rangekeeper/issues/176) will
enumerate stores in general.

## Revision publication and failures

Stores and codecs trust a validated document: an exact `Model`, `Specification` or
`Run` instance was validated when it was built and is immutable, so `put`, `dumps`
and `write` do not validate it again ([ADR-011](../decisions/011-records-and-validation.md#when-validation-runs)).
Data input is always validated: `loads`, `read` and every store read decode
through `from_data`. Partial Specifications may be stored
before their external references exist. A Run additionally undergoes resolved validation
against the store; its attempted Specification, referenced contributions/Models, children,
outputs and report documents must be available first. Even an identical Run put is
rechecked against current stored references, except when execution already
validated that Run against the same store instance and every revision that the
validation read from elsewhere is now in the store: execution marks such a Run,
and `MemoryStore` and `DirectoryStore` then skip the repeat. A failed validation
publishes nothing.

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

`DirectoryStore(path)` takes the folder of the files, as text or a path, such as
`DirectoryStore(path="runs/03")`; a relative path is relative to the working
folder at construction, and `root` is the absolute folder.
Directory construction performs no writes. A successful put creates storage as needed,
writes a same-directory temporary file, flushes/fsyncs it, publishes an atomic hard link
only if the UUID filename is absent, removes the temporary name, and fsyncs the directory
where supported. Concurrent identical writes succeed; conflicts never replace the winner.
A process crash before the final link can leave an ignored temporary file, never a partial
final revision. This implementation requires local filesystem support for those primitives;
it does not silently substitute an overwrite operation.

IO failure after linking leaves a complete published record when directory sync
fails. The internal publication error identifies the visible path; callers can
inspect and retry idempotently. There is no multi-document transaction: execution publishes
outputs first, then its Run, and interruption can leave unreferenced complete outputs.
Direct filesystem edits/deletion are outside the store's immutability contract. Loading a
Run checks local consistency; explicit resolved validation can audit its references again.

## Verification

See [verification](../contributing/verification.md) for current commands and the distinction
between local report checks, resolver-backed validation and real execution.
The [executor](execution.md) uses these interfaces to persist accepted
outputs before their finalized Runs. [Graph consumers](system.md) and
source applications use the same canonical records.
