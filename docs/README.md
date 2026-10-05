# Rangekeeper documentation and current work plan

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
Start with the [duration namespace migration](FULL_MIGRATION_TURN1.md#duration-namespace-migration):
`temporal/` will become `duration/`, while `model.duration` remains the record module.
The 2026-10-05 decision includes the old-caller transition and verification gates;
the runtime rename is pending and adds no implementation turn.
Turns 3–4 finish remaining consumers and retire old modules. The six-checkpoint
history below remains the scalar/core work record; full migration is not complete.

Updated 2026-10-06. This index distinguishes the active acausal-modelling plan,
existing graph APIs, and historical research. A planned API is not evidence of
an implemented runtime.

Current consumer checkpoint: [Model tables, adapters, and source workflows](CONSUMER_MIGRATION.md)
(6C/6D), with [verification](research/consumer-migration/README.md), committed at
`90c2e00`. The expanded [full migration scope](FULL_MIGRATION_REVIEW.md) now has
a four-turn implementation sequence and a delivered Turn 1 foundation.
It covers all remaining older behavior, numerical/temporal redesign, parallel
workbench/layout features, consumer proof, retirement and future upgrade guidance.
6E/6F remain open. Turn 1 schema/API implementations and remaining proposals
are distinguished in [the current contract](FULL_MIGRATION_TURN1.md).

## Overall goal

Evolve Rangekeeper into an acausal, equation-oriented modelling system:

```text
Model + Specification → finalized Run + accepted immutable output Models
```

The Model holds project structure, Values, governing mathematics, and provenance.
The Specification supplies assignments, unknowns, and investigation-specific
requirements. The same equations serve different investigations; recorded results
do not become permanent constraints. The eventual destination is evaluation of
development choices and adaptive policies across market scenarios.

## Current decisions and state

- **Retain LinkML.** Daniel closed the CUE comparison for this stage after reviewing
  the evidence and integration trade-offs. Native CUE suitability was not fully
  evaluated; this is a deliberate choice, not proof that CUE cannot meet the contract.
- **Use Pyomo with HiGHS.** Pyomo 6.10.1 and HiGHS 1.15.1 are pinned and verified
  through actual scalar execution and installed-wheel checks.
- **Replace the domain foundation before execution.** The existing Graph container,
  Characteristics/Value representation, identity resolution, revision machinery,
  and persistence do not implement the complete schema contract. Build the minimal
  replacement core directly in its intended library packages. Graph algorithms
  and numerical routines are candidates for reuse, subject to characterization.
- **Step 1 is complete.** Seven schema suites pass; the supplemental local runtime
  has 491 passing tests and two reproduced baseline failures. The generated-record
  feasibility probe passed 14 checks over 50 classes and 14 document fixtures.
  External-service and downstream-project execution remain unverified.
- **Step 2 is implemented.** The [record boundary](RECORD_BOUNDARY.md) supplies generated
  immutable records and shared structural/bounded semantic validation.
  [Turn 1 verification](research/domain-migration/turn1/README.md) records the new checks.
  [Turn 2](DOMAIN_CORE.md) adds Model lookup/revision, units, and immutable Specification
  composition; [evidence](research/domain-migration/turn2/README.md) records verification.
  Shared helpers and domain rules have since been separated in the
  [validation refactor](DOMAIN_CORE.md#composable-validation), with
  [retained verification](research/domain-migration/validation-refactor/README.md).
  [Turn 3](RUN_AND_STORAGE.md) implements Run, codecs, revision stores and root exports;
  [verification](research/domain-migration/turn3/README.md) covers installed-core operations.
  [Step 5](SCALAR_EXECUTION.md) implements actual affine scalar execution with
  independent acceptance, immutable publication and sequential batches; its
  [evidence](research/scalar-execution/README.md) is separate from synthetic fixtures.
  [Step 6A/6B](GRAPH_MODEL.md) now implements Model-backed views, explicit hierarchy
  and Value reductions. [Graph verification](research/graph-migration/README.md)
  records 783 passing tests, the same two baseline failures, and passing schema,
  typing and installed-package checks.
- **The CUE audit is complete within its stated scope.** All seven schema suites
  passed again. The original bounded import probe reproduced case for case; the
  full five-second pass produced 572 matching outcomes, 28 differences, 106
  timeouts, and seven non-JSON inputs across 713 pairs. These are import-route
  observations, not native CUE or semantic-parity results.
- The core checkpoint is `53f5d3e`; scalar execution and Model-backed consumers
  followed in `90c2e00` on `acausal-modelling`. The separately requested 2026-10-06
  foundations checkpoint includes Turn 1 and its date, financial-library, Flow
  semantics and Movement corrections. [Current verification](research/full-migration/movement-naming/README.md)
  records 946 local tests passing, all seven schema suites, typing and installed
  acceptance. The unrelated `.gitignore` edit and Syncthing lock conflict copy
  remain outside the checkpoint. Recheck live state before continuing.

## Implementation sequence and next step

1. **Establish the migration baseline.** Map domain responsibilities, proposed
   interfaces, consumers, API breaks, and tests; classify replacement/adaptation/
   retention/deferral and record current results. **Completed:** see the
   [migration map](DOMAIN_MIGRATION_MAP.md) and [baseline](research/domain-migration/BASELINE.md).
2. **Establish generated records and validation.** Generate the shared private
   record bundle and structural artifacts; move semantic checks into the library.
   **Completed:** work units 2A/2B and the subsequent validation refactor.
3. **Implement the canonical domain and revision boundary.** Build immutable
   Model/Specification/Run access, UUID resolution, composition, codecs, and storage.
   **Completed:** work units 3A–3C.
4. **Complete the first usable library checkpoint.** Expose the public API and
   verify the installed core outside the checkout, with optional solver dependencies.
   **Completed:** work unit 4; external consumer acceptance remains later.
5. **Implement and verify scalar execution — completed.** Probe/pin Pyomo/HiGHS, execute the
   declared mathematics, independently check candidates, and publish authentic Runs.
6. **Consumer migration is underway.** [Step 6A/6B](GRAPH_MODEL.md) implements
   Model-backed selections, hierarchy and reductions. [6C/6D](CONSUMER_MIGRATION.md)
   adds tables, presentation adapters, and source workflows. Before 6E, review
   the expanded numerical/temporal and consumer plan linked above.

The [domain migration plan](DOMAIN_MIGRATION_PLAN.md) records these six checkpoints
and the detailed Step 1 work plan. Steps 1–4 form the first implementation slice.
Richer numerical/temporal Values, scenario evaluation, and adaptive policies follow
the scalar checkpoint and are now within the requested full-refactor scope.
Their exact contracts need the linked engineering design work. The R1–R6 checklist
is not a mandatory user-approval queue; ask only about concrete unresolved meaning
or material scope tradeoffs after investigating the evidence.

The former plan to implement under `schema/execution/` and later promote that
runtime is superseded. The scalar checkpoint uses the foundation we intend to
keep; it does not require migrating every existing consumer first.

Acceptance includes forward NOI of 550,000 AUD/year and capital value of
11,000,000 AUD; inverse rent of 27,500 AUD/dwelling/year and NOI of 500,000 AUD/year;
and inverse reuse of a genuine forward output without inherited solve roles.
Changed-expression tests, units, bounds, failure/limit reporting, provenance,
immutability, and batch accounting remain required. The
[architecture plan](LIBRARY_ARCHITECTURE.md#first-executable-acceptance-boundary)
contains the full acceptance boundary.

## Document responsibilities

| Document | Role |
| --- | --- |
| [Full migration review](FULL_MIGRATION_REVIEW.md), [static inventory](research/full-migration/README.md) | Proposed full-refactor scope, decisions to review, detailed legacy dispositions, temporal/numerical boundaries, consumer proof and retirement gates. |
| [Library architecture](LIBRARY_ARCHITECTURE.md) | Current package responsibilities, replacement map, implementation sequence, and acceptance criteria. |
| [Run and storage](RUN_AND_STORAGE.md) | Implemented Turn 3 public roots, finalized Runs, strict codecs, immutable stores and execution boundary. |
| [Model-backed graph operations](GRAPH_MODEL.md) | Implemented 6A/6B APIs, explicit legacy transition, and remaining Step 6 slices. |
| [Scalar execution](SCALAR_EXECUTION.md) | Implemented Step 5 API, affine capability, solver/acceptance separation, settings, limits, provenance and actual execution evidence. |
| [Model/Specification APIs](DOMAIN_CORE.md) | Implemented Turn 2 domain operations, docstrings, examples and limits. |
| [Record boundary](RECORD_BOUNDARY.md) | Implemented Turn 1 APIs, examples, factoring and verification links. |
| [Domain migration plan](DOMAIN_MIGRATION_PLAN.md) | Six implementation checkpoints and retained Step 1 work queue; Step 1 is complete. |
| [Domain migration map](DOMAIN_MIGRATION_MAP.md), [baseline](research/domain-migration/BASELINE.md) | Concrete Python interfaces, consumer migration, observed tests and feasibility evidence. |
| [Model, Specification, and Run](MODEL_SPECIFICATION_RUN.md) | Current semantic contracts, dated decisions, and explicitly deferred extensions. Exact record shapes are in [`schema/`](../schema/README.md). |
| [Continuation handoff](handoffs/2026-10-02-acausal-modelling.md) | Current resume instructions, plus clearly labelled historical transfer/environment information. |
| [Schema decision](research/current-schema-comparison/DECISION.md) | Accepted LinkML choice, trade-offs, and implementation consequences. |
| [Current-schema research](research/current-schema-comparison/README.md), [audit](research/current-schema-comparison/audit-2026-10-02/README.md) | Reproducible observations and their limits; original evidence is preserved. |
| [Policy example](PROJECT_DEFINITION_AND_POLICY_EXAMPLE.md) | Longer-term design test and illustrative assumptions; not implemented or numerically validated. |
| [Adapter guide](GRAPH_ADAPTER_GUIDE.md), [YAML workflow guide](GRAPH_YAML_WORKFLOW.md), [format-independent workflow](GRAPH_WORKFLOW_FORMATS.md) | Existing source-to-Graph implementation, to be migrated. Workflow execution is distinct from mathematical execution. |
| [Adapter review](GRAPH_ADAPTER_REVIEW.md), [graph refactor plan](GRAPH_REFACTOR_IMPLEMENTATION_PLAN.md) | Historical implementation/review evidence; their old work queues do not override the current architecture. |
| [Earlier tooling evaluation](SCHEMA_TOOLING_EVALUATION.md), [small-schema probes](research/schema-tooling/README.md) | Historical research; recommendations are superseded by the accepted decision. |

For continuation, use the current architecture and handoff. Preserve historical
measurements and delivered API examples rather than relabelling them as new
schema-backed behavior. Documentation updates do not authorize commits, pushes,
or releases.
