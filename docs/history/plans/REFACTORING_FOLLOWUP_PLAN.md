# Rangekeeper refactoring follow-up plan

Archived on 2026-10-08. Implementation and local acceptance were recorded at
`08aac85`. The original RF identifiers, rationale and recorded results remain
below. Current contracts are linked from the [documentation index](../../README.md)
and [decision index](../../decisions/README.md).

Carried-forward work: [Windows/Rhino/connector acceptance](../../contributing/windows-acceptance.md),
[legacy retirement](../../contributing/legacy-retirement.md), and any unrun remote
checks under [verification](../../contributing/verification.md). Archiving this
implemented plan does not close those gates.

Status: RF-024–RF-034 implemented; local acceptance passed on 2026-10-08. External host limits are recorded below.

Created: 2026-10-07. Reviewed baseline:
`5a111b00bb4990a883af08d6ccbc7561b4bab445` on `acausal-modelling`.

This plan follows the [RF-001–RF-023 implementation](REFACTORING_PLAN.md).
It records the package-wide structural review and defines a bounded second pass.
Some work completes earlier simplification objectives; other work refines the
implemented structure. The earlier acceptance evidence remains historical.
The user approved the final hierarchy and requested documentation followed by implementation on 2026-10-08.

## Scope and baseline

Reduce repeated preparation, unused state, forwarding layers and unnecessary
module boundaries. Put behavior on an existing owner where the contracts match.
Preserve mathematical behavior, diagnostic locations, identity rules, provenance,
immutable evidence and independent numerical acceptance.

The review covered every Python file under `src/rangekeeper`. Counts use physical
lines, including blank lines, and Python AST definitions. Function counts include
methods and nested functions, but exclude lambdas. `__init__.py` and handwritten
`_schema/validation.py` count as active runtime. Only `_schema/records.py`,
`_schema/native.py` and `_schema/enums.py` count as generated Python.

| Category | Files | Lines | Classes | Functions/methods |
| --- | ---: | ---: | ---: | ---: |
| Active handwritten Python | 219 | 29,572 | 210 | 1,018 |
| Generated Python | 3 | 8,544 | 220 | 515 |
| Legacy Python | 22 | 4,100 | 52 | 180 |
| Total reviewed Python | 244 | 42,216 | 482 | 1,713 |

The review included source/caller inspection, a Specification export-count probe
and 15 passing focused baseline tests. It did not rerun the full suite, layout
solvers or external host checks. The earlier 1,428-test acceptance result belongs
to the [first pass](REFACTORING_PLAN.md#acceptance-evidence); it is not acceptance
of these proposed changes. Existing unrelated documentation edits in `README.md`,
`docs/README.md`, `docs/INSTALLATION.md` and `docs/CONTRIBUTING.md` are preserved. RF-034 adds
only the current-API guide changes needed by this pass.

## Intent register and final owners

RF-024–RF-034 form the authorized implementation scope. Dynamics consolidation is
included at the user's request. An earlier RF reference identifies the related
objective; it does not replace that intent's historical implementation record.

| Intent | Work package and final owners | Earlier intents | Status |
| --- | --- | --- | --- |
| [RF-024](#rf-024-specification-and-execution-preparation) | Specification graph/roles in `specification.composition`; solve state in `run.execution.preparation`; located traversal in `model.formulation.preparation` | RF-005, RF-006, RF-009, RF-022 | Implemented |
| [RF-025](#rf-025-record-construction) | One construction copy in `schema.runtime`; shared structural checks in `schema.validation` | RF-006, RF-020 | Implemented |
| [RF-026](#rf-026-flow-operations-and-callers) | Coordinate indexing in `FlowBehavior`; alignment policies remain with callers | RF-002, RF-014, RF-015 | Implemented |
| [RF-027](#rf-027-scenario-contracts-and-sampling) | Conformance in `model.scenario.contracts`; sampling in `Distribution` | RF-021 | Implemented |
| [RF-028](#rf-028-workflow-ownership) | Loading/expansion in `workflow.specification`; lineage in `workflow.provenance`; produced-value contract in `_contracts` | RF-023 | Implemented |
| [RF-029](#rf-029-evidence-preparation-for-source-checks) | Issue indexing in `workflow.evidence.validation`; source-check policy in `workflow.source_checks` | RF-023 | Implemented |
| [RF-030](#rf-030-atomic-json-publication) | Atomic JSON replacement in `io._atomic`; domain controllers remain separate | RF-023 | Implemented |
| [RF-031](#rf-031-adapter-and-layout-preparation) | Projection in Cytoscape; membership on `Problem`; arithmetic assessment in layout `check`; errors in `shared.errors` | RF-010–RF-013, RF-023 | Implemented |
| [RF-032](#rf-032-execution-acceptance-ownership) | Comparison acceptance in `run.execution.acceptance`; finite arithmetic in `model.expression.evaluation` | RF-008 | Implemented |
| [RF-033](#rf-033-dynamics-consolidation) | One `calculations.dynamics` module for the five deterministic kernels | RF-021 | Implemented |
| [RF-034](#rf-034-agreed-module-hierarchy-and-import-migration) | Model–Specification–Run hierarchy, schema/shared foundations and workflow Evidence | All above | Implemented |

## RF-034 Agreed module hierarchy and import migration

This package hierarchy supersedes earlier destination paths in RF-024–RF-033.
Problem descriptions name the reviewed source; implementations use the final
owners below. Source links lead to the current owner after consolidation. Apply relocation and each associated simplification together so
code is not moved twice. Python package location does not change wire ownership,
reference scope, mathematical order or execution authority.

```text
rangekeeper/
  schema/                 generated records/enums/resources; runtime, index,
                          revision, structural validation and behavior mixins
  shared/                 table, units, resolver protocols, diagnostics, errors,
                          arguments, validation, encoding, structured, yaml,
                          fingerprint mechanics
  model/
    definitions.py        catalogue records and lookup
    system/               System/Entity/Assembly/Relationship exports; validation,
                          views, membership, hierarchy, selection and reduction
    provenance.py         canonical Source/Claim/Fact conformance and lookup
    characteristics.py    owner-local Value/Label access
    flow.py               Flow, Movement and revision-pinned Stream
    distribution.py       Distribution domain import home
    duration/             Period/Span exports, calendar and period operations
    expression/           shared language, authoring, analysis and arithmetic
    formulation/          shared containers, preparation and passive builders
    scenario/             records, contracts, generation, captured paths and replay
    model.py              Model facade, lookup and revision
    scope.py              Model/composed mathematical scope
    validation.py         Model validation coordinator
    update.py, diff.py
  specification/
    specification.py, composition.py, targets.py, validation.py
    policy/               declaration, observation, exact truth and outcome rules
  run/
    run.py, report.py, outputs.py, validation.py
    execution/            planning, preparation, compiler, independent acceptance,
                          publication and explicit backend services
  calculations/           known-data operations; account conventions and Account;
                          one deterministic dynamics module
  workflow/
    evidence/             transient source support and transformations
    operation.py          invocation contracts, Outcome and diagnostics
    provenance.py         explicit conversion to canonical Model provenance
    ...                   source composition and optional runner
  io/                     codecs, stores and atomic publication
  adapters/               formats, transport, viewer and geometry layout
  migration/, examples/, legacy/
```

### Final path map and boundaries

| Reviewed location | Final location / action |
| --- | --- |
| `_schema/`, `_records.py`, `_record_index.py`, `_revision.py`, `_behaviors/` | `schema/`, `schema/runtime.py`, `schema/index.py`, `schema/revision.py`, `schema/behaviors/` |
| `table.py`, `units.py`, `references.py`, `diagnostics.py`, `errors.py` | Same filenames under `shared/`; keep Table/Row names and semantics |
| `validate.py`, `_validation.py`, `_encoding.py`, `_structured.py`, `_yaml.py`, `_implementation.py` | `shared/arguments.py`, `validation.py`, `encoding.py`, `structured.py`, `yaml.py`, `fingerprints.py`; preserve separate contracts |
| `metadata.py` | Export the same canonical Metadata from `schema`; remove the thin file |
| `graph/`, `model/system.py` | `model/system/`; move System checks into its validation module and make package imports lazy |
| `model/entity.py`, `assembly.py`, `relationship.py` | Export canonical types from `model.system`; delete the three thin files |
| `formulations/` | Merge into `model/formulation/`; expression constructors go to `model/expression/authoring.py` |
| `duration/`, `model/duration.py` | One `model/duration/` package, preserving Period/Span exports |
| `scenarios/`, `model/scenario.py` | One `model/scenario/` package, with lazy generation/replay imports |
| `policies/` | `specification/policy/`; Run outcome validation can use pure policy checks without importing evaluation services |
| `execution/` | `run/execution/`; Run construction/validation stays passive and imports no solver |
| `evidence/`, `operation.py` | `workflow/evidence/`, `workflow/operation.py`; adapters import contracts without loading catalog/configuration/runner |
| `account.py` | Absorb conventions into `calculations/account.py`; passive builders import the options/check only, with no reverse formulation dependency |

Shared modules have no runtime dependency on Model/Specification/Run facades,
workflow orchestration, stores, adapters or solvers. Schema primitives are allowed
where needed, such as Quantity in UnitSystem. Initializers do not eagerly collect
all shared modules. Keep actual leaf imports acyclic: schema may use shared
errors/diagnostics, while units uses generated records. Do not introduce a generic
utils module or merge the distinct encoding/validation contracts.

Keep Model-wide references and pinned Views. Formulations and Expressions remain
shared between Models and Specifications, although Model formulations serialize
under System. The generated canonical class is defined once; domain exports expose
that class. Workflow Evidence Claims retain their separate native-value contract
and explicit conversion to canonical provenance. No new dataframe API, canonical
Table record, account schema, revision format or runtime Function support is added.

### Implementation and acceptance

Update the generator destination, generated behavior imports, packaged resources,
all live import paths, subprocess entry points, semantic manifests and wheel tools
in the same relocation. Regenerate through pinned tools; do not hand-edit generated
outputs. Runtime schema resources move without changing their contents or wire
versions. Migrate maintained tests, typing fixtures, examples, notebooks and guides;
historical audit records retain historical names. Remove old namespaces without
compatibility modules or sys.modules aliases. Preserve the user's existing README
and contributor changes while applying necessary current-API documentation edits.

Verify fresh imports in several orders and without numerical/adapter extras,
absence of retired namespaces, generator checks, typing, full required-solver tests,
conformance and installed-wheel checks. Keep current-format evidence readable;
changed source paths legitimately change computation fingerprints. Validate each
manifest from its final package location and exercise its semantic-change tests.

Relocations do not count as deletion. In addition to RF-024–RF-033's twelve net
module reduction target, remove the metadata and three entity-type facades, the
root account conventions file and the duplicate package initializers/facades
absorbed by the hierarchy. New shared/schema/system initializers or authoring
modules must be included in final accounting. Recompute the exact module total
from the final tree rather than retaining the earlier 207-file estimate as a gate.
No new domain wrapper classes are required. Record runtime/generator/test/docs
counts separately and retain the combined net handwritten reduction target.

## Shared contracts and deliberate API changes

Reuse prepared results only within an operation over the same content, revision,
scope, units, history and settings. Do not introduce a global cache, a public
`trusted` flag, a generic validation context or a new resolver framework. Preserve
checks at independent IO, solver-acceptance and stored-evidence boundaries.

| Change | Contract for implementation |
| --- | --- |
| `Flow.coordinate_index()` | New intrinsic operation; detached ordered mapping to existing Movements; duplicate coordinates fail; no magnitude access, sorting or join policy |
| `scope_for_model(..., units=...)` and `observe(..., units=...)` | Remove the currently unused parameter and migrate callers; observation returns recorded units. Retain UnitSystem on evaluation and all actual arithmetic/validation consumers |
| `quantity` in expression evaluation | Rename to `finite_quantity` and update callers together; preserve rejection of Boolean, complex and nonfinite values and existing error translation |
| `sample_noise` | Remove the forwarding API; use `Distribution.sample(size=..., generator=...)` directly |
| `calculations.dynamics` | Replace the subpackage with one module; import the five deterministic functions from `rangekeeper.calculations.dynamics`; remove old submodule paths without aliases |
| `AdapterError` / `AdapterEncodingError` | Remove aliases and package exports; use the existing `BoundaryError` / `EncodingError` classes without changing inheritance or catch behavior |
| `Produced.from_evidence()` | Construct the existing output contract from Evidence; preserve its fingerprint and source rules |
| Layout assessment | One operation returns findings and metrics from the same geometry; standalone metrics retains its validation contract |
| Wire formats and stored evidence | No schema/version migration, pin rewrite or stored-result conversion is planned. Preserve exact content, field presence, order and revision rules |

These are explicit pre-1.0 API changes. Update maintained callers, tests, typing
fixtures, examples, notebooks and guides together. Do not leave forwarding
aliases. Historical documents and captured evidence retain their old names.
Routine private signatures can be resolved during implementation within these
contracts; record any broader behavioral change before extending scope.

### Fingerprints and source moves

Update source inventories in the same work package as each move. Preserve separate
execution, scenario and workflow provenance contracts; reuse only their existing
hashing mechanics. Code movement can change implementation fingerprints even
when output mathematics is unchanged. Do not promise identical realized revision
IDs across implementations or substitute an old fingerprint to satisfy a test.

| Manifest | Required coordination |
| --- | --- |
| [Execution](../../../src/rangekeeper/run/execution/implementation.py) | Remove `_coordinates.py`, `model/_scenario.py`, `model/formulation/traversal.py` and `execution/evaluator.py`; retain their final owners in the correct common/compiler/evaluator groups |
| [Scenario](../../../src/rangekeeper/model/scenario/implementation.py) | Remove `model/_scenario.py`; keep `scenarios/contracts.py` and Flow behavior. Replace the four deterministic dynamics paths with `calculations/dynamics.py`. Moving the coordinate helper into Flow changes an already included file. Sampling remains outside replay mathematics |
| [Workflow](../../../src/rangekeeper/workflow/implementation.py) | Remove stale `_artifacts.py` and adapter-error path rules; include moved provenance/computation. Preserve full installed-code audit separately from computation identity and presentation exclusions |

Keep current-format historical results readable. Replay must report unavailable
implementation identity when appropriate. Test inclusion of semantic sources,
exclusion of presentation-only changes, portable paths and missing-source errors.
Do not edit source while fingerprint-dependent acceptance is running.

## RF-024 Specification and execution preparation

**Problem and evidence.** [Planning](../../../src/rangekeeper/run/execution/planning.py)
collects and exports resolved Specifications, but
[composition](../../../src/rangekeeper/specification/composition.py) exports the entire
supplied document set again for each leaf despite receiving its catalogue. The
review probe measured 7, 142 and 2,702 `Specification.to_data()` calls for batches
with 1, 10 and 50 leaves respectively. Of the last total, 2,550 came from the
redundant catalogue comprehension. Typed graph collection and role-set checks
also have multiple owners.

**Implementation.** Give composition one typed Specification graph collection
operation and reuse its exact documents/catalogue for all leaves. Public compose
collects when needed; Plan uses the same collection while retaining Model
preflight, batch pin checks, per-leaf failure records and scheduling. Reuse the
root export and remove the unused catalogue comprehension. Keep one local role
inventory/check operation in composition; complete validation adds scope, unit,
estimate, policy and completeness rules.

Remove unread `Prepared.values`, its Model scan and local-Value accumulation from
[execution preparation](../../../src/rangekeeper/run/execution/preparation.py). Keep
`model_values`, which enforces Model-owned publication. Move `walk_formulations`
into its sole consumer, existing `model/formulation/preparation.py`, retaining
original paths. Remove the unused scope/observation unit arguments as specified
above; do not remove the actual policy evaluation unit context.

**Deletion and size.** Delete `model/formulation/traversal.py`, the duplicate
planning collector, repeated role blocks, unused Value state and no-op argument
plumbing. Expect a net handwritten reduction; no new context or module is needed.

**Preserve.** Keep resolver kind/identity/cycle checks, one load per revision,
diamond includes, contributor conflict rules, JSON Pointer locations, batch versus
sibling scope distinctions, checkpoints and failure retention. Equal content from
independent contributors can still conflict. Partial declarations may contain
targets that become complete only after composition.

**Verification and completion.** Use `test_domain_specification.py`,
`test_core_preparation.py`, `test_core_review_regressions.py`, `test_execution.py`
and policy tests. Add a linear export-count regression across several batch sizes
and one-load-per-revision checks; retain malformed/cyclic and mixed-success batch
cases. Verify local publication rejection, Movement roles, one-shot traversal,
source locations and caller-supplied evaluation units. Complete when unused state
and the duplicated collectors are absent and batch growth is linear in exports.

## RF-025 Record construction

**Problem and evidence.** [`Record._set_data`](../../../src/rangekeeper/schema/runtime.py)
copies the whole JSON tree, then [`validate`](../../../src/rangekeeper/schema/validation.py)
copies it again in the same construction call. No timing improvement was measured.

**Implementation.** Separate the existing schema-only check from the public
copy-and-check entry point inside `_schema.validation`. Record construction makes
one defensive copy, checks that detached tree, then normalizes/freezes it. Public
validation retains its own copy and returns the existing `ValidationReport`.
Use a private internal operation, not a caller-supplied trust switch or a new
prepared-record class. Preserve current exception/report behavior at each entry.

**Deletion and size.** Remove the second whole-tree copy from construction.
A small private check operation can be line-neutral or add a few lines; that
bounded growth is justified only by sharing the existing schema loop and removing
the duplicate traversal. No new module or duplicated validation body is allowed.

**Preserve.** Keep input nonmutation, deep immutability, UUID normalization,
omitted/null/empty distinctions, exact JSON types, nonfinite rejection, nested
locations, equality and revision behavior. Codec/store snapshots are separate
trust boundaries and remain validated.

**Verification and completion.** Run record/identity, structural conformance,
codec, store, revision and installed-wheel checks from [Verification](../../contributing/verification.md).
Add a focused construction-copy regression with nested mutable input and invalid
JSON values; compare public validation reports and construction failures. Complete
when each entry retains its boundary and construction copies its input only once.

## RF-026 Flow operations and callers

**Problem and evidence.** [`_coordinates.py`](../../../src/rangekeeper/schema/behaviors/flow.py)
has three production importers, all passing a whole Flow. Its owner is the Flow,
not an arbitrary package-root helper. Example authoring also repeats an existing
constructor, while series/projection repeat exhaustive enum checks.

**Implementation.** Add `coordinate_index()` to existing
[`FlowBehavior`](../../../src/rangekeeper/schema/behaviors/flow.py). Replace calls in
`calculations/account.py`, `calculations/series.py` and `formulations/flow.py`.
Keep coordinate equality independent of Movement identity and retain duplicate
rejection and encounter order. Replace the applicable Movement loops in
`examples/design.py` and `examples/investment.py` with `Flow.from_periods`, keeping
explicit dates, keys, IDs where supplied, and unresolved magnitudes.

Remove full-member enum checks after successful enum type checks in
`calculations/series.py` and `calculations/projection.py`. Keep proper-subset and
cross-argument checks, including ZERO restrictions and mean weighting.

**Deletion and size.** Delete `_coordinates.py`, the example construction loops
and redundant choice branches. Expect a net reduction and no new module. Update
the generated behavior bridge only if required; never hand-edit generated records.

**Preserve.** Keep numerical account transaction order, symbolic destination
order and exact set matching, and numerical join/sort/missing-value policies with
their callers. Do not read magnitudes in the coordinate index or make symbolic
authoring depend on numerical series. Do not change deterministic scenario Flow
UUID construction as an incidental example cleanup.

**Verification and completion.** Run `test_reference_identity.py`,
`test_account_schedule.py`, Flow alignment/missing-value cases,
`test_design_example.py` and `test_models.py`; retain independent financial
oracles. Check duplicate coordinates, unresolved movements, result identity and
all supported enums. Complete when all three consumers use the Flow operation,
the root helper is absent, and explicit order/identity tests pass.

## RF-027 Scenario contracts and sampling

**Problem and evidence.** [`model/_scenario.py`](../../../src/rangekeeper/model/scenario/contracts.py)
owns method/capture conformance but already imports `scenarios.contracts`.
`market.captured_inputs` repeats content checks certified by construction of its
immutable Model. `calculations/dynamics/noise.py` only forwards to Distribution;
production sampling already calls the owner directly.

**Implementation.** Move `validate_plan`, `validate_realizations` and their
content helper into existing `scenarios/contracts.py`. Keep Distribution and scope
imports local where required to avoid Model initialization cycles. Model provenance
remains the integration point for independent stored-content validation.
Reduce `captured_inputs` to its external plan-selection checks and typed extraction
from that exact validated Model. Use `Distribution.sample` directly in the noise
test and migrate maintained API references.

**Deletion and size.** Delete `model/_scenario.py` and
`calculations/dynamics/noise.py`; remove repeated capture shape, units, inventory,
fixed-value and support checks in market. Expect a net reduction. Keep
`model/scenario.py` as the generated-record facade and keep `scenarios/_paths.py`.

**Preserve.** Retain forged-capture rejection on Model loading, parameter support,
period/date precedence, availability and delayed observations, base revision/plan
matching, output replay checks and deterministic identity encodings. Keep pure
numerical kernel checks and caller-owned random generators. `make_noise` remains
the market recipe constructor; sampling streams remain in `scenarios.random`.

**Verification and completion.** Run `test_scenario_contracts.py`,
`test_scenarios_policies.py`, `test_dynamics.py`, sampling tests and scenario
import-isolation checks. Preserve serial/parallel equivalence, caller-only RNG
advancement and point-mass behavior. Complete when conformance has one owner,
generation no longer imports the private Model helper, and stored evidence still
fails independently when forged. Coordinate manifests with RF-026.

## RF-028 Workflow ownership

**Problem and evidence.** [`workflow/_shared.py`](../../../src/rangekeeper/workflow/specification.py)
has one production consumer, specification loading. Validators are imported
through composition. `implementation.py` combines fingerprint selection with
provenance construction. Table operation declarations repeat mapping preparation
and two identical output-description functions.

**Implementation.** Move number/measurement-set expansion and its local helpers
into `workflow/specification.py`. Import validators directly from existing
`_model_validation.py` and remove composition's forwarding exports. Keep that
validation module and direct composition without WorkflowSpec.

Move `configuration`, `deferred_records` and `metadata` into existing
`workflow/provenance.py`; leave manifests, capabilities and dependency selection
in `implementation.py`. Reuse a small local mapping normalization/parsing helper
within `_table_operations.py`, retaining distinct NumbersSpec and TransformsSpec.
Add `Produced.from_evidence` to existing `_contracts.py` and point all relevant
table/Excel declarations to it. Do not make Evidence import workflow contracts.

**Deletion and size.** Delete `_shared.py`, forwarding validator exports,
duplicate mapping bodies and both free `describe_table` functions. Relocations
are mostly line-neutral; the combined package must reduce handwritten lines.
No new registry, module or compatibility wrappers are needed.

**Preserve.** Keep copied definitions, inline/reference exclusivity, unused-set
checks, mapping order, error contracts, consumer source locations and single-row
Evidence contexts. Keep Source/Claim object identity, UUID namespaces, configuration
encoding, lineage, metadata keys and format versions. Preserve optional-import
boundaries and the distinction between audit and computation fingerprints.

**Verification and completion.** Run `test_workflow_shared.py`,
`test_workflow_boundaries.py`, `test_workflow_formats.py`, workflow schema/parsing,
Excel and publication regression tests. Include named/inline equivalence,
nonmutation, fake non-Excel registration, direct composition and determinism.
Complete when imports lead to the stated owners, duplicate descriptions are gone
and lineage remains exact. Coordinate shared-file edits with RF-029/RF-030/RF-031.

## RF-029 Evidence preparation for source checks

**Problem and evidence.** [`workflow/source_checks.py`](../../../src/rangekeeper/workflow/source_checks.py)
scans all Issues for each missing numeric cell through `tabular.issues_for`, despite
the existing index in [`PreparedEvidence`](../../../src/rangekeeper/workflow/evidence/validation.py).
It also repeats missing-column branches after `require_columns`.

**Implementation.** Prepare each exact Evidence object once per source-check
operation, including when several named inputs refer to that same object. Reuse
the existing cell-scope index; do not create a workflow index type. Remove only
the redundant post-preparation column checks. If preparation has unrelated cost,
measure it before changing the existing API; do not fork the indexing algorithm.

**Deletion and size.** Remove repeated full Issue scans and duplicate branches.
Expect a net reduction or line-neutral local preparation; no new module or
persistent cache is allowed.

**Preserve.** Keep Issue encounter order, global/row/cell applicability, first
displayed reason, source filtering and exact Evidence/Claim identity. Keep upfront
column checks for empty tables. The `column=None` query also finds child cell
issues, so do not replace every tabular lookup with a cell-only operation.

**Verification and completion.** Run ingestion/evidence and workflow format/
boundary tests. Add overlapping global/row/cell Issues, aliased inputs and empty
tables with missing columns. Verify one preparation per exact Evidence within a
call and fresh preparation on later calls. Complete when repeated cell lookup
uses the shared index and all scope/order failures remain unchanged.

## RF-030 Atomic JSON publication

**Problem and evidence.** [`workflow/_artifacts.py`](../../../src/rangekeeper/io/_atomic.py)
and the layout review controller duplicate the same JSON replacement wrapper.
[`io/_atomic.py`](../../../src/rangekeeper/io/_atomic.py) already owns publication,
durability, interruption and cleanup semantics.

**Implementation.** Add `replace_json(path, value)` to that existing IO module,
with the current JSON options and final newline. Use it from workflow workbench
and layout review. Leave artifact schemas, status transitions, manifest validation
and review controllers in their current domains.

**Deletion and size.** Delete `_artifacts.py`, layout's `_atomic_json` wrapper and
obsolete imports/manifest rules. Expect a small net reduction and no new module.
Do not expand this into a shared bundle-publication framework.

**Preserve.** Propagate `PublishedFileError` and `PublishedFileInterrupted`.
Distinguish visible publication from confirmed durability, preserve completed
outputs after post-publication failures, and never restore an old pointer over a
later writer. Cancellation and status/observer failures retain their contracts.

**Verification and completion.** Run `test_review_publication_regressions.py`,
`test_workbench.py`, `test_layout_workbench.py` and `test_layout_saved.py`.
Update tests that patch old import aliases without weakening failure injection.
Complete when both controllers use the one JSON operation and interruption,
durability and competing-writer regressions pass.

## RF-031 Adapter and layout preparation

**Problem and evidence.** [`Cytoscape.project`](../../../src/rangekeeper/adapters/cytoscape/__init__.py)
repeatedly scans selected entities/relationships and rebuilds selected-ID sets
inside membership tests. Layout `Problem.descendants` rebuilds its group index
and revisits shared subgraphs. Layout `metrics` reruns the arithmetic checker
after many callers have just checked the same geometry.

**Implementation.** Materialize selected entities/relationships and their ID sets
once inside projection. Keep descendant traversal on existing `Problem`, make it
iterative with visited tracking, and prepare each group's descendants once per
checking/rendering/formulation operation. Private checker/collision helpers accept
only the map created by that local operation; public entry points prepare their
own map. Emitted SVG read-back remains a separate validation boundary. Reuse the existing local maps where
MiniZinc/reduction already do this; do not add parallel topology types.

In existing `layout/check.py`, provide one assessment operation that computes
findings and metrics together. Keep standalone `metrics` validated, and make its
internal arithmetic reuse findings created by the same assessment. Update solver
acceptance, seed, saved-layout and refinement callers. Import renderer `Result`
directly from `.result`. This corrects ownership; it is not a claim that importing
the current renderer fails without Z3.

Replace adapter error aliases with direct imports from root `errors.py`, including
their retained legacy codec consumer. Keep Speckle's context-bearing mapping and
transport error contracts. This naming migration does not retire legacy code.

**Deletion and size.** Delete `adapters/errors.py`, its package exports, inner
selected-set construction, repeated traversals and adjacent check/metrics passes.
Expect a net reduction across callers. No new cache module, universal graph type
or solver base class is needed.

**Preserve.** Keep selection order, canonical identity, explicit assembly
membership, shared DAG membership, containment policy, serialized layout contracts
and geometry checks. Keep preparation local because shallowly frozen Problem
inputs need not be deeply immutable. Never accept stale findings or saved metrics
as proof of valid geometry. Keep both solver formulations independent from the
arithmetic checker, native objective comparison and strict/diagnostic acceptance.

**Verification and completion.** Run Cytoscape/model-consumer tests, adapter/Excel
error tests, legacy codec tests, fresh-process imports and the strict layout suite.
Add selected-scope call counts, a shared DAG/deep chain, and one arithmetic check
per assessment. Retain malformed geometry, objective disagreement, diagnostic
collisions, fixed seeds and timeout-incumbent cases. Complete when operation-local
preparation is reused, the alias module is absent and both solver acceptance
paths pass without skips. Coordinate IO fault tests with RF-030.

## RF-032 Execution acceptance ownership

**Problem and evidence.** [`execution/evaluator.py`](../../../src/rangekeeper/run/execution/acceptance.py)
defines only `comparisons`, used by acceptance. Publication imports `quantity`
through the evaluator's incidental import, although shared arithmetic already
belongs to `model.expression.evaluation`.

**Implementation.** Move comparison acceptance into `execution/acceptance.py`
as a private operation. Rename the finite quantity constructor as specified in
the API table and import it directly from its owner in publication and all other
callers. Update focused tests and the execution evaluator fingerprint inventory.

**Deletion and size.** Delete `execution/evaluator.py`, its forwarding dependency
and obsolete imports. The function move is line-neutral; module/import overhead
should decrease. No replacement module is needed.

**Preserve.** Evaluate original expressions independently of affine compiler
rows. Keep conjunction order, exact fixed strict predicates, residual tolerances,
nonfinite rejection and caller-level NumericalError/UnsupportedProblem/UnitError
translation. Policy Boolean truth and short-circuit rules remain separate.

**Verification and completion.** Run expression-evaluation, execution, strict
predicate, nonfinite candidate, independent acceptance and policy regressions.
Verify fingerprint sensitivity to the final arithmetic/acceptance owners.
Complete when comparisons have one owner and publication has no dependency on
an accidental evaluator re-export. Coordinate RF-024 caller edits and RF-025
record-boundary tests.

## RF-033 Dynamics consolidation

**Problem and evidence.** After RF-027 removes the noise wrapper, the deterministic
dynamics package contains `trend.py`, `volatility.py`, `cyclicality.py`, `shock.py`
and a one-line `__init__.py`: about 130 lines in five files.
[`scenarios/_paths.py`](../../../src/rangekeeper/model/scenario/_paths.py) is their only
production consumer. One module can expose the same small family of operations
without the extra navigation and import paths.

**Implementation.** Replace that subpackage with `calculations/dynamics.py`.
Keep `calculate_trend`, `calculate_cycle`, `calculate_autoregression`,
`accumulate_volatility` and `calculate_shock` as distinct functions with unchanged
signatures and algorithms. Share their existing `math` and `Sequence` imports,
and adjust the projection import for the shallower module location. Keep sampling
on Distribution and scenario composition in `_paths`; do not move either into
dynamics or introduce a dynamics class.

Migrate `_paths`, direct tests and maintained documentation to import from
`rangekeeper.calculations.dynamics`. Change the scenario manifest's four kernel
paths to the new module. Update the fingerprint mutation test that currently
edits `calculations/dynamics/volatility.py` to modify the corresponding function
in the new module. Remove the old package directory in the same change so module
and package forms cannot coexist. Preserve historical audit documents.

**Deletion and size.** Delete the four kernel modules and their `__init__.py`;
add one consolidated module. RF-027 owns the separate noise deletion, which must
not be counted twice. Expect four net modules removed and a modest line reduction
from common imports/module overhead. This is consolidation of existing functions,
not a new abstraction or a change to their mathematics.

**Preserve.** Keep trend initial-value defaults, explicit sample inputs, bounded
shear root iteration and tolerances, autoregression order, first-return behavior,
mean reversion, first-event shock onset, exactly-once impact and all finite/range/
shape failures. Preserve optional-import behavior. A new source fingerprint is
expected; retain output oracles and honest replay-availability checks rather than
forcing the previous implementation fingerprint.

**Verification and completion.** Run `test_dynamics.py`, `test_calculations.py`,
`test_calculation_equivalence.py`, `test_scenario_contracts.py` and the fixed
scenario-oracle/serial-parallel tests. Verify the new import path in a fresh
process and installed wheel, all five functions, manifest sensitivity to each
kernel, and absence of the old subpackage/imports in maintained callers. Complete
when the single module replaces the directory, numerical oracles remain valid
and calculation provenance includes the new source. Implement after RF-027.

## Boundaries retained and exclusions

Keep `schema.index`, `schema.revision`, `shared.fingerprints`, the generated
behavior bridge, policy availability, Evidence derivation, `io._document`, and
pure `model.scenario._paths`. Each has a real shared contract. Keep `_model_validation`,
workflow catalog/contracts/schema, subprocess worker entry points and the public
record exports retained by RF-034. Do not merge them solely because a module is short or private.

Evidence payload encoding, request freezing, record JSON rules and declaration
YAML decoding have different contracts. Table and Evidence also have different
identity/immutability requirements. Graph membership, rooted hierarchy and
coverage reduction are separate operations. Numerical account calculation and
passive symbolic account construction retain their different capability limits.
Keep the independent solver backends, arithmetic acceptance and Speckle network/
mapping/SDK boundaries. No generic serializer, validator or publication framework
is proposed in this pass.

The entire legacy package remains outside consolidation. Its 4,100 lines must not
be counted as an immediate reduction. Retirement requires the existing
[Windows connector acceptance gate](../../contributing/legacy-retirement.md), then a
separate removal of the predecessor package, tests, extra and corresponding C#
tree. Retain supported wire converters and fixtures after retirement. This plan
does not claim that gate, Rhino loading, Linux execution or remote CI has passed.

## Execution order and integration

Execute these steps under the 2026-10-08 implementation authorization. No work package
requires a new product decision within its stated scope. Legacy retirement remains
excluded until its separate acceptance gate and removal scope are satisfied.

1. Inspect HEAD and dirty state. Preserve unrelated edits. Refresh the source
   baseline if HEAD differs, confirm callers, and capture failing/counting cases
   before their refactors. Use the same line/AST method for final accounting.
2. Establish RF-034 final paths and lightweight import boundaries, then apply RF-025, RF-026, RF-027 and RF-033 in that order where their record/Flow/
   scenario files overlap. Apply RF-024 then RF-032 as one coordinated core sequence.
   RF-028 then RF-029 share workflow preparation and can form a separate sequence.
   RF-030 then RF-031 share publication consumers. Independent sequences can run
   in parallel only with exclusive file ownership and explicit integration points.
3. Update each package's imports, exports, tests and manifest paths with its source
   changes. One integration owner reconciles shared manifest files and API guides;
   do not postpone broken manifest references to the final test run. Search all
   maintained source/docs/notebooks for retired names and classify historical hits.
4. Run focused tests after each stable work package. Do not edit semantic sources
   while fingerprint-sensitive tests run. Inspect the combined diff for lost
   diagnostics, duplicated helpers, changed identity encodings and optional-import
   regressions before broad acceptance.
5. Run the combined acceptance below. Record actual commands, environment, results,
   limitations, deletions and size changes. Update current architecture/naming/API
   guides and this plan's status to match the verified implementation. Preserve the
   first plan's acceptance record; add only a link to this pass's final record.

## Combined acceptance and reduction criteria

Use [Verification](../../contributing/verification.md) for environment and tooling instructions.
From `src`, run the full Python suite with required layout solvers:

```sh
MPLBACKEND=Agg .venv/bin/python -m pytest -q --require-layout-solvers --ignore=tests/legacy/test_api.py
```

Missing required solver engines or skips are not acceptance. The three live
predecessor service tests remain explicitly excluded. Run the pinned schema
generation checks, structural/native/domain conformance, type checks including
intentional invalid fixtures, and installed-wheel import/runtime checks for the
affected execution, financial, table and workflow slices. No wire schema changes are planned. Regenerate Python for the new package imports;
confirm schema resources and C# fields are unchanged and all generated files
match their generators. Source manifests record the changed generator paths/hashes.
Execute maintained examples/notebooks affected by API moves; check renderer and
saved-layout behavior. Report unavailable external checks separately.

| Completion criterion | Required evidence |
| --- | --- |
| Ownership and deletions | RF-024–RF-034 deletion/merger targets complete; exact module count includes new package initializers; no forwarding shims; maintained callers use final owners |
| Repeated work | Linear Specification exports; one record-construction copy; one selected-scope/Evidence preparation and one layout arithmetic assessment per matching operation |
| Behavior | Existing independent mathematical/identity oracles plus focused negative and boundary regressions; no changes to wire, pins, stored evidence or mathematical algorithms |
| Diagnostics and failure | Original contributor locations, partial failures, malformed inputs, publication interruption and competing writers retain their contracts |
| Provenance | Final source inventories work from the wheel; semantic edits affect the proper fingerprint; presentation exclusions and unavailable-replay behavior remain explicit |
| Size | Net reduction in active handwritten implementation across the pass; count all affected owners/callers once and explain any local growth |
| Delivery record | Actual verification results and limitations, before/after counts, API migration notes and current documentation; no inherited test count presented as a new pass |

The eight direct deletion targets are `_coordinates.py`,
`model/formulation/traversal.py`, `model/_scenario.py`,
`calculations/dynamics/noise.py`, `workflow/_shared.py`, `workflow/_artifacts.py`,
`adapters/errors.py` and `execution/evaluator.py`. RF-033 also replaces
`calculations/dynamics/{__init__,trend,volatility,cyclicality,shock}.py` with one
`calculations/dynamics.py`: five old files removed and one added. The combined
expected active module count before RF-034 was 219 → 207, a net reduction of twelve.
RF-034 changes the module accounting as specified above; measure its combined result. Do not count legacy retirement toward it.

Record added, removed and net physical lines and AST class/function counts using
the same baseline method. Separate runtime, generators, generated output, tests
and documentation; identify formatting-only changes. Do not delete tests or
compress formatting to claim reduction. Most moves are line-neutral, so the
duplicate preparation/branches and unused state must produce the net reduction.
RF-025 permits a small local helper increase for a single-copy boundary; any other
growth needs an explicit contract-based explanation in the implementation record.

## Implementation record

Implemented on 2026-10-08 against `5a111b00bb4990a883af08d6ccbc7561b4bab445`.
The user authorized commit and push on 2026-10-08. The final hierarchy above is
the import contract. The earlier plan's
schema migration and acceptance record remain unchanged.

| Intent | Delivered behavior |
| --- | --- |
| RF-024 | One Specification collector/catalogue; shared contributor records and role checks; removed unused `Prepared.values`, traversal forwarding and unused units arguments. Batch regression uses 1/10/50 leaves and verifies 3/12/52 exports, one export/load per revision. |
| RF-025 | Record construction copies JSON once and calls the private structural checker; public validation keeps its defensive copy and issue conversion. Nested mutation, cycle and malformed-record failures remain covered. |
| RF-026 | `Flow.coordinate_index()` owns coordinate identity and duplicate rejection. Alignment retains its own order/join policy. Examples use `Flow.from_periods`; redundant enum checks are removed. |
| RF-027 | Scenario conformance resides in `model.scenario.contracts`; captured inputs reuse Model validation; noise sampling calls Distribution directly. |
| RF-028 | Workflow specification owns expansion; provenance owns configuration/metadata/lineage; `Produced.from_evidence` and one mapping helper replace repeated construction. |
| RF-029 | Source checks prepare each exact Evidence object once per call; aliases share preparation, distinct/equal objects do not. Global/row/cell order, source filters and empty-column checks remain intact. |
| RF-030 | `io._atomic.replace_json` replaces both controller wrappers and keeps publication, durability and interruption semantics. |
| RF-031 | Projection materializes each selected collection once. Iterative topology preparation serves checks, rendering and both formulations; assessment combines findings and metrics. Saved/solver results still require independent checks. Adapter aliases are removed. Shared-DAG, 1,100-group chain and preparation-count regressions pass. |
| RF-032 | Execution comparisons live in acceptance; finite arithmetic lives in expression evaluation under `finite_quantity`. The evaluator forwarding module is removed. |
| RF-033 | Five deterministic kernels share `calculations/dynamics.py`. Their executable arithmetic ASTs match the baseline; independent numerical oracles remain unchanged. |
| RF-034 | Schema/shared foundations and Model–Specification–Run owners are integrated; workflow owns Evidence. Imports, generators, resources, type exports, worker entry point/path, manifests, examples, notebooks and maintained guides use the final hierarchy. Retired namespaces have no aliases. |

### Format and provenance checks

Schema and slot JSON are byte-identical to the baseline. Generated C# wire fields
and transport constants are unchanged; only the source manifest records new
paths/hashes. Python generated fields and enum values are unchanged; record imports
use the relocated runtime and behavior modules.

Persisted Evidence profiles remain `rk.evidence/v1` and `rk.table-evidence/v1`.
The calculation contract name remains `rangekeeper.scenarios.market`, and the unit
implementation identifier remains `rangekeeper.units/1`; these are stable protocol
names, not Python import paths. Source-based implementation fingerprints change
for the relocated implementation. Historical current-format results remain readable;
replay still distinguishes unavailable implementations from invalid documents.

Execution, scenario and workflow retain separate manifests. Scenario provenance
also includes the Model/provenance validation sources now used by captured-input
validation. Workflow retains exact installed-code audit separately from semantic
computation and excludes presentation controllers. Independent arithmetic checks
remain separate from solver formulations.

### Local acceptance evidence

The final full suite passes: **1,478 tests, zero skips**. Logs, preserved input baselines, executed
notebooks and accounting scripts are in `/private/tmp/rk-followup-20261008`.

| Check | Result |
| --- | --- |
| Full Python suite | 1,478 passed in 188.22 seconds with required MiniZinc/CP-SAT and Z3; zero skips; three live predecessor service tests explicitly excluded |
| Python/C# generators | Both `--check` commands pass; all generated outputs match |
| Conformance | All seven schema suites pass: structure, native round trip, expressions, formulations, Models, Specifications and Runs |
| Stock native bundle | 16 active fixture round trips pass |
| Typing | All 209 selected sources/valid fixtures pass; invalid fixtures retain all 38 intended errors |
| Installed wheel | Final isolated wheel passes base/runtime, execution, workflow, financial and table slices, including genuine forward/inverse solves and Polars/CSV with pandas absent |
| Walkthroughs | All seven execute in fresh kernels: 91 code cells, fixture design inputs, outputs kept outside the checkout |
| Standalone examples | Valuation/composed forward-inverse and XLSX workflow-to-solver examples pass with stored Run validation |
| Independent review | Core, temporal and workflow reviews complete; wire-string and validation/preparation findings resolved |

The full-suite command runs from `src` with `MPLBACKEND=Agg`, a writable
`MPLCONFIGDIR`, and `RK_MINIZINC` pointing to MiniZinc 2.10.1 with CP-SAT 9.15:

```sh
.venv/bin/python -m pytest -q --require-layout-solvers --ignore=tests/legacy/test_api.py
```

Generator/conformance/type commands use the pinned schema environment. Installed
wheel verification supplies runtime, execution, workflow, financial and table
interpreters to `tools/schema/verify_install.py`. The local runtime is Python
3.10.19; schema tools use Python 3.12.12. No Rhino/Windows host, live connector,
Linux execution or remote CI pass is claimed. This pass does not rebuild the
examples/walkthrough website or change viewer TypeScript/assets.

### Size and deletion accounting

<!-- followup-counts-start -->
| Source category | Files before → after | Physical lines before → after | Added / removed lines | Classes before → after | Functions before → after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Active handwritten Python | 219 → 200 | 29,572 → 29,496 | +1,997 / −2,073 | 210 → 210 | 1,018 → 1,024 |
| Generated Python | 3 → 3 | 8,544 → 8,544 | +5 / −5 | 220 → 220 | 515 → 515 |
| Legacy Python | 22 → 22 | 4,100 → 4,100 | +49 / −49 | 52 → 52 | 180 → 180 |

Active handwritten Python decreases by **19 modules and 76 lines**. Generated
Python changes only five import lines. Generated C# has one changed manifest;
its four output artifact hashes are unchanged.

| Supporting changes | Files changed | Added / removed physical lines |
| --- | ---: | ---: |
| Python tests | 63 | +842 / −449 |
| Generators, typing and conformance tools | 23 | +206 / −113 |
| Notebook sources | 7 | +21 / −21 |
| Maintained Markdown, including both plans | 26 | +509 / −212 |
<!-- followup-counts-end -->

Relocations are matched to final owners before counting changed lines. Merged
sources are grouped once; new initializers count as additions. Physical lines
include whitespace and comments. Classes/functions use Python AST counts.
The active module reduction is 19: twelve from RF-024–RF-033, plus seven net from
RF-034's facade/initializer mergers after adding the shared initializer.
There are no new runtime classes. The small net increase in function count comes
from explicit local preparation/check operations and lazy package exports.

Legacy retains all 22 modules and 4,100 lines; only necessary canonical imports,
exception names and one ownership docstring changed. None of that work counts
as consolidation. Expanded imports and Black formatting are included in runtime
line totals, not claimed as separate simplification. Test growth adds boundary,
identity and work-count regressions; it does not mirror arithmetic implementations.
Maintained documentation preserves unrelated README/contributor changes.
