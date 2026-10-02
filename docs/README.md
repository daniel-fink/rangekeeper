# Rangekeeper documentation and current work plan

Updated 2026-10-02. This index distinguishes the active acausal-modelling plan,
existing graph APIs, and historical research. A planned API is not evidence of
an implemented runtime.

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
- **Use Pyomo with HiGHS.** Backend selection is settled; tested versions and actual
  execution integration still need to be established.
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
  Scalar execution is next. No new
  schema-backed library executor has produced the synthetic Run/output fixtures.
- **The CUE audit is complete within its stated scope.** All seven schema suites
  passed again. The original bounded import probe reproduced case for case; the
  full five-second pass produced 572 matching outcomes, 28 differences, 106
  timeouts, and seven non-JSON inputs across 713 pairs. These are import-route
  observations, not native CUE or semantic-parity results.
- This checkpoint contains the documentation/research and Turn 1–3 implementation
  on `acausal-modelling`, built from `c91a76c`. Retained verification snapshots record
  the pre-commit state. The unrelated `.gitignore` edit is excluded from the checkpoint.
  Recheck live state before implementation; preserve unrelated work.

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
5. **Next: implement and verify scalar execution.** Probe/pin Pyomo/HiGHS, execute the
   declared mathematics, independently check candidates, and publish authentic Runs.
6. **Migrate consumers and retire the old domain implementation.** Adapt graph
   operations, adapters, workflows, integrations, and walkthroughs with acceptance checks.

The [domain migration plan](DOMAIN_MIGRATION_PLAN.md) records these six checkpoints
and the detailed Step 1 work plan. Steps 1–4 form the first implementation slice.
Richer numerical/temporal Values, scenario evaluation, and adaptive policies follow
the scalar checkpoint and the consumer interfaces they require.

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
| [Library architecture](LIBRARY_ARCHITECTURE.md) | Current package responsibilities, replacement map, implementation sequence, and acceptance criteria. |
| [Run and storage](RUN_AND_STORAGE.md) | Implemented Turn 3 public roots, finalized Runs, strict codecs, immutable stores and execution boundary. |
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
