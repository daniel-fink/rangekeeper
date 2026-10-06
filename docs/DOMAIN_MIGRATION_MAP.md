# Domain migration map and Python interface contract

**Legacy isolation, 2026-10-06:** held Python code is now in `rangekeeper.legacy`,
predecessor tests in `src/tests/legacy`, and excluded C# code in `grasshopper/legacy`.
Old public paths have no aliases. See [the boundary and current checks](LEGACY_ISOLATION.md).
The Windows gate remains open; earlier Turn 4 results below describe the preceding wheel.

**Turn 4 update, 2026-10-06:** [Permitted legacy retirement](FULL_MIGRATION_TURN4.md)
removes the superseded numerical/presentation modules and narrows optional
dependencies. The paired Turn 3 checkpoint is pushed: RK `305f3ff`, Projects
`6146ad2`. Turn 4 is uncommitted. [Current acceptance](research/full-migration/turn4/BASELINE.md)
records 1,058 passing local tests, seven walkthroughs and all three real source
builds. The [remaining retirement register](research/full-migration/turn4/RETIREMENT.md)
holds old graph/Measure/Speckle API and excluded C# code for the Windows connector
gate. Full retirement is not complete. Hypar is retired; Browser/outliner is on hold.
Dated checkpoints below remain historical and do not override this current state.


**Turn 2 update, 2026-10-06:** [Temporal equations, scenarios and policies](FULL_MIGRATION_TURN2.md)
now use Model/Specification 0.5.0 and Run 0.2.0. `ValueReference` addresses scalar
Values or owner-local Movement keys. The canonical calendar package is `duration/`;
`temporal` has no public alias. Finite Flow formulations, captured scenario replay,
exogenous declarative policies and the four numerical walkthroughs are implemented.
See [verification](research/full-migration/turn2/README.md) and the
[upgrade guide](LEGACY_UPGRADE_GUIDE.md). Turn 3 completes remaining consumers and
integrations; Turn 4 retires obsolete code after their acceptance gates.
The dated checkpoint descriptions below remain historical context.

**Movement naming, 2026-10-06:** the current API uses `Movement` and
`Flow.movements`. See the [naming contract](FULL_MIGRATION_TURN1.md#movement-naming)
for the Python/wire-format change and upgrade requirements.

**Flow semantics update, 2026-10-06:** Flows no longer carry semantic kinds or
basis. The overall model logic owns their meaning and selects operations; units,
dates, alignment and missingness remain checked. See the
[current contract](FULL_MIGRATION_TURN1.md#flow-semantics-and-explicit-operations)
and [verification](research/full-migration/flow-semantics/README.md).

**Full migration update, 2026-10-04:** [Turn 1 foundations](FULL_MIGRATION_TURN1.md)
implements Model 0.4.0 rich properties and Flow Values, `model.duration`,
`temporal`, `calculations`, detached dataframe adapters, and explicit Graph conversion.
The basic DCF notebook, financial test model and synthetic source workflows migrated.
Read the [upgrade guide](LEGACY_UPGRADE_GUIDE.md) and [verification](research/full-migration/turn1/README.md).
Turn 2 is implemented; see the current contract and verification linked above.
Turns 3–4 finish remaining consumers and retire old modules. The six-checkpoint
history below remains the scalar/core work record; full migration is not complete.

**Expanded review:** [Full migration review](FULL_MIGRATION_REVIEW.md) now covers
all remaining older modules, temporal/numerical redesign, consumer proof and
upgrade guidance. Its [symbol inventory](research/full-migration/SYMBOLS.md)
expands the earlier grouped numerical row; proposed APIs remain subject to review.

**2026-10-03 update:** [Step 6C/6D](CONSUMER_MIGRATION.md) is implemented.
The responsibility inventory below retains its Step 1 baseline; current consumers
use `table`, `adapters`, and `workflow`, with `WorkflowResult.model`. External
consumer migration (6E) and old-domain retirement (6F) remain.

Status: Step 1 design and baseline completed 2026-10-02. This is the recommended
implementation contract for Steps 2–4. Work units 2A/2B are now implemented;
see [record boundary](RECORD_BOUNDARY.md) for working APIs and verified limits.
Work units 3A/3B are also implemented; [domain APIs](DOMAIN_CORE.md) records the
working facade/resolver interfaces and their bounded semantics.
[Run/storage](RUN_AND_STORAGE.md), [scalar execution](SCALAR_EXECUTION.md) and
[Model-backed graph operations](GRAPH_MODEL.md) are now implemented. Those guides
record current APIs; remaining consumer interfaces below are migration contracts. Read together with
[the observed baseline](research/domain-migration/BASELINE.md), the
[work plan](DOMAIN_MIGRATION_PLAN.md), and [architecture](LIBRARY_ARCHITECTURE.md).
The baseline inspected 93 Python modules, seven walkthrough notebooks, and the
available Mandarin/East Whisman consumer references. Live services, external
project execution, and Rhino/Grasshopper remain unverified.

## Decisions

1. LinkML owns fields and variants. Generate a shared native Python bundle for
   interoperability checks and a shared immutable record projection for runtime
   access. Both derive from the same Model/Specification/Run import bundle; neither
   is independently authored. Keep native LinkML construction out of normal imports.
2. Handwritten `Model`, `Specification`, and `Run` facades contain immutable generated
   records. Nested Entity, Value, Metadata, Expression, etc. are generated immutable
   records, re-exported from their domain modules. Do not write a parallel class
   hierarchy or a wrapper for every schema class.
3. Handwritten functions implement local lookup, validation, composition, diff,
   and units. Document facades supply identity and revision behavior. A graph View
   references a Model plus selection IDs. It does not own a second copy of domain data.
4. Use native `UUID` values at public typed boundaries; serialized references remain
   UUID strings. UUID lookup never falls back to code/name lookup. Assembly eligibility
   for Entity references follows the schema; storage remains in `System.assemblies`.
5. `Model.metadata.id` is revision identity. Do not introduce another `Revision`
   envelope or use Python object identity as a cross-revision reference contract.
6. Keep source-building WorkflowSpec, mathematical Specification, and finalized Run
   distinct. Keep graph reduction over recorded quantities distinct from governing
   mathematical aggregation declared by Expressions.
7. Preserve useful algorithms, not obsolete field meanings. The first scalar core
   does not represent arbitrary Features, Flow/Stream payloads, or executable callbacks.

This refines the earlier illustrative API: nested records expose schema fields;
`characteristics.value(characteristics, key)` supplies local lookup rather than
handwriting behavioral Entity/Characteristics wrapper classes. `Model.revise()` is
explicit about revision creation. Generation is a small maintained tool, not an
assumption that stock `gen-python` already supplies immutable public objects.

## Current responsibilities and dispositions

Paths in this table are relative to `src/rangekeeper/` unless prefixed with `schema/`.
The [static inventory](research/domain-migration/evidence/inventory.json) records
symbol locations, imports, notebook code references, and inspected consumer hashes.

| Current responsibility and evidence | Contract mismatch / decision | Destination and disposition | Consumers, acceptance, and retirement |
| --- | --- | --- | --- |
| `graph/graph.py: Graph`, `_catalog.py: Catalog` | Graph lacks Metadata/System/Formulations; lookup checks canonical Python instances. Code-keyed catalogues cannot supply revision scope. | **Replace** container with `model.Model`; **adapt** indexing into `model/_index.py`. | Views, updates, all adapters/workflows; identity and graph tests. Retire old Graph only after these consumers migrate. |
| `graph/entity.py`, `relationship.py`, `assembly.py` | Assemblies currently occupy the Entity collection; serialized endpoints and inheritance must follow LinkML. | **Replace** record definitions with generated Entity/Relationship/Assembly; **retain** membership algorithms after adaptation. | Views, persistence, C# source authoring. Verify separate storage, eligible endpoints, overlap/cycles and no duplicate ownership. |
| `graph/characteristics.py: Label, Measurement, Feature, Characteristics` | Measurements keyed by Measure code; Features accept arbitrary content. Values need UUID plus owner-local key and a supported kind. | **Replace** with generated Labels/Values; `model/characteristics.py` owns lookup helpers. | Reduction, tables, YAML construction, evidence targets. Verify two Values per Measure and unresolved versus zero. No silent Feature-to-Value conversion. |
| `graph/definitions.py`, `taxonomy.py`, `classification.py` | Current reference resolution uses live instances; new Definitions also contains Functions. | **Replace** fields; **adapt** catalogue lookup/hierarchy checks into `model/definitions.py` and validation. | Entity/Label validation, query/filtering. Retire instance-check contract after UUID scope tests pass. |
| `measure.py: Measure, QuantityKind, AggregationRule, Index` | Schema Measure has unit text, no implicit aggregation rule; Quantity is explicit magnitude/units. Existing count/currency conventions need separation. | **Replace** domain shape in `model/measure.py`; **adapt** numerical unit operations in `units.py`; **retain** legacy unit API until numerical consumers migrate. | Numerical modules/notebooks, graph reductions. New core must not import old Measure. Test incompatible currencies/count dimensions and explicit reducers. |
| `graph/provenance.py: Source, Claim, Fact, Provenance, locations` | Current Facts target object instances; provenance derives catalogues from live references. New records have UUID references and canonical collections. | **Replace** fields; **adapt** Fact/Claim checks and source-location traversal into `model/provenance.py`. | Ingestion, workflow reviews, output publication. Verify typed Fact targets, claim cycles, selected-content agreement for supported targets. |
| `graph/revision.py: Revision, Diff, Delta`; `update.py: Update, _Candidate` | Separate graph revision envelope and enumerated legacy collections omit mathematics. | **Replace** revision envelope; **retain/adapt** atomic candidate pattern and UUID comparison. New `model/update.py`, `model/diff.py`. | Mandarin equivalence and Graph tests. Require complete-document validation and preserved input before retirement. |
| `graph/adapter/json.py` | Registered-class `rk.graph` persistence is not Model interchange; supports payloads outside current schema. | **Replace** new-document codec in `io`; **retain** old codec for old consumers during migration. | Graph JSON tests, workflow exports, external comparisons. No auto-detection as Model and no implicit conversion. |
| `graph/view.py` | Useful selection/filter/traversal API, but tied to Graph and its instance checks. | **Adapt** to Model; retain selection-by-ID and immutable results. | Table, visualization, reductions. Verify membership, roots/leaves, direction and filtered endpoints. |
| `graph/reduction.py` | Good Reduction/Aggregation/Coverage separation; `by_measure` implies reducer from Measure and unique measurement. | **Adapt** to explicit Value selector and reducer; retain coverage distinction. | Tables, project totals. Verify missing data/known subtotal and no implicit zero or arbitrary Measure selection. |
| `graph/table.py` | Useful Row/Table projection, but measurements indexed by Measure and private View access. | **Adapt** Value columns and public graph traversal interface. | CSV, pandas, viewer/review outputs. Verify row identity, scalar units, missing cells and stable presentation order. |
| `graph/operation.py`, `_structured.py`, `_encoding.py` | Operation/Outcome is an ingestion invocation contract, not mathematical Run. Frozen-data helpers are useful but format-specific. | **Retain/adapt** under workflow; reuse audited freeze/encoding principles in private record support. | Document/ingestion tests. Do not merge invocation identity with Run revision identity. |
| `schema/checks/*_contract.py`, `specification_composition.py` | Valuable semantics, but direct imports/dicts and bounded checks are research/conformance entrypoints. | **Adapt** into domain validation and composition; existing scripts become callers. | Seven schema suites. Preserve negative cases, identify unsupported unit/content checks, avoid two validators drifting. |
| Root `__init__.py`, `validate.py` | Root eagerly imports measure/graph; includes plotting helper and class-patching decorator. | **Adapt** explicit lightweight domain exports and lazy optional modules; **retain** legacy helpers until actual consumers move. | Import smoke tests and notebooks using `update_class`. New core depends on neither helper. |
| `api.py: Speckle` | V2 service integration in generically named module; old domain conversion. | **Defer/adapt** to `adapters/speckle` after scalar core. | Live API tests, design notebooks, Grasshopper. Unverified until service/host acceptance. |
| `graph/adapter/{excel,document,csv,pandas,cytoscape,visualization}` | Format parsing useful; domain exporters/projectors reference Graph. | **Retain** format readers; **adapt** projections/construction, later move to `adapters`. | Existing adapter tests. Do not move directories before interfaces are exercised. |
| `graph/workflow/{catalog,runtime,composition,...}` | Closed operation catalogue and explicit wiring are useful; composition builds Graph measurements/features. | **Retain** operation wiring/Evidence; **adapt** Model construction in Step 6. | Mandarin/East Whisman, workflow suites. Feature-rich inputs require explicit later contract work. |
| `flux`, `duration`, `distribution`, `extrapolation`, `projection`, `formula`, `dynamics`, `segmentation`, `space`, `policy` | Numerical/presentation behavior is not schema record shape; pandas Flow coerces numeric content; Policy contains callbacks. | **Retain** numerical algorithms; **defer** rich payload and symbolic bridges. | Numerical tests and seven notebooks. Do not convert callbacks into serialized mathematics. |

## Factoring and naming contract

- Files name a coherent concept or operation; use `expression.py`, `formulation.py`,
  `composition.py`, `validation.py`, `diff.py`. Use `formulations/valuation.py` only
  for helpers constructing mathematics. No generic manager/service/helper modules.
- Classes require owned state: document, view, composition result, store, executor.
  Use functions for validation, conversion, comparisons, local lookup, and traversal.
- Methods describe object behavior: `entity`, `find_entities`, `revise`, `filter`,
  `successors`. Properties expose content; they never perform IO or execution.
- Preserve operation/result separation: `Reduction`/`Aggregation`, saved
  `Specification`/derived `Composition`, executor/finalized `Run`.
- UUID lookups raise on missing/wrong-kind targets; `find_*` returns a tuple,
  possibly empty; owner-local optional lookups return `None`. Do not overload a
  string as a UUID, code, path, or object according to runtime guesses.
- Keep keyword-only selectors and construction arguments. Generated signatures
  preserve required fields, optional omission, enum types, and useful type hints.
- Cross-module private access is not the interface. Extract shared traversal into
  `graph/traversal.py`; provide supported lookup on Model and View. Private indexes
  belong to Model, not algorithms that mutate/reconstruct them independently.
- Public schema fields use schema names. Convenience `Model.id` forwards
  `metadata.id`; it creates no second identifier. No generic inheritance hierarchy
  combining Model/Specification/Run behavior beyond private record plumbing.

The subsequent [validation refinement](DOMAIN_CORE.md#composable-validation) is
implemented: `validate.py` owns argument guards, `_validation.py` owns generic semantic
invariants and stage orchestration, and domain modules own their rule composition.
`Scope` is lookup data; expression inference and predicate validation are functions
with explicit scope dependencies. The shared helpers import no domain behavior.

## Concrete module ownership

This is a creation sequence, not an instruction to move the existing tree at once.

| Module/package | Public symbols / responsibility |
| --- | --- |
| `_schema/native.py`, `_schema/records.py`, `_schema/slots.json`, `_schema/manifest.json`, `_schema/jsonschema/` | Generated stock LinkML types for conformance; immutable types for normal use; generated slot metadata, closed validators, source/version manifest. Private. |
| `_records.py`, `_schema/validation.py` | Shared freeze/thaw, presence tracking, primitive conversion, canonical serialization; lazy structural-validation entrypoints. Private. |
| `metadata.py`, `diagnostics.py`, `errors.py` | Generated `Metadata`; handwritten `Issue`, `ValidationReport`; typed library exceptions. Run's schema Diagnostic remains a separate generated record. |
| `model/model.py`, `model/_index.py` | `Model`; private canonical UUID/owner/type indexes. |
| `model/{entity,relationship,assembly,system,definitions,measure,characteristics,expression,formulation,provenance}.py` | Re-export relevant generated nested records; handwritten lookup functions where useful. `measure.py` exports Measure/Quantity; characteristics exports Label/Value/Characteristics. |
| `model/{validation,update,diff}.py` | `validate`; `Update` and revision construction; `Diff`, `Change`, `between`. |
| `specification/{specification,composition,validation}.py` | `Specification`; `Composition`, `compose`; `validate`. |
| `run/{run,validation}.py` | `Run`; `validate` finalized records against referenced documents. |
| `references.py` | Read-only `SpecificationResolver` and extended `DocumentResolver` protocols, containing only typed lookup signatures. Imports document types under TYPE_CHECKING; no storage code. |
| `io/{json,yaml,store,memory,directory}.py` | Format codecs; writable `RecordStore`; `MemoryStore`, `DirectoryStore`. |
| `units.py` | `UnitSystem`, `default_units`; no schema authority or solving. |
| `graph/{view,traversal,reduction,table}.py` | Model-backed View and graph algorithms, migrated after core. |
| `execution/`, `formulations/` | Step 5 implements preparation/compiler/evaluator/acceptance/publication/backend orchestration; see [scalar execution](SCALAR_EXECUTION.md). Richer mathematical construction remains future work. No execution implementation was part of Steps 2–4. |
| Root and package `__init__.py`, `py.typed` | Small explicit public exports, lazy optional integrations, packaged typing. |

Dependency order: generated records/private record support → document facades and
semantic operations → IO/graph/workflow/execution consumers. `references.py` is a
leaf typing contract. IO may call domain validation; domain code accepts a resolver
and never imports an IO implementation. Domain validation may use `units`; unit
operations import Pint lazily. Generated records and structural validation do not
import handwritten domain facades. This eliminates generated/public class registries
and avoids per-field dynamic `__getattr__` dispatch.

## Generated record decision and evidence

The [isolated probe](research/domain-migration/evidence/record_boundary_probe.py)
generated 50 classes from the complete import bundle. All 14 selected document
fixtures passed structural validation before and after exact data round trips.
Every declared field in those fixtures was accessible. Nested mappings/sequences
and opaque Claim content were protected; input/export mutation did not affect the
snapshot. Explicit constructors, UUID access and evaluable type hints worked.
Stock generated LinkML metadata remained mutable, as expected.

The initial projection incorrectly treated `Content` as a structured record; the
corrected generator detects `class_uri: linkml:Any` and treats it as opaque JSON.
The failure and corrected result are retained. Opaque `id` keys must never enter
domain identity indexes. See [results](research/domain-migration/evidence/record-boundary-results.json).

Production generation rules are fixed as follows:

- Generate `native.py` once from a shared import bundle using pinned LinkML 1.11.1.
  Generate closed schemas with an explicit top class, avoiding ambiguous tree-root
  inference. Treat stock native classes as a conformance/interoperability surface.
- Generate explicit immutable classes and constructors from induced LinkML slots.
  Required fields are required keyword arguments; optional arguments default to a
  private omission sentinel. Conditional requirements stay in structural validation.
  Required slots do not become optional merely because the prototype allowed it.
- Include inherited slots. Use schema inheritance where it applies (Assembly is an
  Entity); generated field ownership remains schema-derived. Generate enum annotations
  as Literal unions and structured alternatives as explicit unions. References to
  identified records expose UUID, embedded records expose immutable generated types.
- Snapshot storage is a recursively frozen, detached JSON-compatible tree. Public
  collections are tuples/read-only mappings; UUID conversion is schema-directed.
  Opaque JSON content preserves strings, numbers, booleans, nulls and list order.
- Public constructors validate local structural shape. Complete document factories
  additionally run document semantics. Child construction cannot validate ownership
  until attached to a complete document. No Python coercion of strings/bools to numbers.
- `from_data` and `to_data` preserve field presence: omitted, explicit null, and
  empty collection remain distinct representations. Attribute access returns None
  for absent optional scalar/record fields and an empty tuple/read-only mapping
  for absent collections. Keyed LinkML inline dictionaries retain both shorthand and
  expanded serialized forms; see the implemented record-boundary guide.
  `has_field(name)` makes presence explicit; reject unknown field names.
- Accept finite JSON int/float magnitudes; reject bool as numeric, NaN/Infinity and
  arbitrary Python objects. Reject duplicate object keys in codecs. Native UUIDs
  accepted by typed constructors serialize as canonical lowercase UUID strings.
- Thin root facades hold these records plus derived indexes. They do not redeclare
  the field schema. Nested records are public aliases of generated immutable types.
- Generate source deterministically, omitting generation timestamps; fingerprint
  schema inputs, generator version/options, and outputs. Check in packaged artifacts;
  verify regeneration in CI. Ship typing information and test static example checking.

The Step 1 probe established feasibility and deliberately omitted
semantic entrypoints, stores, index caching, constructor validation, complete union
annotations, and a static checker run. Generated constructors, shared bounded validation and static checking are now
implemented and verified in [Turn 1](research/domain-migration/turn1/README.md);
Model/Specification facades and indexes are now implemented in [Turn 2](DOMAIN_CORE.md);
[Turn 3](RUN_AND_STORAGE.md) now implements Run, codecs, stores and final public exports.

## Public interface contract

In the signatures below `Data = Mapping[str, JSONValue]`; `Document` means the three
root facades; `EntityLike = Entity | Assembly`; generated nested types are immutable.
`Unset` denotes omitted operation arguments, not a serialized schema value.
All collections returned by domain operations are immutable. None initializes a
solver. Model/Specification operations are now implemented as documented in
[DOMAIN_CORE.md](DOMAIN_CORE.md); [Turn 3](RUN_AND_STORAGE.md) implements the Run/IO signatures.
Specification exposes generated fields through `.record`; Composition also retains
immutable `.contributions` snapshots. `SpecificationResolver` provides the two investigation
lookups; `DocumentResolver` extends it with the implemented Run lookup.

### Shared construction, validation and errors

| Signature | Result, validation and effects |
| --- | --- |
| `Model.from_data(data: Data, *, units: UnitSystem = default_units) -> Model` | Copy/freeze; validate structure, schema version, complete identity/reference/ownership semantics and supported recorded units. History lookup is optional, never needed to interpret current Model. No IO. |
| `Specification.from_data(data: Data) -> Specification` | Validate structure/local consistency; allow partial contributions and unresolved external document references. Composed completeness is a separate operation. |
| `Run.from_data(data: Data) -> Run` | Validate structure/local status/report consistency. Cross-document/output checks require explicit `run.validation.validate`. Loading is not certification of numerical claims. |
| `document.to_data() -> dict[str, JSONValue]` | Detached mutable plain data, preserving optional presence and mathematical order. |
| `Model.create(*, metadata: Metadata, definitions: Definitions|Unset=UNSET, system: System|Unset=UNSET, provenance: Provenance|Unset=UNSET, units: UnitSystem=default_units) -> Model` | Typed authoring convenience delegating to the same validated construction path. Metadata/UUID creation is explicit. Specification/Run use their generated root-record constructors plus `from_data`, avoiding redundant hand-maintained constructors. |
| `model.validation.validate(model: Model, *, units: UnitSystem=default_units) -> ValidationReport` | All Model semantics; no solving. Constructor failure raises the same report. |
| `specification.validation.validate(composition: Composition, *, resolver: SpecificationResolver, units: UnitSystem=default_units) -> ValidationReport` | Pin/model scope, eligible roles, completeness, references, and units. No backend capability or feasibility claim. |
| `run.validation.validate(run: Run, *, resolver: DocumentResolver) -> ValidationReport` | Resolve pinned records; check outputs, lineage, report requirements and batch accounting. Reuse bounded scalar checks without claiming an independent numerical solve. |

`ValidationReport.issues` is a tuple of `Issue(code, message, document_id, path)`;
`valid` is true when empty, and `raise_if_invalid()` raises `ValidationError(report)`.
These are programmatic diagnostics, not a duplicate of schema-defined Run Diagnostic.
Use stable issue codes and JSON-pointer-style paths. Input decoding failures raise
`DecodeError`; unsupported versions `UnsupportedVersionError`; missing UUIDs
`MissingReferenceError`; wrong-kind references `ReferenceTypeError`; conflicting
identities/content `IdentityConflictError`/`RevisionConflictError`; invalid unit
operations `UnitError`. Filesystem failures retain `OSError` and cause context.
Failures return no partially constructed public document.

### Model and local access

| Signature | Behavior |
| --- | --- |
| `Model.id: UUID`, `.metadata`, `.definitions`, `.system`, `.provenance` | ID forwards metadata. Optional envelope fields retain schema optionality. Read-only. |
| `Model.entity(id: UUID) -> EntityLike` | Includes canonical Assemblies without duplicating their stored occurrence. Missing/wrong-kind raises. |
| `Model.relationship(id: UUID) -> Relationship`, `.value(id: UUID) -> Value`, `.formulation(id: UUID) -> Formulation` | Resolve in this Model only. No predecessor search. |
| `Model.owner_of(id: UUID) -> UUID|None` | Owning identified declaration, or None for records owned by anonymous root containers. Unknown ID raises. |
| `Model.find_entities(*, code: str|None=None, name: str|None=None, classification: UUID|None=None) -> tuple[EntityLike,...]` | AND matching, exact classification, includes Assemblies, stable document encounter order. Hierarchy expansion is an explicit graph/query operation. |
| `characteristics.value(items: Characteristics|None, key: str) -> Value|None` and `label(...) -> Label|None` | Owner-local lookup; absent container/key returns None. Names are case-sensitive. |
| `definitions.measure(items: Definitions|None, id: UUID) -> Measure`; `find_measures(items, *, code: str) -> tuple[Measure,...]` | Identity versus catalogue code kept separate. Similar functions for Taxonomy/Classification/Function. |
| `provenance.fact_for(model: Model, target: UUID) -> Fact|None`; `locations(model: Model, claim_id: UUID) -> tuple[Location,...]` | UUID lookup and cycle-checked provenance traversal within the Model. |

Repeated lookups use a private index; they need not promise `is` equality. Equality
of declarations is not equality of revision context. An external reference carries
document UUID plus target UUID whenever the contract requires both.

### Revision, comparison and storage

For the first core use complete-section replacement, retaining the current atomic
candidate pattern. Avoid a new generic patch language or a field per possible
add/remove mutation. Fine-grained authoring helpers can build replacement sections.

- `Update(*, definitions: Definitions|Unset=UNSET, system: System|Unset=UNSET,
  provenance: Provenance|Unset=UNSET, metadata: Metadata|Unset=UNSET)` is a Python
  operation request, not another serialized schema. Omitted sections are retained;
  supplied empty containers clear their content. No cascading deletion by default.
- `Model.revise(update: Update) -> Model` builds privately, creates fresh metadata
  UUID/previous=current ID while retaining descriptions/version, and fully validates.
  Supplied metadata must have a new ID, current previous ID, and supported unchanged
  schema version. Reject an update that changes no domain/descriptive content.
  Removing something still referenced fails. Do not silently repair provenance.
- Specification revision creation is `Specification.revise(replacement: SpecificationRecord)
  -> Specification`: preserve the proposed complete content, require new ID and
  previous=current ID, validate locally. Run is finalized: no public revise method.
  Schema migration is a separate operation, not a side effect of revise.
- `diff.between(before: Model, after: Model) -> Diff` returns `added`, `removed`,
  `modified` declaration UUIDs plus path-level `Change(path, before, after)` entries
  for embedded/envelope changes. Do not require lineage to compare two documents;
  do not emit an executable patch or silently merge them.
- `DocumentResolver.load_model(id: UUID) -> Model`, `.load_specification(id) ->
  Specification`, `.load_run(id) -> Run` are the read-only protocol. Wrong kind is
  distinct from missing. Resolution never reads from a network implicitly.
- `RecordStore` adds `put(document: Document) -> UUID`. `MemoryStore()` and
  `DirectoryStore(root: Path)` implement it. No update/delete API. Creating a
  DirectoryStore object performs no write; `put` creates storage as needed.
- Store filenames are UUID-based; retain an explicit envelope `{kind, document}`
  only inside storage, never in Model interchange. On read verify requested UUID,
  kind and version. A repeated identical revision is idempotent; changed content
  under an existing ID raises `RevisionConflictError`, including a different kind.
- Equivalence canonicalizes mapping key order, UUID spelling in typed fields, and
  unordered schema collections. Preserve duplicate multiplicity, all declared
  ordered lists (operands, parameters, arguments, criteria, traversal, objectives,
  Run trace), and every opaque-content list. Preserve absence/null/empty and numeric
  representation; do not collapse these for revision equivalence. Generate the
  ordered-slot table from LinkML annotations. No broad recursive list sorting.
- Directory publication writes a same-directory temporary file, flushes/fsyncs,
  then uses an atomic no-overwrite hard link to the final UUID filename and removes
  the temporary name; fsync the directory where supported. If the destination
  exists, compare it. A crash cannot expose a partial final record. Support local
  filesystems with these primitives; fail explicitly on unsupported operations.
  Do not substitute an overwrite rename. Test concurrent identical/conflicting puts.
- `put` revalidates shape/local document rules. Model self-contained semantics must
  pass; partial Specifications may still reference documents not yet stored. A Run
  additionally passes cross-document validation against the store before publication,
  so its children/outputs/attempted Specification must already resolve. Invalid puts
  leave storage unchanged.
- Multi-document transaction/publication is not claimed by `put`. Execution later
  stores validated outputs before its finalized Run, so a published Run cannot
  reference an output not yet stored. Crash recovery may leave unreferenced outputs.

### Composition, codecs and units

| Signature | Contract |
| --- | --- |
| `compose(root: Specification, *, resolver: SpecificationResolver) -> Composition` | Resolve includes, verify kinds/versions/cycles, contribute each revision once, reject independent duplicated requirements even when equal. Batch is not one composition. No defaults, overrides, execution or writes. |
| `Composition.root_id`, `.model_id: UUID|None`, `.contributors: tuple[UUID,...]`, `.requirements`, `.sources` | Immutable effective requirements and source paths; allow a partial contribution. No new Metadata and no store/codec support for Composition. `requirements` uses generated field types; its combination is derived state, not an authoritative schema. |
| `json.loads(text: str, *, kind: type[D]) -> D`, `.dumps(document: Document) -> str`, `.read(path: Path, *, kind: type[D]) -> D`, `.write(document, path: Path) -> Path` | Explicit root kind, strict JSON and document factory validation. Read/dump preserve encounter order; canonical storage comparison is separate. `write` creates a new file atomically and rejects existing destinations. |
| Corresponding `yaml` functions | Same contract, safe loader with duplicate-key rejection, no custom executable tags. Normalize only schema-typed date/time/UUID values; preserve opaque content. YAML dependency remains an optional IO extra. |
| `UnitSystem.compatible(left: str, right: str) -> bool`; `.convert(quantity: Quantity, *, to: str) -> Quantity` | Validate finite magnitudes, parse known units and return a new Quantity. Unknown/malformed units raise. Incompatible conversion raises. No in-place conversion or exchange-rate inference. |

Default units use a private lazy Pint registry: standard physical units, dimensionless,
year, squaremeter/squarefoot aliases, dwelling as an independent count dimension,
and an independent dimension for each supported ISO currency code. AUD/USD are
incompatible without an explicitly modelled exchange relation. No locale-selected
currency or globally mutated old `measure.Index.registry`. Currency names/aliases
come from a pinned registry bundle. Retain existing legacy conventions for old
numerical consumers until their explicit migration. `UnitSystem` configuration is
immutable after construction and has an implementation/version identifier.

### Graph/execution interface boundary

`View(model, *, entities=None, relationships=None, assembly=None)` retains the existing
selection modes with UUID inputs and references one immutable Model. `filter` returns
a new View; `entity(id)`, `predecessors(id)`, `successors(id)`, `entities_in(assembly,
recursive=False)` and `containing_assemblies(...)` own traversal behavior. Membership
and relationship traversal remain separate. `filter` classification matching is exact;
include descendants only through an explicitly supplied classification set.

`Reduction` exposes `apply(view) -> Aggregation`; `View.aggregate(reduction)` delegates.
`by_value(key: str, *, reduce: Callable, contributors: Callable|None=None,
require_value: bool=False) -> Reduction` chooses one local Value per Entity. Reuse
Coverage, missing/known-subtotal distinctions, and arborescence preconditions.
Do not infer a reducer from Measure. Unit-aware sum is an explicit supplied reducer.
These are record-inspection utilities, not a substitute for expression mathematics.

The future executor consumes a pinned Model, validated Composition, and immutable
unit settings; it receives `DocumentResolver`/`RecordStore` through injection.
Prepared equations, backend state, candidate quantities and acceptance results are
runtime-only objects. The acceptance evaluator traverses original expressions and
must not import the Pyomo adapter. `Executor.execute(specification) -> Run` is now
implemented in [Step 5](SCALAR_EXECUTION.md), separately from the Step 2–4 scope.

## Usage contracts

End-to-end examples below combine implemented domain/IO/root APIs with graph APIs
that remain design targets; see the implemented guides for runnable core examples.
For executable Turn 2 examples, use [the domain API guide](DOMAIN_CORE.md).

```python
from uuid import uuid4
import rangekeeper as rk
from rangekeeper.model import Model, System, Entity, Characteristics, Value
from rangekeeper.model import characteristics
from rangekeeper.model.update import Update
from rangekeeper.metadata import Metadata
from rangekeeper.io import json, MemoryStore
from rangekeeper.specification import compose

# Typed nested records come from generated fields; use a supported schema version.
entity = Entity(id=uuid4(), code="A", characteristics=Characteristics(values=()))
model = Model.create(
    metadata=Metadata(id=uuid4(), schema_version="0.4.0"),
    system=System(entities=(entity,)),
)
loaded = json.loads(json.dumps(model), kind=rk.Model)
assert loaded.entity(entity.id).code == "A"
assert characteristics.value(loaded.entity(entity.id).characteristics, "rent") is None

# New complete section, unchanged declaration ID, fresh Model revision ID.
renamed = Entity(id=entity.id, code="Apartment-A", characteristics=entity.characteristics)
revised = loaded.revise(Update(system=System(entities=(renamed,))))
assert revised.id != loaded.id
assert revised.metadata.previous == loaded.id

store = MemoryStore()
store.put(loaded)
store.put(revised)
assert store.load_model(loaded.id).entity(entity.id).code == "A"
```

```python
# Against the valuation fixture and all its referenced contributors:
model = json.read(model_path, kind=rk.Model)
spec = json.read(specification_path, kind=rk.Specification)
store.put(model)
for contribution in included_specifications:
    store.put(contribution)
store.put(spec)
composition = compose(spec, resolver=store)
rk.specification.validate(composition, resolver=store).raise_if_invalid()
value = model.value(rent_value_id)  # recorded quantity does not assign a solve role
view = rk.graph.View(model, assembly=assembly_id)  # implemented in Step 6A
children = view.successors(parent_id)
```

## Consumer migration placement

| Consumer and observed dependency | Timing/change | Acceptance and retirement condition |
| --- | --- | --- |
| Seven schema scripts and existing fixture corpus | **Before scalar**: call shared structural/semantic implementation; remove duplicate semantic copies once parity holds. | Existing seven suites plus new record/store cases; preserve intended invalid outcomes, not permissive native construction. |
| Root imports and new domain clients | **Before scalar**: explicit Model/Specification/Run and domain records; avoid importing old graph/measure when loading new core. | Clean installed-wheel import with optional extras absent; meaningful static example checking. Old root numerical exports remain until consumers move. |
| Existing graph tests, views, reductions, tables | **After core**, required for migrated consumers, not first solve. Update lookup and aggregation semantics explicitly. | 71 immutable-graph, 37 scoped-code, 4 unresolved tests are characterization evidence; adapt expectations deliberately and add new schema cases. |
| JSON/CSV/pandas/viewer adapters | **After core**: separate canonical document persistence from projections. | 20 existing Graph JSON tests, 39 adapter cases (one current failure), two Cytoscape cases; new Model round trips and projection tests. Old JSON codec stays for old consumers. |
| Document/Excel/ingestion capabilities | **Retain reading**, migrate domain binding later. | 17 document, 31 Excel, 46 ingestion, 13 tabular cases. Preserve source fingerprints and evidence addresses. |
| Source workflows and closed catalog | **Step 6**: Model construction, UUID references, explicit Value keys, new output codec; keep workflow-specific specification and invocation results. | 91 current workflow-family tests plus project fixtures. Retire old composition after explicit Feature policy is accepted. |
| Mandarin and East Whisman | **Step 6 / richer-content gate**. Imports Graph JSON, provenance, workflow; Mandarin also Diff and Feature. Shared project repo inspected at `5725cc02748ace15e390c8dcea2c5d69185d67c9`, requires Python 3.13 for Mandarin. | Project test/equivalence suites and reviewed exports in their own environment. Not executed here. Migrate persisted comparisons intentionally; do not assert byte equality across different interchange formats. |
| Seven walkthrough notebooks | **After relevant consumers/numerics**. Two use Speckle, others use Flux/duration/units; several use root `update_class` and obsolete distribution/graph calls. | Clean-kernel runs with declared data/services; compare numerical outputs. Inspection only; no notebook has been certified by this step. |
| Grasshopper C# | **Later integration**. Entity inherits Speckle Base; model references Speckle 2.18.0. | Pure cross-language Model fixture tests plus Rhino/Windows authoring acceptance. Current README's Snapshot/Phase 6 description is historical; new Model contract supersedes it. No host verification here. |
| Hypar directory | **Retired and removed**. No Git-tracked source existed; ignored build/editor residue was removed at the user's request. | No migration or acceptance task. Preserve the [removal record](research/full-migration/hypar-removal/README.md) and earlier research. |
| Root Speckle API | **Later integration**; legacy conversions used by design notebooks. | Three live tests excluded from baseline. Require available service fixtures and explicit transport environment. |
| Numerical modules, formula examples, Policy | **Retain initially**; bridge later. | 58 numerical/unit/module cases passed, one residual expectation failed. Root class-patching helper remains until notebooks/examples are migrated; no new core use. |

The external inventory excludes archived Mandarin implementations from the active
migration queue. Their existence does not require reviving those APIs. Downstream
inspection is bounded to the available projects, not a claim of exhaustive private
consumer discovery.

No converter is required for the first core: it loads current Model fixtures.
For active projects later, convert scalar Measurements to locally keyed Values only
with an explicit key mapping. Preserve provenance meaning, not just numbers. Generic
Features and rich pandas payloads cannot be silently dropped, stringified, or placed
in opaque Claim content to pretend they are supported Values. Their migration stays
blocked on the appropriate later contract; the scalar checkpoint is independent.

## Ordered implementation work units and acceptance

| Unit | Files/responsibilities | Required acceptance / removal condition |
| --- | --- | --- |
| 2A Generate artifacts | `tools/schema/` generator, shared import bundle, `_schema` artifacts, private record support, package data/typing configuration | Deterministic regeneration; all 50 imported classes accounted for; required/optional/union/enum annotations; constructor and duplicate-key rejection; exact presence and 14 fixture round trips; static typing examples; no handwritten fields. |
| 2B Shared validators | Domain validation functions and typed reports; schema scripts delegate | Seven suites retain intended outcomes. Separate structure/local semantics/composed completeness/backend/acceptance. Remove old duplicate routines only after shared callers pass. |
| 3A Model and references | Model facade, indexes, local lookup/provenance helpers, UnitSystem, Update/Diff | Multiple Values per Measure; Assembly single ownership; nested/local formulations; UUID/type/owner errors; same declaration across revisions; immutable nested data; unit/currency checks; no old Graph dependency. |
| 3B Specification | Facade, read-only resolver, composition and validation | Diamond includes once; independent duplicate requirements conflict; role disjointness; partial records valid; exact Model pin; cycles/wrong kinds rejected; contributor sources preserved; batches not flattened. |
| 3C Run and stores | Run facade/validation, codecs, both stores, canonical comparison | Status/report and cross-document fixtures; missing outputs and wrong kinds rejected; omitted/null/zero/false preserved; ordered lists not sorted; conflicting revision puts; concurrent writes/crash-before-publish; old revisions still load. |
| 4 Public/installed checkpoint | Root/package exports, optional dependency groups, `py.typed`, clean wheel tests and examples | Install wheel outside checkout; no repository-relative resource lookup; core import does not load Pyomo, pandas, NetworkX, plotting or Speckle; generated code imports without LinkML tooling; encode/decode works with declared core deps and YAML extra only when used. |

Production tests should be organized under domain, specification, run, IO, generation,
and import boundaries rather than mirror every helper function. Existing Graph tests
remain characterization tests until their consumer migration. Failure cases must
check transactional behavior and useful diagnostic paths, not just exception classes.

The two reproduced baseline failures are not part of these implementation units.
No core design decision is left as an option menu. Full consumer migration, rich
Values, external-service acceptance and numerical solver diagnosis remain later work.
Scalar execution and Step 6A/6B graph operations now have separate implementation evidence. No commit, push, or release was performed.
