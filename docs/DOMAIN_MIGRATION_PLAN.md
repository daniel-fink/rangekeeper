# Domain migration implementation plan

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
The [date-only correction](research/full-migration/date-only/README.md) removes
TimePoint. Period movements store coverage; a separate date is optional and records
an independent payment or observation. Dated valuation requires explicit timing
when the movement has no recorded date.
[Financial-library integration](research/full-migration/financial-library/README.md)
now delegates PV, XNPV, IRR and day counts to PyXIRR. The draft mandatory IRR
bracket is replaced by an optional initial guess.
Next is Turn 2: temporal mathematics, scenarios/policies, and their consumers.
Its opening slice is the [duration namespace migration](FULL_MIGRATION_TURN1.md#duration-namespace-migration),
recorded 2026-10-05: relocate the retained old duration implementation privately,
move `temporal/` to `duration/`, update callers and verify the installed package
before adding new consumers. This adds no implementation turn; the rename is pending.
Turns 3–4 finish remaining consumers and retire old modules. The six-checkpoint
history below remains the scalar/core work record; full migration is not complete.

**Scope update, 2026-10-03:** the full refactor now includes numerical and temporal
redesign, every supported consumer, and guidance for later legacy upgrades.
The [full migration proposal](FULL_MIGRATION_REVIEW.md) supplies the engineering
work needed for 6E. It extends the work below with behavior contracts and acceptance
checks. Daniel selected `model.duration` and `formulations/flow.py`; other new
schema/API details need technical design, not blanket user approval. No unanswered
user question currently blocks that design work.
6E/6F alone must not be reported as completion of the numerical/temporal redesign.

Status: Step 1 completed 2026-10-02. The [migration map](DOMAIN_MIGRATION_MAP.md)
records the concrete interface design and consumer sequence; the
[baseline](research/domain-migration/BASELINE.md) records current checks and limits.
The detailed work queue below is retained for traceability. Step 2 (work units 2A/2B)
is now implemented: see the [record boundary](RECORD_BOUNDARY.md) and
[Turn 1 verification](research/domain-migration/turn1/README.md). Work units 3A/3B
are also implemented: [Model/Specification APIs](DOMAIN_CORE.md) and
[Turn 2 verification](research/domain-migration/turn2/README.md). Work units 3C/4
are now implemented: [Run and storage](RUN_AND_STORAGE.md) and
[Turn 3 evidence](research/domain-migration/turn3/README.md). Step 5 is now implemented:
[scalar execution](SCALAR_EXECUTION.md) and [observed evidence](research/scalar-execution/README.md).
Step 6A/6B are now implemented: [Model-backed graph operations](GRAPH_MODEL.md).
[Step 6C/6D](CONSUMER_MIGRATION.md) now implements shared tables, presentation
adapters, and source workflows. Step 6E continues through the full migration sequence above.
[Consumer verification](research/consumer-migration/README.md): 798 Python tests
pass, one unchanged numerical baseline failure remains, and schema, static,
installed-package, and actual workflow/execution checks pass. The graph guide records the six bounded Step 6 slices.
The approved [validation factoring refinement](DOMAIN_CORE.md#composable-validation)
was implemented and verified before 3C/4; it adds no new execution work.

[Library architecture](LIBRARY_ARCHITECTURE.md) owns package responsibilities and
scalar acceptance. [Model, Specification, and Run](MODEL_SPECIFICATION_RUN.md)
and the [schema reference](../schema/README.md) own record meaning. This document
owns the implementation work breakdown and Step 1 deliverables. Earlier migration
numbering is superseded by the six checkpoints here and in the architecture plan.

## Six implementation checkpoints

| Step | Work | Exit condition |
| --- | --- | --- |
| 1. Establish the migration baseline | Inventory canonical objects, public interfaces, consumers, persistence, and tests. Specify replacement interfaces and classify replacement, adaptation, retention, and deferral. | Evidence-backed domain/consumer map, interface contracts, baseline results, and ordered implementation slices. |
| 2. Establish generated records and validation | Generate one shared LinkML Python bundle, structural schemas, and a manifest into private `_schema` artifacts. Move reusable semantic validation into the library; conformance commands call it. | Reproducible generation and intended conformance outcomes, with omission/null/zero/false and meaningful ordering preserved. |
| 3. Implement the canonical domain and revision boundary | Implement `model`, `specification`, `run`, and `io`; canonical ownership, revision-scoped UUID resolution, additive composition, codecs, immutable public access, and revision storage. | Valuation fixtures load, validate, resolve, round-trip, and create new revisions without mutating saved content or losing meaning. |
| 4. Complete the first usable library checkpoint | Expose `rk.Model`, `rk.Specification`, and `rk.Run`; finalize construction/loading/validation/revision interfaces and installed artifacts. Keep execution dependencies optional. | An installed library outside the checkout can load a Model, compose its Specification, resolve required references, and save an immutable revision without initializing a solver. |
| 5. Implement and verify scalar execution | Probe and pin Pyomo/HiGHS; prepare, compile, solve, independently check candidates, and publish authentic finalized Runs and output Models. | Full scalar acceptance, including forward/inverse results, genuine output reuse, changed-expression behavior, failures, limits, provenance, and batches. |
| 6. Migrate consumers and retire the old domain implementation | Adapt graph algorithms, adapters, source workflows, integrations, and walkthroughs; remove superseded classes/codecs after consumer verification. | Migrated consumers use the canonical Model and obsolete implementations have an explicit, verified retirement path. |

Steps 1–4 form the first implementation slice: a usable packaged domain core.
Packaging and import checks start as soon as Step 2 introduces library artifacts;
Step 4 closes that checkpoint rather than postponing those checks. Step 6 discovery
happens in Step 1, and particular consumers may migrate earlier when needed to
verify an interface. Full consumer migration is not a prerequisite for Step 5.

LinkML remains authoritative. Generated record shapes are private; handwritten
Python supplies behavior without creating a second field schema. Public immutable
access must contain generated-record mutability, including nested data. Model
changes require a new Metadata UUID, while unchanged declarations retain their
identities. Recorded quantities do not imply solve roles. Specification composition
accumulates requirements and rejects conflicts rather than overriding them.

Step 3 starts with in-memory and local filesystem revision stores. Their contracts
must define duplicate writes, conflicting content, and atomic publication before
execution depends on them. A production database is outside this checkpoint.

Step 5 must produce forward capital value of 11,000,000 AUD and inverse annual
rent of 27,500 AUD/dwelling/year from declared mathematics. It must reuse a real
forward output, independently check candidate quantities, and preserve immutable
inputs and provenance. The [full acceptance boundary](LIBRARY_ARCHITECTURE.md#first-executable-acceptance-boundary)
also governs failures, settings, units, limits, and batch accounting. Synthetic
fixtures remain expectations; observed outputs are stored separately.

Rich temporal Values and Flow/Stream content are implemented in full migration
Turn 1. Indexed formulations and policy evaluation are Turn 2; remaining consumer
proof and retirement follow in Turns 3–4.
There is no temporary production runtime under `schema/execution/` and no later
promotion into the library.

## Step 1: establish the migration baseline

### Purpose and scope

Produce a concrete answer to what must change, where it belongs, what can be
reused, who consumes it, and how each change will be verified. This step performs
read-only implementation discovery and runs existing checks; its authored outputs
are design and baseline documentation. It does not move packages, change runtime
behavior, rewrite tests to new expectations, regenerate retained research evidence,
or implement a solver.

The following is the completed Step 1 work queue, retained as its original scope.
Observed results and the chosen interfaces are in the linked migration map and
baseline. At Step 1 completion the APIs were proposed; Turns 1/2 now implement the
record and Model/Specification boundaries. External verification limits remain explicit.

### 1A. Capture the checkout and environment

1. Record branch, HEAD, dirty/untracked paths, and applicable repository instructions.
   Preserve existing documentation/research and the unrelated `.gitignore` change.
2. Record Python, dependency-tool, lockfile, and installed package versions used by
   each check. Establish whether commands import the checkout or an installed copy.
3. Record fingerprints for authoritative schemas and relevant fixtures so subsequent
   comparisons can distinguish changed inputs from changed implementation behavior.
4. Choose an isolated output directory for logs and build artifacts. Do not overwrite
   synthetic fixtures, retained CUE evidence, or existing consumer exports.

**Output:** a dated baseline manifest with exact commands, working directories,
input fingerprints, environment details, and evidence locations.

### 1B. Trace the current domain and public API

Inspect definitions, construction, ownership checks, mutation protection, imports,
exports, callers, serialization, and tests for each responsibility below.

| Responsibility | Initial inspection targets | Questions to settle |
| --- | --- | --- |
| Canonical container and identities | `src/rangekeeper/graph/graph.py`, `_catalog.py`, `entity.py`, `relationship.py`, `assembly.py` | Which assumptions depend on Python instances, Graph ownership, entity/assembly storage, or local codes? Which indexes can become derived Model access? |
| Definitions and Value content | `graph/definitions.py`, `taxonomy.py`, `classification.py`, `characteristics.py`, root `measure.py` | How do current Measurements/Features map to identified, locally keyed Values? Which payloads have no current schema representation? Which unit/aggregation behavior is reusable? |
| Provenance and revision operations | `graph/provenance.py`, `revision.py`, `update.py` | What is the target scope of Facts/Claims? Which identity, lineage, diff, and update assumptions fail when mathematics and the full Model envelope are included? |
| Persistence | `graph/adapter/json.py`, `_encoding.py`, `_structured.py`, `_yaml.py` | Which format/type-registry assumptions are specific to Graph? Which safe encoding and file-write routines are reusable? What happens to existing saved Graph documents? |
| Graph operations | `graph/view.py`, `reduction.py`, `operation.py`, `table.py` | What canonical object/query interface does each algorithm require? Which ordering, topology, membership, Value lookup, and aggregation semantics must be preserved or deliberately changed? |
| Root API and packaging | `src/rangekeeper/__init__.py`, `graph/__init__.py`, `api.py`, `src/pyproject.toml` | Which exports change? What triggers heavy imports? Where will generated artifacts and optional execution dependencies be declared? |
| Validation and composition | `schema/checks/*_contract.py`, `specification_composition.py`, `src/rangekeeper/validate.py` | Which routines are reusable library semantics, which are fixture harnesses, and which use bounded assumptions that require extension? |

**Output:** a responsibility matrix. Each row must identify the current symbol/file,
schema obligation, semantic mismatch, proposed destination, disposition, dependent
consumers/tests, prerequisite, and retirement condition. A file can contain both
reusable algorithms and domain behavior requiring replacement.

### 1C. Specify the new interface contracts

Document signatures or small pseudocode examples for the operations below, labelled
as proposed until implemented. Do not duplicate schema field declarations.

- **Construction and loading:** document decoding, structural validation, semantic
  validation, immutable snapshot creation, and diagnostics. Decide how callers
  create/revise records and how private generated records are contained.
- **Identity and access:** lookup by UUID within a pinned revision; typed resolution
  of document references; owner-local Value lookup; Entity/Assembly access; canonical
  ownership and derived indexes. The same declaration UUID in different revisions
  must not accidentally resolve through a process-global object cache.
- **Composition:** loading contributors, deduplication by included revision, conflict
  detection, effective requirement access, and contributor traceability. Composition
  is a derived view, not mutated content under an existing Specification UUID.
- **Validation ownership:** separate shape, domain semantics, composed-investigation
  completeness, backend capability, numerical acceptance, and Run/publication checks.
  Loading a record must not silently solve or claim numerical feasibility.
- **Revision and storage:** new revision creation, lineage, serializing and retrieving
  exact immutable records, same-ID writes, conflicting-content rejection, and atomic
  publication. Define content equivalence, including unordered collections versus
  ordered expressions/objectives; raw JSON byte equality alone is not the contract.
- **Units:** separate schema Measure/Quantity records from Pint operations and define
  the interface for compatibility/conversion. Identify legacy aggregation or currency
  assumptions that cannot simply be copied into the new Measure record.
- **Graph and execution consumers:** minimum read interfaces for traversal and the
  future scalar executor, publication interface for new revisions, and dependency
  direction. Graph indexes and prepared solver state do not own another Model copy.

**Output:** an interface table containing operation, inputs, result, owning package,
validation/error behavior, mutability, and dependencies. Include a proposed example
of loading a Model, resolving a Value, composing a Specification, and saving a new
revision, without requiring an executor.

### 1D. Inventory consumers and intentional breaks

Trace direct imports and attribute use, then inspect dynamic/lazy imports, persisted
formats, command-line entrypoints, notebook source cells, and integration boundaries.
Text search is a starting point, not proof of complete coverage.

Start with `src/rangekeeper/graph/adapter/`, `graph/workflow/`, root `api.py`,
`src/tests/`, `walkthrough/`, `grasshopper/`, and `hypar/`. Check which integrations
are active, stale, generated, or independently versioned before assigning work.
Known downstream project references should be listed with revision/availability
status; do not claim external compatibility without inspecting and running them.

For each consumer record:

1. The symbols, format, or behavior it consumes and the evidence for that dependency.
2. Whether it needs the new core before scalar execution or can migrate afterward.
3. The intended API/format change, unsupported content, and any explicit conversion.
4. The acceptance command or behavioral example and required environment/data.
5. The condition allowing the old implementation to be removed.

Distinguish source-building `WorkflowSpec` and workflow execution from mathematical
`Specification` and `Run`. Identify old Graph JSON explicitly; loading it as a new
Model without a defined conversion is not an acceptable compatibility strategy.
Do not build speculative compatibility shims. If a conversion is needed, specify
what it preserves, what it rejects, and how unsupported rich content is reported.

**Output:** consumer migration matrix and an explicit breaking-change list, with
external or unavailable consumers marked unverified.

### 1E. Establish the behavioral baseline

Run the seven existing schema suites listed in the
[schema validation instructions](../schema/README.md#validation-and-known-limits):
`validate.py`, `native_roundtrip.py`, `expressions.py`, `formulations.py`,
`models.py`, `specifications.py`, and `runs.py` under `schema/checks/`.
Use the appropriate pinned environment and record the exact invocation.

Run Python tooling from the `src/` project with its verified environment. Organize
existing tests by the behavior they protect:

| Test group | Initial targets |
| --- | --- |
| Domain, ownership, unresolved values, and persistence | `test_schema_graph_contract.py`, `test_scoped_codes.py`, `test_immutable_graph.py`, `test_unresolved_measurements.py`, `test_graph_json.py` |
| Root API, unit handling, and imports | `test_modules.py`, `test_measures.py`, `test_validate.py`, `test_api.py` |
| Adapter and workflow behavior | `test_adapters.py`, `test_cytoscape_adapter.py`, `test_workflow*.py`, `test_excel_ingestion.py`, `test_ingestion_evidence.py`, `test_tabular_operations.py`, `test_document_operations.py` |
| Numerical behavior to retain | `test_formulas.py`, `test_models.py`, `test_projections.py`, `test_dynamics.py` |

Collect the complete existing test inventory before deciding the execution scope.
Run available local tests; isolate service-dependent or unavailable integration
checks and record why they could not be verified. For every failure, distinguish
an existing implementation failure, environment/dependency issue, unavailable
fixture/service, or unresolved cause. Reproduce relevant failures narrowly before
classifying them; historical pass counts and failure descriptions are clues, not
current results. Baseline establishment does not include unrelated repairs.

For each planned interface, map existing test coverage or identify a missing future
acceptance test. Focus gaps on multiple Values per Measure, canonical Assembly
storage, Formulation-local Values, revision-scoped references, nested immutability,
composition conflicts, content-preserving round trips, and installed artifacts.
Write those new tests alongside implementation in later steps, not as assertions
against APIs that do not yet exist.

**Output:** command/result matrix with passed/failed/skipped/blocked counts, retained
logs, failure classification, and an acceptance coverage map.

### 1F. Turn findings into ordered implementation slices

Translate the map into independently verifiable work units for Steps 2–4:

1. Reproducible shared record generation, structural artifacts, and package inclusion.
2. Shared semantic validation and diagnostics with conformance callers redirected.
3. Model ownership, UUID access, immutable snapshots, and schema-compatible codec.
4. Specification revision resolution, additive composition, and role validation.
5. Finalized Run record access/validation and revision-store behavior for all document kinds.
6. Public exports and installed-package verification of the complete first slice.

For each unit name the files to introduce/change, prerequisites, intended API breaks,
existing checks to preserve, new behavioral acceptance checks, and the old code it
eventually replaces. Record unresolved design questions with a recommendation and
their impact on ordering. Keep rich temporal payloads and policy behavior deferred.

### Step 1 completion criteria

- Every core responsibility has a supported replace/adapt/retain/defer decision.
- Every discovered consumer has a migration placement and an acceptance check,
  or an explicit unverified status and reason.
- Core interfaces specify construction, resolution, composition, validation,
  immutability, persistence, diagnostics, and package dependency direction.
- The baseline identifies exact inputs, environment, commands, results, and limits.
- Steps 2–4 can begin as concrete work units without redesigning their boundaries
  during scalar execution; remaining questions and blockers are explicit.
- The architecture, documentation index, and handoff agree with the resulting map.

The resulting inventory, interfaces, and ordered work units are in
[DOMAIN_MIGRATION_MAP.md](DOMAIN_MIGRATION_MAP.md), with observed run evidence in
[BASELINE.md](research/domain-migration/BASELINE.md). All 1A–F deliverables are covered.
Work units 2A/2B, 3A/3B, and 3C/4 are now implemented. Review the
[Model/Specification APIs](DOMAIN_CORE.md) and [Run/storage APIs](RUN_AND_STORAGE.md),
and the implemented [scalar executor](SCALAR_EXECUTION.md), then continue with [Step 6E](GRAPH_MODEL.md#remaining-step-6-implementation-slices).
The three domain implementation turns completed
checkpoints 2–4; they do not renumber the six checkpoints above.
Commit/push/release remain separate actions.
