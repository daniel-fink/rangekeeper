# Rangekeeper library architecture and migration plan

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
The [date-only correction](research/full-migration/date-only/README.md) removes
TimePoint. Period movements store coverage; a separate date is optional and records
an independent payment or observation. Dated valuation requires explicit timing
when the movement has no recorded date.
[Financial-library integration](research/full-migration/financial-library/README.md)
now delegates PV, XNPV, IRR and day counts to PyXIRR. The draft mandatory IRR
bracket is replaced by an optional initial guess.
Turn 2 is implemented; see the current contract and verification linked above.
Turns 3–4 finish remaining consumers and retire old modules. The six-checkpoint
history below remains the scalar/core work record; full migration is not complete.

**Full-refactor review, 2026-10-03:** [Full migration review](FULL_MIGRATION_REVIEW.md)
expands the consumer/retirement scope to numerical, temporal, scenario and policy
behavior. It proposes detailed ownership, a package tree and acceptance checks.
`model.duration` and `formulations/flow.py` are the selected names; remaining
details are engineering design work, with no current user-input blocker. The scalar architecture below
remains implemented. Root numerical modules are retained code, not completed
integration with the canonical Model.

Status: agreed architecture and revised implementation sequence, 2026-10-02. This document
describes the target library and the route to its first executable checkpoint.
The Model/Specification/Run core, codecs, revision stores and root exports are now
implemented. [Step 5 scalar execution](SCALAR_EXECUTION.md) is also implemented;
[Model-backed views, hierarchy and reductions](GRAPH_MODEL.md) now implement
Step 6A/6B. [Tables, adapters, and source workflows](CONSUMER_MIGRATION.md)
now implement 6C/6D. External consumer migration (6E) remains part of full migration Turn 3.
Step 1 is complete: the [migration map](DOMAIN_MIGRATION_MAP.md) fixes the concrete
interfaces and factoring; the [baseline](research/domain-migration/BASELINE.md)
records observed results. Those detailed decisions refine the responsibility tree
below. Work units 2A/2B are now implemented: [record boundary](RECORD_BOUNDARY.md)
and [verification](research/domain-migration/turn1/README.md). Work units 3A/3B are
also implemented: [domain APIs](DOMAIN_CORE.md) and
[Turn 2 evidence](research/domain-migration/turn2/README.md). Work units 3C/4 are also
implemented: [Run and storage](RUN_AND_STORAGE.md) and
[Turn 3 evidence](research/domain-migration/turn3/README.md). The
[scalar evidence](research/scalar-execution/README.md) records actual forward/inverse
solves and output reuse. The intervening
[validation refactor](DOMAIN_CORE.md#composable-validation) is implemented: shared
invariants are domain-independent, local naming rules are reused, and mathematical
checks consume an explicit data scope.

The semantic record contracts are described in
[Model, Specification, and Run](MODEL_SPECIFICATION_RUN.md) and the
[schema reference](../schema/README.md). This document supplies the Python library
boundaries, repository layout, and migration order. The
[policy example](PROJECT_DEFINITION_AND_POLICY_EXAMPLE.md) remains a later stage.

## Decisions and current state

- LinkML is the selected authority for record structure. Daniel closed the CUE
  comparison on 2026-10-02: the potential native-CUE benefits do not justify the
  integration and migration costs for this stage. The
  [decision and evidence](research/current-schema-comparison/DECISION.md) preserve
  the distinction between import-route failures and untested native capability.
  Two independently maintained authoritative schemas are excluded.
- The public domain concept is `rk.Model`, implemented through `rk.model`. It
  evolves the current graph foundation to include the complete schema envelope.
  `Specification` and finalized `Run` are separate documents.
- Pyomo with HiGHS is the selected primary algebraic backend for the first
  affine scalar checkpoint. Pyomo 6.10.1 and HiGHS 1.15.1 are now probed, pinned
  and integrated as the optional execution extra. SymPy may support exact affine analysis
  and test oracles; it is not a competing production solve path.
- Map replacement of the existing domain core before implementing execution.
  Build the minimal schema-backed core directly in its intended library packages,
  then implement the scalar executor against it. This supersedes the earlier
  temporary `schema/execution/` implementation and later promotion plan.
  Migrate graph consumers, adapters, and numerical capabilities incrementally;
  the first solve does not require moving or rewriting the entire repository.
- Preserve native UUID identity, immutable revisions, additive Specification
  composition, and the separation between recorded quantities and solve roles.
  `Study` names the larger analytical process; no new Scenario or Evaluation
  object is required for this checkpoint.

The starting schema checkpoint is commit
`c91a76c941bac0a26fa18ad5a3105ab4641f22f0` on `feature/graph`.
Continuation work uses the local branch `acausal-modelling`, created from
that commit. The unrelated Syncthing `.gitignore` edit is preserved and excluded
from this work's changes. Creating this branch does not publish subsequent work.

At this checkpoint, `schema/` contains the LinkML records, synthetic fixtures,
and structural/semantic/native-round-trip checks. `src/rangekeeper/graph/`
retains the old domain pending consumer retirement and hosts the new Model graph
algorithms. Model-backed adapters and source workflows now live at
`src/rangekeeper/adapters/` and `src/rangekeeper/workflow/`. The numerical library includes distributions, extrapolations,
projections, durations, Flows, Streams, and financial functions. The new executor
produces separately retained authentic Runs/outputs; the original schema fixtures
remain synthetic conformance expectations.

## Responsibility layers

| Layer | Responsibility | Proposed Python home |
| --- | --- | --- |
| Schema | Records, fields, identities, references, variants, and structural rules. | Authoritative LinkML sources under `schema/`. |
| Domain object model | Schema-adherent Models, Definitions, System, Values, mathematical records, provenance, Specifications, and finalized Runs. | `model`, `specification`, `run`. |
| Mathematical library | Reusable construction of explicit mathematics and supported numerical/symbolic implementations of Functions. | `formulations`, using existing numerical modules where appropriate. |
| Semantic validation and compilation | Resolve references, compose requirements, establish roles, check types/units/capabilities, and prepare mathematical expressions for lowering. | Domain validation and `execution`. |
| Execution and acceptance | Evaluate or solve, enforce limits, account for batches, verify candidates, and publish immutable outputs and evidence. | `execution` and its backend adapters. |

Serialization, revision resolution, and persistence support these layers through
codecs and a record-store interface. Selecting a production database is separate
from establishing immutable local records.

### Model, graph, Specification, and Run

The Model envelope contains `metadata`, `definitions`, `system`, and
`provenance`. System contains Entities, Relationships, Assemblies, and
Formulations. Specifications pin input Models and define investigation roles
and requirements. Runs pin attempted Specifications and reference accepted
output Models and direct subordinate Runs.

`graph` supplies views, traversal, querying, reduction, and related algorithms
over the Model's canonical objects. Derived indexes and projections are useful;
independently authored Model and Graph copies must not compete as authorities.
The current Graph cannot become the complete new Model merely through renaming.

A Run is the finalized evidence record. The executor is the service performing
the work. Mutable solver state and live progress remain private runtime state.

### Value content and governing mathematics

A scalar measurement, Flow or property supplies Value content.
Stream is a revision-pinned runtime selection of canonical Flow Values.
Flow and duration content are implemented; persistent Account payloads remain
subject to their later acceptance stage.
A Formulation groups the governing Expressions, Constraints, local Values, and
references to shared Values. An Account's balances and movements are content;
balance continuity, interest, and repayment equations are mathematics.

`model/formulation.py` represents the schema-defined Formulation record.
`formulations/` supplies Python construction helpers and supported mathematical
implementations. Helpers can return explicit Formulation records without
introducing a template-reference mechanism into the schema.

Numerical evaluation and symbolic construction are separate capabilities.
Existing pandas-based Flow and Stream operations do not represent unknown
movements automatically. A supported symbolic implementation must preserve every
unknown-dependent expression. Random sampling can generate saved solve inputs;
it must not precompute unknown-dependent quantities as fixed coefficients.

### Dependencies and generated records

- Domain records and their validation do not depend on Pyomo, solvers, or live
  execution state. Backend adapters depend on the prepared domain mathematics.
- Graph algorithms and formulation builders use the canonical domain objects.
  Mathematical construction does not execute the Model implicitly.
- The numerical acceptance evaluator traverses the original declared expressions
  with candidate quantities, independently of the backend's compiled constraints.
- The authoritative schema owns record shape. Handwritten Python owns semantic
  behavior, indexing, compilation, execution, and publication. Do not maintain
  another handwritten schema with competing field definitions.
- Schema-derived record machinery is private. Generated or bundled artifacts
  carry a source/version fingerprint, are reproducible, and are not edited
  independently. Installed packages must contain their required artifacts rather
  than resolve paths back into a source checkout.
- Importing core domain objects should not initialize solvers, notebook tooling,
  or integrations. Keep execution dependencies optional from the first library
  implementation and test installed-package behavior at that checkpoint.

Generate stock native records for interoperability checks and an immutable runtime
projection from the same Model/Specification/Run import bundle, plus pinned closed
JSON Schemas. Use thin handwritten document facades and generated nested records;
local behavior is supplied by functions, avoiding a wrapper hierarchy for every
schema class. The bounded 50-class probe demonstrated feasibility. Production
constructor validation, typing, packaging and shared semantic validation remain
required; native construction alone is not complete validation.

## Target repository layout

Keep the existing library, walkthrough, and integration project boundaries.
The library project remains rooted at `src/pyproject.toml`. The tree below is a
target decomposition; create files as their implementation checkpoint requires.

```text
Rangekeeper/
  README.md
  schema/                         # authoritative schema sources
    examples/                     # valid inputs and synthetic expectations
    README.md
  tools/
    schema/                       # generation and conformance commands
  docs/
    LIBRARY_ARCHITECTURE.md
    MODEL_SPECIFICATION_RUN.md
    research/                     # retained comparisons and evidence
  src/
    pyproject.toml
    uv.lock
    rangekeeper/
      __init__.py                 # public Model, Specification, Run APIs
      _schema/                    # schema-derived machinery and manifest
      model/
        model.py                  # immutable envelope and revision scope
        definitions.py
        system.py
        characteristics.py
        measure.py
        entity.py
        relationship.py
        assembly.py
        expression.py
        formulation.py            # mathematical record/container
        provenance.py
        validation.py
      specification/
        specification.py
        composition.py
        validation.py
      run/
        run.py                    # finalized record
        validation.py
      formulations/
        valuation.py              # helpers constructing explicit mathematics
        ...                       # later supported mathematical families
      execution/
        preparation.py            # scope, roles, units, capabilities
        compiler.py               # typed mathematical preparation
        evaluator.py              # evaluation of original Expressions
        acceptance.py
        publication.py
        executor.py               # attempts, limits, batches
        backends/
          pyomo.py                # lowering and selected solver integration
      graph/                      # views and algorithms over canonical objects
      table.py                    # planned shared Row/Table container for Step 6C
      io/                         # codecs and immutable revision storage
      adapters/                   # file, visualization, service integrations
      workflow/                   # source-to-Model construction workflows
      ...                         # existing numerical modules, evolved gradually
    tests/                        # domain, execution, graph, adapter conformance
  walkthrough/
  grasshopper/
  hypar/
```

Build the first implementation directly in the library. The initial working
slice uses `_schema/` for generated records and structural validators, `model/`,
`specification/`, and `run/` for domain behavior, `io/` for codecs and immutable
revision storage, and `execution/` for the executor and backend adapter. Exact
module interfaces and the generated-record boundary are now specified in the
[migration map](DOMAIN_MIGRATION_MAP.md). This tree specifies responsibilities, not
a requirement to create empty files; use the map for concrete file names.

`tools/schema/` owns reproducible generation commands. Existing `schema/checks/`
entrypoints remain conformance checks and should delegate to shared library
validators as those are implemented. `schema/` continues to own the authoritative
LinkML sources and fixtures; it is not a temporary home for the production runtime.
Research probes may remain under `docs/research/` without becoming a second core
or executor. Keep observed outputs separate from synthetic expected fixtures;
execution commands accept an explicit output directory.

## Mapping existing code

The existing domain core requires substantial replacement. This is a change in
ownership, record meaning, and persistence, not a package rename. The inventory
below is based on inspection of the current code; reuse candidates still require
behavioral characterization. It does not claim that every graph algorithm or
numerical routine must be rewritten.

| Current responsibility | Required change | Intended home |
| --- | --- | --- |
| `graph.Graph` owns domain objects, definitions, and provenance | Replace the canonical container with a complete immutable Model revision, including Metadata, System, and Formulations. Graph indexes become derived access structures. | `model`, `io`; views in `graph` |
| Handwritten Entity, Classification, Definitions, Characteristics, Measurement, and Feature records | Establish schema-derived shape with domain behavior. Replace separate measurement/feature collections with identified, locally keyed Values; preserve supported meaning explicitly. | `_schema`, `model` |
| Object-instance-based reference checks and Fact targets | Resolve UUIDs within pinned revision scopes. Python accessors may expose canonical resolved objects without making Python object identity the serialized contract. | `model`, `specification`, `io` |
| Graph revision, diff, and update machinery | Cover the full Model envelope and mathematical records; preserve lineage, identity, and immutability. Reuse generic diff logic where its assumptions hold. | `model`, `io` |
| Registered-class Graph JSON codec | Implement schema-adherent Model/Specification/Run codecs. The existing format is not the new Model interchange contract. | `io` |
| `View`, traversal, filtering, topology, reduction, and table projection | Reuse suitable algorithms over canonical Model objects or explicit projections; revise Value lookup, aggregation rules, and ownership assumptions. | `graph` |
| Pure routines in `schema/checks/*_contract.py` and Specification composition | Reuse and evolve semantic checks in the library; conformance commands call the same implementation. | `model`, `specification`, `run`, `execution` |
| Root `measure.py`, exports, and integration entrypoints | Separate schema-defined Measure content from Pint/unit operations; reconcile quantity-kind, aggregation, currency conventions, and public imports. | `model`, unit support, package exports, adapters |
| `graph/adapter` and root `api.py` | Adapt persistence and domain bindings, retaining useful format-specific reading/writing. Move integrations once the new interfaces are verified. | `adapters` |
| `graph/workflow` | Preserve useful ingestion/evidence operations; replace graph construction with Model construction and migrate consumers explicitly. | `workflow` |
| Flow, Stream, Account, and callback-based Policy abstractions | Separate numerical content/operations from schema Value payloads and symbolic governing mathematics. Rich payloads and policy contracts are later work. | Numerical support, later `model` and `formulations` |
| Distributions, durations, extrapolations, projections, financial calculations | Characterize and retain numerical algorithms where correct. Add explicit bridges and supported symbolic formulations as required; do not automatically turn each numerical class into a schema record. | Existing numerical modules initially; `formulations` as needed |

For example, current Characteristics keys measurements by Measure code; the
schema gives each Value an owner-local key and permits multiple Values using
one Measure. Graph currently contains Assemblies among Entities, whereas the
Model stores Assemblies once in a separate System collection. The current Graph
also lacks Formulation-local Values and the complete mathematical reference scope.
These are observable model differences, not changes that moving files can fix.

Generated records and public domain APIs are different responsibilities, but
must not become independently authored field schemas. Step 1 selected generated
immutable nested records with thin document facades, pinned UUID lookup and atomic
new-revision construction. The migration map records the exact interfaces.

The existing `WorkflowSpec` configures a source-building workflow. The new
`Specification` configures a mathematical investigation. They remain distinct.
Old graph consumers can remain operational during staged migration, but must not
become a second authority for the same new Model. Use explicit conversion when
required, documenting unsupported content; do not silently translate away schema
meaning. Compatibility is not a reason to retain obsolete domain semantics.

The completed migration map identifies affected consumers/tests, intentional API
breaks, replacement/reuse decisions, generation/storage interfaces, and retirement
conditions. Feature-rich consumers explicitly wait for supported payload contracts.
Full consumer migration can follow the first scalar solve; the canonical replacement core must precede it.

## Migration checkpoints

The [schema decision](research/current-schema-comparison/DECISION.md) is settled:
retain LinkML. The import probe and independent audit remain evidence; a complete
native CUE evaluation was not performed and is no longer required for this stage.
The schema-backed library core and affine scalar executor are implemented.
The checkpoints below retain the agreed sequence; Steps 1–5 are complete locally.

The [domain migration plan](DOMAIN_MIGRATION_PLAN.md) supplies the detailed work
breakdown, Step 1 discovery procedure, deliverables, and completion criteria.
Its six checkpoints refine and supersede the earlier migration numbering.

1. **Establish the migration baseline — completed.** Map canonical objects, current/public
   interfaces, generated-record ownership, UUID resolution, snapshot/store behavior,
   affected consumers, and tests. Classify replacement, adaptation, retention, and
   deferral. Record actual baseline results and ordered implementation slices.
2. **Establish generated records and validation.** Generate shared LinkML records,
   closed structural schemas, and a manifest into private `_schema` artifacts.
   Move reusable semantic checks into the library and redirect conformance commands
   to them. Verify reproducibility, omission/null/zero/false, meaningful ordering,
   and intended corpus outcomes. Begin package-artifact and dependency checks here.
3. **Implement the canonical domain and revision boundary.** Build Model,
   Specification, Run, composition, codecs, and revision storage in their intended
   packages. Establish immutable public access, canonical ownership, and typed,
   revision-scoped reference resolution. Verify round trips, nested immutability,
   new-revision creation, duplicate writes, and conflicting-content rejection.
4. **Complete the first usable library checkpoint.** Finalize public construction,
   loading, validation, and revision interfaces; expose `rk.Model`,
   `rk.Specification`, and `rk.Run`. Verify required artifacts in an installed
   package outside the checkout, lightweight imports, and optional execution
   dependencies. A user can load a Model, compose its Specification, resolve
   required references, and save an immutable revision through the library.
5. **Implement and verify scalar execution.** Probe Pyomo/HiGHS
   in isolation and pin tested versions. Under `rangekeeper.execution`, load the
   actual valuation Model and composed Specifications through the new core,
   prepare units and roles, lower declared equations, solve, independently verify
   serialized candidates, and publish authentic Runs and immutable output Models.
   Support arithmetic affine after assignments, equality and nonstrict bounds;
   report unsupported content, resource limits, and mathematical conclusions
   accurately. Include actual output reuse and sequential batch cases.
6. **Migrate consumers and retire the old domain implementation.** Adapt views, traversal,
   reductions, tables, provenance access, and diff/update behavior. Migrate each
   adapter, workflow, and consuming project with explicit acceptance checks; retire
   superseded domain classes and codecs as their consumers move. There is one
   canonical new Model and one executor throughout. Finish namespace changes,
   integration/walkthrough migration, and removal of superseded code.

Steps 1–4 form the first implementation slice. Consumer discovery begins in Step 1;
particular consumers can migrate earlier when needed to verify a core interface.
Full migration Turn 1 now supplies temporal Values, Flow/Stream content and known-data
calculations. Indexed formulations and policy evaluation remain Turn 2 work. Check
numerical/symbolic agreement with explicit calendars, units and stock/flow conventions.

## First executable acceptance boundary

The first checkpoint implements the scalar slice of the layers above. It does
not require temporal Values, policy optimization, structural interventions,
market-generator inversion, a production database, or migration of every existing
graph consumer. It does require the minimal canonical replacement core in the
library; the old Graph is not the authoritative state behind the new executor.

Use the same declared relations throughout:

```text
NOI = homes * annual_rent_per_home - annual_operating_cost
capital_value * capitalization_rate = NOI
```

Acceptance must demonstrate:

- Forward assignments produce NOI `550,000 AUD/year` and capital value
  `11,000,000 AUD`.
- Inverse assignments produce annual rent `27,500 AUD/dwelling/year` and NOI
  `500,000 AUD/year`.
- New Specification revisions pinned to the actual forward output reproduce the
  inverse investigation. Recorded rent `30,000` does not fix the next solve.
- Changed inputs and declared expressions change the calculation; no separate
  hard-coded forward/inverse formulas produce these answers.
- Supported units, assignments, equations, and bounds are verified against the
  proposed serialized quantities before publication. Temporary Specification
  mathematics does not become permanent output Model mathematics.
- Composition conflicts, unsupported operations, inconsistent/underdetermined
  systems, numerical rejection, and resource limits produce accurate evidence.
  A timeout or solver failure is not an infeasibility proof; finding a feasible
  candidate does not establish uniqueness or optimality.
- Every direct batch case has a child Run, including failures. Parent outputs
  are exactly the unique union of accepted child outputs.
- New Model revisions preserve definitions, declaration identities, unrelated
  content, lineage, and valid provenance. Runs identify actual implementations,
  settings, timing, termination, residual conventions, diagnostics, and trace.

Structural preflight, mathematical compilation/solution, numerical acceptance,
and publication are separate checks. Enforce a worker deadline and account for
each requested numerical setting, including requests that cannot be applied.
Keep solver tolerances distinct from dimensional acceptance tolerances.

Rerun the seven schema suites and targeted Python compatibility tests at the
relevant checkpoints. Establish the current baseline before migrations and
report the previously identified adapter-export failure separately if it remains.
Do not expand scalar execution work into unrelated adapter repair.

Commit, push, release, and deployment are separate from local implementation and
validation. This document records the plan; it does not authorize publication.

## Market and scenario naming

See the [RK naming update](RK_NAMING.md) for the typed Market view, shared Distribution and Binding records, RandomStream, DecisionHistory, component constructors and explicit scenario draft upgrades.
