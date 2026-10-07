# Rangekeeper refactoring plan

Status: all 23 intents implemented; local acceptance passed. External host checks remain as stated below.

Created: 2026-10-06. Decisions and implementation: 2026-10-07.

This plan collects refactoring intents for one coordinated implementation pass.
The integration decisions, shared contracts and work packages below coordinate
the detailed intents. Resolve routine implementation details within these
contracts and record them before their dependent edits. The user authorized the
implementation after the plan commit and push.

The current [architecture](LIBRARY_ARCHITECTURE.md) and other guides describe the
new ownership. The combined implementation record tracks acceptance evidence.
Problem and baseline sections describe the pre-refactor code; retired source paths
remain as text. Implementation records and current guides describe the final state.

## Overall strategy: reduce and simplify

The primary goal is a smaller codebase that is easier to understand and change.
Target a net reduction in maintained, handwritten implementation code across the
combined refactor. Reduce the number of concepts, branches, wrappers and steps a
caller must understand. Adding classes or modules is not a measure of progress.

Start each intent by identifying what can be deleted, combined or made unnecessary.
Remove redundant helpers, duplicate rules, obsolete paths and needless conversion
between representations. Prefer direct operations on the appropriate owner and
a few cohesive modules. Share an implementation when its callers have the same
contract; keep distinct domain rules and required independent checks separate.

Each new abstraction must replace identified code or establish a necessary
boundary. Review the total cost across its definition, adapters and callers.
Moving a long function into several files does not, by itself, meet the reduction
goal. Avoid forwarding layers, compatibility aliases, speculative extension
points and general frameworks for a single use. Use composition or inheritance
only where it removes repetition and leaves ownership clear.

Preserve required behaviour, identity, provenance, validation and execution
boundaries, except for the explicit behaviour changes agreed in individual
intents. Keep independent numerical acceptance independent of the compiler and
solver. Preserve useful tests and rationale. Follow
[Contributing](../CONTRIBUTING.md): do not reduce line counts by packing statements,
compressing signatures, shortening meaningful names or deleting explanations.

### Reduction evidence and completion

Before implementation, record the affected implementation's size and the code
each intent expects to remove. After implementation, report added, removed and
net lines, together with changes in module, class and function counts. Include
new files and all affected callers; moving code outside a measured directory
does not count as deletion. Use the same counting method and formatting baseline.

Report handwritten implementation, generators, generated outputs, tests and
documentation separately. Generated enum declarations and additional regression
cases must not hide growth in handwritten runtime code, and deleting tests or
documentation must not be used to claim an implementation reduction. Identify
formatting-only changes separately. Counts support review; simpler control flow
and fewer concepts must also be visible in the result.

Each intent must state its deletion targets and explain any expected net growth
before implementation. At completion, record what was removed and compare the
result with that expectation. If an intent or the combined pass increases
handwritten implementation code, identify the required contract or correctness
fix that causes the increase and why a smaller design would not suffice. Do not
silently treat extra layers as simplification. The default target remains a net
reduction; any exception must be explicit in the implementation record.

Apply this strategy to the current intents:

| Intent | Required simplification |
| --- | --- |
| [RF-001](#rf-001-move-observation-availability-rules-to-policies) | Replace both availability rules with one implementation and remove the old helper and redundant caller logic |
| [RF-002](#rf-002-use-canonical-enums-for-closed-public-choices) | Replace duplicate choice definitions and handling with canonical enums; extend the existing field-aware encoding instead of adding a parallel conversion framework |
| [RF-003](#rf-003-create-the-expression-package-and-compose-semantic-analysis) | Consolidate repeated scope construction and expression analysis; remove the retired module and superseded traversal and translation code, rather than layering the new package over them |
| [RF-004](#rf-004-separate-record-indexing-from-shared-reference-validation) | Remove semantic reference checking from the index; consolidate Definitions UUID lookup through its typed get operation, share equivalent semantic checks and retain distinct scopes |
| [RF-005](#rf-005-separate-formulation-rules-from-scope-preparation) | Reduce Formulation validation to local rules and resolved orchestration; reuse located declarations and expression analysis, and remove duplicate collection and error-path reconstruction |
| [RF-006](#rf-006-consolidate-validation-compose-domain-checks-and-reuse-prepared-results) | Consolidate Model validation orchestration and recorded-unit checks, compose domain rules in their owners, and remove temporary envelopes, repeated preparation and discarded results |
| [RF-007](#rf-007-use-py-moneyed-directly-for-the-currency-catalogue) | Replace the bundled currency snapshot and JSON loader with py-moneyed's catalogue; remove duplicate provenance and resource handling |
| [RF-008](#rf-008-share-numerical-expression-evaluation-and-give-policy-predicates-a-clear-owner) | Replace duplicate numerical expression evaluation with one pure implementation; move policy truth evaluation to policies and retain execution acceptance rules |
| [RF-009](#rf-009-consolidate-scoped-target-resolution-and-recorded-scalar-access) | Remove trivial reference-key wrappers and repeated resolution; share scalar target access across validation, execution and observations |
| [RF-010](#rf-010-consolidate-graph-table-projection-around-view-or-hierarchy-input) | Replace separate flat/tree projection entry points with type-directed to_table; construct rows and the output Table once |
| [RF-011](#rf-011-simplify-graph-reducer-names) | Replace quantity-suffixed reducer names with sum, mean, min and max; keep one implementation per operation and remove the old exports |
| [RF-012](#rf-012-simplify-graph-value-selection-preparation-while-preserving-revision-safety) | Retain shared Value selection and revision checks; remove per-cell selector construction and repeated preparation for canonical graph inputs |
| [RF-013](#rf-013-compose-graph-reduction-and-aggregation-results) | Compose aggregation entries, derive policy-filtered results, remove sum-identity handling and simplify reduction orchestration |
| [RF-014](#rf-014-simplify-formulation-authoring-identity-and-operation-names) | Unify declaration construction and identity; remove private splits and wrappers; add the agreed passive account schedule through existing primitives |
| [RF-015](#rf-015-compose-account-conventions-calculation-and-formulation) | Compose account mechanics from three binary choices, one prepared recurrence and bounded symbolic equations; preserve six legacy combinations and fix rate preparation |
| [RF-016](#rf-016-compose-duration-operations-around-frequency-and-explicit-calendar-rules) | Restore canonical frequency behaviour and compose calendar offsets, boundaries, measurement and alignment; remove scattered frequency dispatch and implicit policies |
| [RF-017](#rf-017-clarify-period-boundary-fields-and-timing-names) | Make stored Period boundaries explicit and derive first/last/end from two dates; use one matching timing enum without duplicate fields or compatibility paths |
| [RF-018](#rf-018-simplify-policy-ownership-evaluation-and-decision-terminology) | Separate model-specific policy authoring from generic evaluation; derive result assignments, prepare evidence once, consolidate policy checks and distinguish Decision declarations from DecisionOutcome evidence |
| [RF-019](#rf-019-simplify-run-validation-around-prepared-documents-and-explicit-checks) | Unify Run preparation, retain report/tree/output checks and give traversal state one owner; remove repeated composition, reconstruction and stateful Publication orchestration |
| [RF-020](#rf-020-integrate-record-equivalence-and-simplify-revision-comparison) | Move equivalence into the record layer, reuse normalized comparison data and Model indexes, and remove repeated copies, serialization round trips and caller plumbing while keeping one shared revision rule |
| [RF-021](#rf-021-consolidate-scenario-mechanics-and-market-contracts-with-explicit-replay-provenance) | Separate stable market methods from implementation provenance; share method contracts and capture construction, remove sequential serialization and make realized revision identity depend on result content |
| [RF-022](#rf-022-consolidate-specification-composition-and-validation) | Consolidate Specification around one Composition, direct local rules and shared graph preparation; remove repeated composition, derived state and trivial target wrappers |
| [RF-023](#rf-023-consolidate-workflow-around-existing-evidence-graph-and-io-owners) | Consolidate workflow around existing evidence, table, graph, IO and adapter owners; remove repeated preparation, legacy result fields, duplicate derivation and publication mechanics |

## Intent register

| ID | Intent | Status | Coordination and prerequisites |
| --- | --- | --- | --- |
| [RF-001](#rf-001-move-observation-availability-rules-to-policies) | Move observation availability rules to policies and remove duplicate logic | Implemented; local acceptance passed | Isolate pure policy helpers from eager package imports |
| [RF-002](#rf-002-use-canonical-enums-for-closed-public-choices) | Use canonical enums for closed public choices | Implemented; local acceptance passed | Generate enums and update record encoding before migrating callers; coordinate policy imports with RF-001 |
| [RF-003](#rf-003-create-the-expression-package-and-compose-semantic-analysis) | Create the expression package and compose semantic analysis from explicit stages | Implemented; local acceptance passed | Define shared scope, inferred-domain uncertainty and analysis ownership; coordinate shared callers with RF-001 and canonical types with RF-002 |
| [RF-004](#rf-004-separate-record-indexing-from-shared-reference-validation) | Separate record indexing from shared reference validation | Implemented; local acceptance passed | Coordinate traversal and composed scopes with RF-003, metadata generation with RF-002, and structured diagnostics with existing validators |
| [RF-005](#rf-005-separate-formulation-rules-from-scope-preparation) | Separate Formulation rules from scope preparation and reuse located declarations | Implemented; local acceptance passed | Share scope and expression results with RF-003, traversal and reference checks with RF-004, and canonical choices with RF-002 |
| [RF-006](#rf-006-consolidate-validation-compose-domain-checks-and-reuse-prepared-results) | Consolidate validation, compose domain checks and reuse prepared results | Implemented; local acceptance passed | Integrate RF-002 decoding, RF-003 scope/analysis, RF-004 indexing/diagnostics, RF-005 Formulations, RF-009 scoped access and RF-001 policy checks |
| [RF-007](#rf-007-use-py-moneyed-directly-for-the-currency-catalogue) | Use py-moneyed directly for the currency catalogue | Implemented; local acceptance passed | Preserve the pinned code set, update dependency and implementation fingerprints, and retain RF-006's unit-validation behaviour |
| [RF-008](#rf-008-share-numerical-expression-evaluation-and-give-policy-predicates-a-clear-owner) | Share numerical expression evaluation and give policy predicates a clear owner | Implemented; local acceptance passed | Coordinate expression package ownership with RF-003, pure policy imports with RF-001, operator enums with RF-002, and validation boundaries with RF-006 |
| [RF-009](#rf-009-consolidate-scoped-target-resolution-and-recorded-scalar-access) | Consolidate scoped target resolution and recorded scalar access | Implemented; local acceptance passed | Integrate RF-003 scope, RF-004 lookup and errors, RF-006 revision-local preparation, RF-001 observations and RF-008 quantity-map keys |
| [RF-010](#rf-010-consolidate-graph-table-projection-around-view-or-hierarchy-input) | Consolidate graph table projection around View or Hierarchy input | Implemented; local acceptance passed | Reuse RF-006 unit-string validation and RF-004 Measure lookup; migrate tree projection callers |
| [RF-011](#rf-011-simplify-graph-reducer-names) | Simplify graph reducer names | Implemented; local acceptance passed | Migrate reducer exports, callers, documentation and typing/install fixtures; remove function-identity checks with RF-013 |
| [RF-012](#rf-012-simplify-graph-value-selection-preparation-while-preserving-revision-safety) | Simplify graph Value selection preparation while preserving revision safety | Implemented; local acceptance passed | Coordinate RF-010 projection preflight, RF-004 catalogue lookup and RF-006 revision-local reuse; retain custom-selector validation |
| [RF-013](#rf-013-compose-graph-reduction-and-aggregation-results) | Compose graph reduction and aggregation results | Implemented; local acceptance passed | Coordinate RF-011 reducer naming, RF-012 selection boundaries and RF-006 unit-string validation; preserve raw-contributor semantics |
| [RF-014](#rf-014-simplify-formulation-authoring-identity-and-operation-names) | Simplify formulation authoring, identity and operation names | Implemented; local acceptance passed | Coordinate RF-002 operators, RF-003/RF-005 semantics, RF-009 ownership, RF-001 imports and RF-015 schedule conventions |
| [RF-015](#rf-015-compose-account-conventions-calculation-and-formulation) | Compose account conventions, calculation and formulation | Implemented; local acceptance passed | RF-002 shared choices, RF-014 authoring, RF-008 fixed-predicate execution support and RF-016/RF-017 coordinates |
| [RF-016](#rf-016-compose-duration-operations-around-frequency-and-explicit-calendar-rules) | Compose duration operations around Frequency and explicit calendar rules | Implemented; local acceptance passed | Integrate RF-002 duration enums and import boundaries; migrate date/period consumers for the new month-end default and alignment contracts |
| [RF-017](#rf-017-clarify-period-boundary-fields-and-timing-names) | Clarify Period boundary fields and timing names | Implemented; local acceptance passed | Coordinate RF-002 timing enum, RF-016 calendar operations, generated Python/C# records, codecs and active consumers; retain half-open date semantics |
| [RF-018](#rf-018-simplify-policy-ownership-evaluation-and-decision-terminology) | Simplify policy ownership, evaluation and decision terminology | Implemented; local acceptance passed | Integrate RF-001 availability/imports, RF-006 preparation, RF-008 predicates, RF-009 scalar access, RF-014 authoring and RF-017 dates; migrate declaration/outcome schema and consumers together |
| [RF-019](#rf-019-simplify-run-validation-around-prepared-documents-and-explicit-checks) | Simplify Run validation around prepared documents and explicit report/output checks | Implemented; local acceptance passed | Reuse RF-003–RF-006 preparation and scopes, RF-009 target access and RF-018 policy outcome validation; migrate executor and conformance callers |
| [RF-020](#rf-020-integrate-record-equivalence-and-simplify-revision-comparison) | Integrate record equivalence and simplify revision comparison | Implemented; local acceptance passed | Coordinate RF-002 record encoding, RF-004 index access and RF-006 preparation; preserve RF-012/RF-013 selector contracts and RF-019 storage boundaries; use the shared `_revision.py` guard |
| [RF-021](#rf-021-consolidate-scenario-mechanics-and-market-contracts-with-explicit-replay-provenance) | Consolidate scenario mechanics and market contracts with explicit replay provenance | Implemented; local acceptance passed | Reconcile RF-002 method strings, RF-006 conformance reuse, RF-009 targets, RF-016/RF-017 periods, RF-018 availability and RF-020 revision identity; migrate stored method names explicitly |
| [RF-022](#rf-022-consolidate-specification-composition-and-validation) | Consolidate Specification composition and validation | Implemented; local acceptance passed | Apply RF-003–RF-006 scope, traversal and preparation; coordinate RF-009/RF-014 target callers, RF-018 policy ownership, RF-019 Run preparation and RF-020 revision rules |
| [RF-023](#rf-023-consolidate-workflow-around-existing-evidence-graph-and-io-owners) | Consolidate workflow around existing evidence, graph and IO owners | Implemented; local acceptance passed | Integrate RF-002 choices, RF-004/RF-006/RF-009 access and preparation, RF-011–RF-013 graph reduction and RF-020 comparison; preserve RF-019/RF-022 document and execution boundaries |

Use stable IDs as the list grows. Each new item must state the problem, intended
ownership, affected code, preserved behaviour, exclusions, dependencies, tests and
completion criteria. Include deletion targets and expected size changes under the
overall strategy. Record unresolved design choices explicitly. Do not expand an
item's scope through an incidental cleanup.

## Agreed integration decisions

The user approved the following decisions on 2026-10-07. They replace earlier
alternatives in this plan. The later instruction authorized committing and pushing
the plan, then implementing it. The final delivery instruction also authorizes
independent review, corrections, and committing and pushing the implementation.

| Decision | Agreed contract | Owning intents |
| --- | --- | --- |
| Account choices | Three named binary choices: balance OPENING/CLOSING, current interest EXCLUDED/INCLUDED, treatment SEPARATE/FINANCED. INCLUDED requires FINANCED. Preserve all six legacy combinations and the existing default. | RF-002, RF-014, RF-015 |
| Account composition | One account convention contract; prepared numerical recurrence; one passive symbolic schedule composer for the nonnegative, fixed-rate subset. Keep signed overdraft calculation and solver capability boundaries explicit. | RF-014, RF-015, RF-008 |
| Historical formats | Explicit migration into new Model/Specification revisions. Preserve originals and historical Runs. Current canonical APIs accept the current format only; old Runs require matching older tooling. | RF-017, RF-018, RF-021 |
| Required query types | Compatible, incompatible and unproven are distinct. Unproven types cannot satisfy required argument/predicate/objective checks. Passive reporting queries can remain unproven. | RF-003, RF-005, RF-006, RF-022 |
| Evidence correctness | Reject a controlled observation without an earlier outcome. Preserve historical Claims with type-sensitive, order-preserving comparison. These are correctness fixes, not merely moves. | RF-001, RF-018, RF-019, RF-020 |

### Shared ownership and preparation contracts

Use this table as the common contract for the overlapping intents. Detailed
sections add domain rules; they must not introduce parallel owners or contexts.
Finalize internal signatures from actual callers within these boundaries. Such
routine engineering decisions do not require another product decision.

| Owner | Result and responsibility | Boundary |
| --- | --- | --- |
| `_record_index.py` | Embedded-record traversal, typed UUID lookup, ownership and original paths within a root | No external resolution, mathematical eligibility, policy timing or opaque-content traversal |
| `model/formulation/traversal.py` | One ordered collection of located declarations, retaining contributor UUID, owner and original JSON pointer | Materialize iterable inputs once; retain owner-local naming scopes |
| `model/scope.py` | Explicit Model-only or composed mathematical scope, target ownership, declared units and scalar access | UUIDs are internal keys; wire/backend strings are converted at their boundaries; no IO or policy timing |
| `model/expression/validation.py` | ExpressionAnalysis with domains, uncertainty and dependencies for one scope | No graph execution, rule evaluation, persistent inferred-domain fields or cross-scope cache |
| `specification/composition.py` | One immutable Composition with effective requirements, original contributors and source locations | Derived view, no new document identity; preserve ordered objectives and case occurrences |
| Existing validation coordinators | Public ValidationReport plus internal prepared data containing the exact resolved Model, scope and analysis when available | Reuse only matching immutable content, revision, units, history and settings; retain structural-error gating |
| `policies` facade and `policies/validation.py` | Policy records and ActionKind exports; shared declaration/outcome rules; policy-owned timing and Boolean truth | Lightweight record imports; no `specification.policy` shim; stored evidence is checked independently of the producer |
| `_records.py` and `_revision.py` | Record equality/equivalence and one small Model/Specification revision guard | Strict equality, schema equivalence, permitted-output comparison and content hashes retain distinct contracts |
| `account.py` | Lightweight Balance, CurrentInterest and InterestTreatment enums and combination validation | Shared by account calculation and authoring; no Model loading, numerical runtime imports, ledger or generic strategy engine |
| `formulations.authoring` | One declaration construction and identity implementation | Mathematical declarations remain passive; existing unchanged operations retain their identity contracts |
| `table.py` and existing graph owners | Table/Row invariants, selection, projection and reduction | Reuse canonical Rows only when their column order matches; retain callback/revision checks |

Do not add a second FormulationAnalysis wrapper when the coordinator can retain
the located declarations, Scope and ExpressionAnalysis directly. Raw mappings
are decoded once at their boundary; already validated immutable records should
not be exported and reconstructed solely to enter the next stage.

Extend `Composition.sources` attribution to retain contributor UUID and original
pointer, not only the contributor UUID. Index traversal locations must survive
collection and composition. Distinguish source locations from paths in derived
requirements. An error in an included document must identify that original
document and pointer, even when another contributor has the same local path.

Execution planning must retain Models it has resolved and checked. Pass those
exact snapshots through composition validation and execution preparation. Do not
reload a Model merely because the public validator returns only a report. Pass
the supplied UnitSystem through policy preparation/evaluation as well; do not
silently replace it with `default_units`. Standalone public calls establish fresh
contexts. Store snapshots, independent acceptance and stored-evidence checks
remain deliberate validation boundaries.

On failure, retain only data whose prerequisites succeeded. A valid composition
pin remains usable for batch accounting when later mathematical checks fail;
a missing or invalid Scope is not a successful prepared result. Keep existing
diagnostic types and failure/not-assessed contracts. Do not add `trusted=True`,
persistent validation flags, universal contexts or global caches.

### Explicit migration contract

Use one coordinated wire change for RF-017, RF-018 and RF-021. The following
versions are the targets from the reviewed checkout. If the implementation
checkout has advanced, select the next unused versions and update this table
before editing schemas; do not reuse a version for two layouts.

| Schema | Reviewed version | Target version |
| --- | --- | --- |
| Model | 0.6.0 | 0.7.0 |
| Specification | 0.6.0 | 0.7.0 |
| Run | 0.3.0 | 0.4.0 |
| Duration | 0.1.0 | 0.2.0 |
| Policy | 0.1.0 | 0.2.0 |
| Scenario | 0.2.0 | 0.3.0 |

| Explicit migration input | Output | Revision and dependency rule |
| --- | --- | --- |
| Model 0.3.0, 0.4.0, 0.5.0 or 0.6.0 | Model 0.7.0 | Apply source-layout conversions in the order below; mint a new revision with the original as predecessor; return its old-to-new revision mapping |
| Specification 0.4.0, 0.5.0 or 0.6.0 | Specification 0.7.0 | Convert its own declarations; require explicit mappings for Model pins, includes and cases; mint a new revision with the original as predecessor |
| Historical Run and its pinned documents | Preserved original documents | No Run conversion or pin rewrite; inspect with matching older tooling |
| Unknown version or ambiguous mixture of layouts | No converted document | Reject before current-facade construction; do not guess a source layout |

Canonical constructors, codecs and stores accept only the new root versions.
There are no old-name aliases, automatic store upgrades, dual-layout canonical
records or new multi-version reader. Historical Runs remain unchanged with their
original pins; this refactor does not convert them into new execution evidence.
Inspect an old Run and its old-format dependencies with matching older tooling.
Current-format results remain readable when their calculation implementation is
unavailable for replay. Format support and replay capability are separate.

Extend the existing explicit migration entry points to support Model
0.3.0/0.4.0/0.5.0/0.6.0 and Specification 0.4.0/0.5.0/0.6.0. Preserve previously
supported scenario conversions. Reject unknown versions and ambiguous mixed
layouts. Do not construct a new facade from partly converted content.

Migration order:

1. Identify and validate the supported source version and source layout.
2. Apply the existing Movement/reference upgrades and coordinated Period,
   policy and scenario-name conversions using that source layout. The current
   `migration/drafts.py` walker uses current slots; replace that assumption with
   explicit source-version traversal/conversion for renamed fields and types.
   Never descend into opaque Claim content as though it were a schema record.
3. Preserve declaration and Movement identities, captured draws, mathematical
   values, order, field presence and availability dates. New schema fields must
   not fabricate unavailable historical calculation fingerprints.
4. Mint a new root revision, name the original as predecessor, and apply an
   explicit old-to-new revision map to Model pins, includes and cases. Reject
   missing/conflicting mappings; never infer the latest revision or rewrite Runs.
5. Construct and validate the complete new facade. Validate migrated dependency
   graphs with the explicit resolver before optional append-only publication.
   Migration itself does not write, resample, solve or recompute historical paths.

Generate Python and C# bundles from the final coordinated schema set. Update
active fixtures and their pins together. Keep representative immutable source
fixtures for migration tests and leave archived evidence unchanged.

### Deliberate behavior changes and acceptance gates

These changes must be visible in implementation evidence. Renaming a module does
not establish their correctness. Each gate needs an independent expected result.

| Gate | Change or risk | Required evidence |
| --- | --- | --- |
| G1 | Stored policy evidence accepts a recorded control without a prior outcome | Solver-free producer/checker cases reject it; valid earlier outcomes and declared delays still pass |
| G2 | Historical Claim content can change from `0` to `False` under dictionary equality | Public Run validation rejects the change; cover `0.0`, nested content, list order and field presence |
| G3 | Query inference currently labels all Value projections as measurements | Caller acceptance matrix and canonical `floor_area` example; no graph execution to infer a type |
| G4 | Account rate pairing and empty-input validation are incorrect | Same-day `z`/`a` coordinates produce independently expected per-period charges; invalid empty-input rates fail |
| G5 | Account API and passive schedule are deliberately expanded | Six legacy mappings, default parity, signed numerical recurrence, valid fixed-rate schedule and explicit unsupported cases |
| G6 | Calendar default and Period/policy wire names change | Date behavior checked separately from field migration; source versions, pins and both generated languages verified |
| G7 | Local Specification settings omit the strict tolerance bound | Local and complete validation both enforce `0 < relative_tolerance < 1` |
| G8 | Scenario output identity omits result content and calculation identity | Changed results or relevant implementation change the revision; declaration IDs and random streams remain stable |
| G9 | New module ownership can escape implementation fingerprints | Inclusion/exclusion inventory and sensitivity tests for moved evidence, indexing, graph, arithmetic and currency data |
| G10 | Shared preparation can lose source paths, units or failure evidence | Original contributor pointers, supplied units, failed/not-assessed Runs, counted resolver/preparation calls and independent IO checks |

The exact shared contracts in the preceding table and the domain gates above
take precedence over historical alternatives and old baseline notes. Keep the
intent sections consistent with them; do not retain contradictory alternatives.

### Review coverage and readiness

Every finding in the combined review is incorporated below. Coverage means that
the plan specifies the work and its acceptance check. It does not mean that the
code is fixed or that implementation checks have passed.

| Review finding or opportunity | Authoritative contract and owning intents | Acceptance requirement |
| --- | --- | --- |
| Recorded controls can bypass earlier-decision requirements | G1; RF-001, RF-018, RF-019 | Independent forged-outcome regression through public validation; no solver required |
| Historical Claims can change scalar types under dictionary equality | G2; RF-019, RF-020 | Type-sensitive comparison preserves nested content, order and field presence |
| Period, policy and scenario migrations can conflict | [Explicit migration contract](#explicit-migration-contract); RF-017, RF-018, RF-021 | Supported source fixtures convert together; new revisions and external pin mappings validate; historical Runs stay unchanged |
| Shared preparation can duplicate contexts or lose paths, Models and units | [Shared ownership and preparation contracts](#shared-ownership-and-preparation-contracts); W2; RF-003–RF-006, RF-009, RF-022 | Original document/pointer diagnostics, exact resolved snapshots, caller UnitSystem, failure gating and operation-local lifetime remain intact |
| Query uncertainty can invalidate or falsely accept typed calls | [Query acceptance](#required-query-acceptance-matrix); G3; RF-003 | Measurement, property, Flow, mixed and unknown cases cover each caller; the canonical floor_area example passes without graph execution |
| Policy exports conflict; returned choice fields lack dispositions | [Public-result inventory](#additional-public-result-inventory-from-the-integrated-review); RF-002, RF-018 | ActionKind comes from policies; closed choices have operation-owned enums; open category/source labels remain strings |
| Account basis and scenario provenance decisions were unresolved | RF-015 and [realized revision identity](#realized-revision-identity-and-replay); G5, G8; RF-021 | Six legacy account combinations, invalid combinations, provenance fields and exact fingerprint/revision fixtures pass |
| Moved or reused computation can escape fingerprints | [Fingerprint inclusion rules](#fingerprint-inclusion-rules); G9; RF-007, RF-008, RF-021, RF-023 | Relevant source/resource changes alter each affected identity; presentation-only changes obey its exclusions |
| Table reconstructs normalized Rows | RF-010, RF-023 | Canonical Row reuse preserves column order, validation and shallow immutability; raw mappings still normalize once |
| Numerical and symbolic Flow alignment share only part of their work | RF-014, RF-015, RF-017 | Duplicate-aware coordinate indexing can be shared; destination order, transaction order, numerical sorting and join policy stay with their operations |
| Stream.merge compares copied plain dictionaries | RF-020 | Use type-sensitive exact pinned-document comparison without repeated exports; distinct revisions still fail |
| Dependencies and deletion counts overlap | [Work packages and order](#work-packages-and-order) | Internal prerequisites are explicit; one owner and one deletion count per shared change; intent sections remain in register order |
| Focused test passes do not establish implementation acceptance | [Review baseline](#review-baseline-not-implementation-acceptance); W0, W7 | Re-establish the baseline and run all applicable gates; report missing full-suite, installed-wheel, C# and host checks |

The account choices, explicit migration approach and scenario provenance contract
are settled in this plan. Before dependent source edits, W1 must record final
signatures, manifest file lists, the check-export version and any version changes
needed because the checkout has advanced. These are bounded implementation checks,
not permission to reopen the agreed behavior or add compatibility paths.

## Combined implementation record

The plan was committed and pushed first as `6f7764e` on `acausal-modelling`.
All 23 intents are implemented under the agreed W1–W6 ownership and contracts.
W7 local acceptance and the independent implementation review are recorded below.
The user authorized review, correction, commit and push as the delivery steps.
The unrelated edits in `README.md`, `docs/README.md`, `src/README.md` and
`CONTRIBUTING.md` remain byte-for-byte unchanged and outside this commit.

Baseline: 1,105 Python tests passed and 24 optional layout tests skipped before
source changes. Final acceptance uses MiniZinc 2.10.1, CP-SAT 9.15 and Z3 5.1.0.0.
Runtime Python is 3.10.19; schema tooling uses Python 3.12.12. Pyomo 6.10.1 and
HiGHS 1.15.1 supply the real execution checks. Independent regressions first
reproduced G1/G2 and now reject both defects. The actual query-consumer matrix
covers all 20 combinations of measurement, property, Flow, mixed and unknown
results with Function arguments, predicates, objectives and passive reporting.

### Independent implementation review

Fresh reviewers checked core preparation, graph/workflow and temporal/account
contracts against the plan and current implementation. Additional execution probes
checked expected failure boundaries. Eleven findings required corrections; the
publication review also extended its checks to interruptions and competing writers.

| Finding | Correction and regression |
| --- | --- |
| Including a Specification predecessor was rejected | Separate include edges from revision lineage; retain declaration, cycle and invalid predecessor checks |
| Batch IDs could collide with leaf declarations | Check the batch identity against each complete leaf scope while keeping sibling scopes separate |
| Wrong reference kinds escaped structured validation | Emit located `reference.kind` diagnostics; retain direct lookup exceptions |
| A one-shot iterable bypassed local binding-name checks | Materialize the declarations at the helper boundary before repeated checks |
| Binding diagnostics lost source locations | Preserve the original contributor document and binding field path, including offset roots and unit failures |
| Derivation discarded conflicting settings Claims | Deduplicate only the same Claim object; reject distinct objects that share a UUID |
| Publication could report failure after changing the pointer | Distinguish visible publication from confirmed durability; retain the completed output after sync, status-record or observer failure; propagate cancellation without rewriting completion; never roll back or adopt a later writer's pointer |
| Workflow identity omitted a used validation dependency | Include jsonschema in implementation identity, exported dependency metadata and installed-wheel checks |
| Migration could reuse a prior UUID with different letter case | Validate source Metadata and compare UUID identities before minting a revision |
| Fixed strict arithmetic failures escaped execution | Translate unsupported computation and numerical errors to their separate execution failures; preserve UnitError |
| Incomplete selected policy outcomes escaped evaluation | Translate the final outcome contract failure to PolicyCapabilityError; persist the failed Run without invoking a solver |

Regressions first reproduced the defects. Separate reviewers rechecked the fixes,
including valid controls and rejection boundaries. Review logs and probes are at
`/private/tmp/rk-refactor-review-20261007-hp0frw5q`. They supplement the earlier
acceptance evidence; temporary probes are not package inputs.

### Acceptance evidence

| Check | Result |
| --- | --- |
| Full Python suite with required layout solvers | **1,428 passed, zero skips**, using `--require-layout-solvers --ignore=tests/legacy/test_api.py`; only the three live predecessor service tests were excluded |
| Independent implementation review | Eleven findings corrected with regressions and separate review closure; publication checks also cover interruption, status-write failure and competing writers |
| Type checking and intentionally invalid calls | All 221 active package Python files plus seven valid typing fixtures pass; the seven invalid fixtures produce exactly 9/6/5/4/5/3/6 expected errors |
| Installed wheel | Minimal imports, records, JSON/YAML, both stores, graph/tables/viewer assets, PyXIRR, real process-isolated forward/inverse solves, XLSX workflows, Polars and CSV pass with their optional-import checks |
| Generated artifacts | Python generation and C# generation checks pass; generated files match the schemas and pinned generator environment |
| Conformance | All seven suites pass: structural, native, Expression, Formulation, Model, Specification and Run; all 16 stock native fixture round trips and 759 raw/simplified schema-equivalence cases pass |
| C# | Model/Tests and Grasshopper Components build; Components has zero warnings/errors against installed Rhino 8 assemblies; Python–C#–Python content, presence, identity and ordered-mathematics checks pass on .NET 8 |
| Viewer | TypeScript check passes; 35 pure JavaScript tests pass; five packaged assets match a fresh in-memory build. The existing synthetic saved-layout interaction test was not run because its fixture URL was not configured |
| Walkthroughs | All seven notebooks execute in fresh kernels, 91 code cells; fresh site builds from those outputs; all 16 browser pages pass with zero JavaScript errors, failed requests or broken images |
| Documentation and preservation | Current API guides and examples updated; local links and `git diff --check` pass; all 171 existing files under `walkthrough/_build` remain unchanged |
| External acceptance | Rhino host loading, Windows connector acceptance, Linux execution and remote CI were not run; local build and browser results do not establish those passes |

The offline book build disables unused Thebe through supported Sphinx extension
configuration. This removes duplicate inline declarations without editing built
HTML. Its declared dependency versions and build instructions remain in the
walkthrough lockfile and README. No site was published.

Reproduction commands are in [Verification](VERIFICATION.md), the
[schema guide](../schema/README.md), [C# guide](../grasshopper/README.md) and
[walkthrough guide](../walkthrough/README.md). The local baseline, logs, source
hashes, notebook outputs and size accounting are retained at
`/private/tmp/rk-refactor-20261007-tuzea054`; these are evidence, not package inputs.

### Size and deletion accounting

The default net-reduction target was **not met**. This is the explicit combined
exception required by the strategy above. The immutable pre-edit snapshot and
final working tree were counted with the same physical-line and AST method,
including new files, shared helpers and callers. Legacy runtime is unchanged.
The runtime count includes handwritten `_schema/validation.py` and `__init__.py`;
generated records and native bindings are counted separately.

| Category | Files before → after | Lines before → after | Added / removed | Net lines |
| --- | --- | --- | --- | --- |
| Handwritten active Python runtime | 224 → 219 | 27,090 → 29,572 | +9,867 / −7,385 | **+2,482** |
| Python generators | 2 → 2 | 447 → 490 | +47 / −4 | +43 |
| Schema verification/typing tools | 19 → 19 | 1,168 → 1,172 | +132 / −128 | +4 |
| Schema conformance tools | 9 → 9 | 3,278 → 3,321 | +102 / −59 | +43 |
| Other tools, including the maintained book builder | 5 → 5 | 676 → 697 | +36 / −15 | +21 |
| Python documentation examples | 2 → 2 | 267 → 267 | +5 / −5 | 0 |
| Handwritten C# | 24 → 24 | 1,834 → 1,834 | +2 / −2 | 0 |
| Generated Python | 2 → 3 | 8,217 → 8,544 | +556 / −229 | +327 |
| Generated C# bundle | 5 → 5 | 10,597 → 10,718 | +403 / −282 | +121 |
| Python tests | 70 → 83 | 17,318 → 22,044 | +5,388 / −662 | +4,726 |
| Repository Markdown | 90 → 90 | 21,607 → 21,974 | +903 / −536 | +367 |

There are 40 retired runtime paths and 35 new runtime paths: five fewer modules.
Runtime classes increase from 167 to 210; 31 of those 43 additions are the closed
choice enums replacing repeated string conventions. Runtime functions/methods
increase from 936 to 1,018. Each moved or shared definition is counted once.
Applying Black 25.9.0 independently to both snapshots gives 27,098 → 29,572 runtime
lines (+2,474), eight fewer net lines than the physical comparison. This removes
formatter differences; it does not claim that every formatting edit is separately
identifiable inside a changed function. Final explicit multiline signatures are
retained. No timing improvement or net runtime reduction is claimed.

The required additions are the six account combinations and passive schedule,
calendar rules, plain typed enums, explicit migration and replay provenance,
query-domain uncertainty, source-located diagnostics, prepared failure results,
truthful publication status through IO failure and cancellation, and independent
evidence checks. Their supporting records retain distinct domain
contracts. Removing these checks or merging policy truth with numerical acceptance
would make the implementation smaller by discarding agreed behavior. Further
wrapper removal would not eliminate those responsibilities.

The simplification is visible in one record index, one mathematical Scope, one
ExpressionAnalysis, one Composition, direct domain validation owners, UUID target
access and shared graph/Evidence preparation. Retired policy, execution, Run,
composition, ingestion and authoring forwarding paths are removed. No compatibility
aliases, universal validation context or persistent trust cache replace them.
The individual records below name final owners and deletion targets; shared
package counts are not added again to these combined totals.

## Combined implementation process

Implementation starts only when the user asks to execute this plan. That request
authorizes the agreed implementation and its required checks; do not ask again
for routine module placement or signatures already bounded by this plan. Changes
to agreed domain behavior or new features still require a new decision. Commit
and push are separate actions and require the user's instruction.

### Work packages and order

The intent register lists coordination links, not a topological order of whole
intents. Use these work packages. An intent can span packages; each shared change
has one implementation owner and one deletion count.

| Package | Prerequisites | Work and exit condition |
| --- | --- | --- |
| W0: establish the baseline | User instruction to execute | Inspect dirty work, snapshot relevant source/size baselines, confirm tool environments and add independent regressions for G1–G10 where applicable |
| W1: contracts and generation | W0 | Freeze public exports, internal result shapes, source-location and key representations, migration versions, scenario provenance/hash encoding and check-export version; generate coordinated enums and wire records |
| W2: records and shared preparation | W1 | Implement RF-020 comparison/guard and RF-004 index; then RF-003 scope/analysis, RF-005 located rules, RF-009 access, RF-006 coordinator results and RF-022 Composition; migrate callers without parallel contexts |
| W3: temporal, authoring and account work | W1, W2 | RF-016/RF-017 calendar/Period consumers; RF-014 authoring and RF-015 numerical/symbolic account composition, including its bounded execution support; independent equations and identities pass |
| W4: policies, execution and Run evidence | W2, W3 | RF-001/RF-008/RF-018 policy and arithmetic owners; RF-019 Run checks; G1/G2 and unit-context regressions pass; original numerical acceptance remains independent |
| W5: graph and scenarios | W2, W3; W4 interfaces for policy availability | RF-010–RF-013 projection/selection/reduction plus Table normalization; RF-021 contracts, capture, content identity and replay; complete coordinated migration fixtures and pin checks |
| W6: workflow integration | W2, W4, W5 | RF-023 Evidence preparation, derivation, graph reuse, reporting and publication; RF-007 catalogue/fingerprint changes; remove superseded paths and verify all fingerprint groups |
| W7: combined acceptance | W1–W6 | Full applicable verification, installed artifacts, maintained guides/examples, deletion/size accounting and final residual-risk report |

RF-007 can be implemented independently after W0, but its dependency and
fingerprint results must be present before W6/W7 acceptance. Within W3, finish
the authoring primitives and calendar/coordinate contracts before account and
scenario consumers. W3 may establish the RF-008 pure arithmetic interface needed
for fixed account-rate predicates; W4 consumes that same implementation. There is
no requirement to finish one entire RF section before touching another.

### Instructions for the execution step

1. Read this coordination section and the affected intent sections. Inspect the
   actual working tree, including untracked files. Preserve unrelated work and
   do not reset, clean, stage or commit it. An isolated checkout must include
   the agreed working-tree baseline rather than silently starting from an older
   committed version.
2. Record Python/interpreter, dependency and solver versions. Use `src/` for
   Python tests and the repository root for schema/build tools. Use the existing
   pinned runtime and schema environments; dependency installation is setup,
   not proof that a required check passed.
3. Freeze representative identities, exports, error paths and calculation
   expectations before moving code. Add small failing regressions for confirmed
   defects. Keep numerical expectations independent of the shared implementation.
4. Apply W1–W6 with focused checks after each affected boundary. Migrate active
   callers, exports, typing fixtures and guides together. Delete old paths after
   their final callers migrate; do not keep forwarding aliases to ease the move.
5. Maintain a per-package record of prerequisites, actual deletions, justified
   additions and verification. Count a shared deletion once. Separate runtime,
   generators, generated output, tests and docs; use one formatting/counting
   baseline. Account for necessary growth from correctness and the new schedule.
6. Finish W7 using [Verification](VERIFICATION.md), the schema guide and each
   intent's focused checks. Run generation freshness, typing, conformance,
   runtime/regression, installed-wheel/import isolation and affected C# checks.
   Include strict layout checks and maintained walkthrough execution where the
   changed enums, workflow or generated records affect them. Missing engines,
   skipped mandatory checks and unavailable host acceptance remain limitations.
7. Do not edit source while fingerprint-sensitive tests run. If later edits
   affect their inputs, rerun the affected checks. A local Python pass does not
   establish installed-wheel, C#, native host, Linux or remote CI acceptance.
8. Update each implementation record with actual results and limitations. Finish
   with changed behavior, migration instructions, public API moves, retained
   boundaries and net handwritten size. Do not mark the combined plan complete
   while an applicable gate remains unresolved.

### Review baseline, not implementation acceptance

On 2026-10-07, 178 focused tests passed across records, Model, Specification, Run,
composition, graph and reference identity. After installing the declared
`pyomo==6.10.1` and `highspy==1.15.1` packages in the source virtual environment,
all 16 scenario/policy and market tests passed. The earlier policy integration
failure was missing runtime support. The independent G1/G2 probes still exposed
validation gaps not covered by those tests. No full-suite, installed-wheel or C#
acceptance was established by this review. Re-establish the baseline at execution.

## RF-001 Move observation availability rules to policies

### Problem and ownership

`model/_availability.py` contains
`available_on()`. It calculates when a policy may observe a referenced quantity
from Movement coordinates, scenario provenance and a declared availability date.
It is active code, with one direct caller:
`specification/_policy_validation.py`,
inside `validate_decisions()`.

[`policies/observation.py`](../src/rangekeeper/policies/observation.py) independently
implements substantially the same date rule when `observe()` builds observations.
The implementations currently use different representations: the validation
helper reads encoded mappings and returns an ISO date string; `observe()` reads
generated records and uses native `date` objects.

The Model owns the stored coordinates and provenance. Policies own the rule that
uses those facts to limit observations at a decision date. Put that rule in
`policies`, and use one implementation for observation construction and recorded
decision validation. This preserves the check against using future information.

### Intended structure

```text
src/rangekeeper/
  model/
    _availability.py            remove after migrating its caller
    scope.py                    RF-003/RF-009: scoped target access
    _references.py              RF-009: remove after migrating callers
    _scenario.py                retain captured scenario conformance checks
  policies/
    __init__.py                 expose existing API without eager runtime imports
    _availability.py            pure internal date rule
      available_on(...)         return date or None
    observation.py
      observe(...)              resolve records and call the shared date rule
    evaluation.py               retain policy orchestration and prior decisions
    validation.py               RF-018/RF-022: shared outcome and declaration checks
      validate_decisions(...)   check evidence and call the shared date rule
  specification/
    _policy_validation.py       remove after moving its checks to policies
```

Use a small typed helper over native dates. A proposed interface is:

```python
def available_on(
    *,
    movement_date: date | None = None,
    period_end: date | None = None,
    scenario_dates: Iterable[date] = (),
    declared: date | None = None,
) -> date | None:
    ...
```

Keep reference resolution and quantity extraction in the callers. Normalize
encoded dates at the validation boundary and convert the result to ISO format
only where recorded evidence requires it. Avoid serializing or validating a whole
Model for each observation. Preserve the existing aggregation of provenance dates
where it avoids repeated scans.

The helper must have no IO, mutation, solver access, random generation or policy
execution. It should depend only on the standard library. It must not import
Model, Specification, Run or the policy evaluator.

### Import dependencies

Importing a submodule first executes its package initializer.
[`policies/__init__.py`](../src/rangekeeper/policies/__init__.py) currently imports
observation, evaluation and the resale builder eagerly. Evaluation imports
Specification validation; the resale builder imports formulations. A file move
alone would therefore make decision validation load policy runtime modules and
introduce a dependency back to its own validation module. This is an import-cycle
risk, not an observed import failure.

Before redirecting the validator, make the policy package initializer lightweight.
Use lazy resolution for the existing public exports, consistent with the root
package's approach, and preserve `__all__` and public import behaviour except for
RF-018's explicit removals and declaration/outcome renames. Importing
`policies._availability` must not load policy evaluation, resale builders,
formulations, execution or optional numerical packages as a side effect.

Specification and Run validation may call the pure policy rule. They must not
execute a policy to validate stored decision evidence. Keep the validation entry
points in their current locations for this item. RF-018 separately consolidates
shared policy declaration and outcome checks under policy ownership while keeping
Specification and Run validation as their respective public coordinators.

### Behaviour to preserve

| Case | Required result |
| --- | --- |
| Movement has a date | Use that date as its coordinate boundary |
| Movement has a period but no date | Use the final included day, `period.end - one day`; the period end is exclusive |
| Several scenario availability entries match the target | Use the latest date across all matching entries |
| Binding declares an availability date | It can delay availability but cannot advance it before the coordinate or provenance boundary |
| No coordinate, provenance or declared date establishes availability | Return `None`; observation access fails |
| Decision date equals the resulting availability date | Observation is permitted, subject to the existing quantity and reference checks |
| Decision date precedes availability | Reject the observation |
| Scalar has no Movement coordinates | Require a date from provenance or an explicit declaration |
| Quantity is absent or unresolved | Keep the existing error; do not substitute zero |
| Recorded observation claims an earlier or later availability date | Reject it unless it equals the date derived from the input evidence |

Preserve the existing precedence of a Movement date over its period boundary.
Do not add a new rule for records that contain both fields as part of this move.

Earlier policy assignments are a separate source of observations.
[`policies/evaluation.py`](../src/rangekeeper/policies/evaluation.py) and
`validate_decisions()` use the earlier decision date, delayed if necessary by the
binding's declared date. Preserve that path and its requirement for an earlier
decision. Do not impose the controlled Movement's later coordinate on an already
known decision, or substitute a recorded control value for decision history.

Correct the `observe()` docstring during implementation: its current wording says
period data needs explicit availability, while its implementation derives the
last included day from the period. Document the preserved implementation.

### Scope and exclusions

Change the files in the intended structure, the relevant tests, and current
documentation. Update the ownership tree in
[Scenarios and policies](SCENARIOS_AND_POLICIES.md), and clarify the pure policy
dependency in [Library architecture](LIBRARY_ARCHITECTURE.md).

This item does not change persistent schemas, record fields, public policy names,
scenario generation, calendar conventions, numerical execution or stored document
versions. Keep scenario provenance validation in `model/_scenario.py`; it checks
captured Model evidence. RF-008 separately owns the `_predicate.py` refactor;
coordinate its import changes without expanding this item's availability rules.
Do not move other Model helpers or all policy validation as an incidental part
of this item. Remove the old private module without a forwarding alias.

The integrated review identified G1: stored-outcome validation can accept a
recorded controlled quantity where runtime evaluation requires an earlier
outcome. Apply RF-018's explicit rejection while consolidating availability.
Availability and prior-control eligibility remain distinct checks; a declared
date does not turn a recorded control into a prior decision.

### Verification

Add focused tests for the behaviour table, including period boundaries, multiple
provenance dates, absent dates and explicit delays. Exercise both `observe()` and
`validate_decisions()` against the same evidence so the tests verify agreement
between the callers. Cover forward-derived scenario values that remain unavailable
until the next period ends, and observations supplied by earlier decisions.

Use a valid decision trace to test forged availability directly without requiring
a numerical solve. Retain the existing Run integration test as a separate check.
Test that forged dates fail even when the forged date is before the decision date.
This proves that validation checks input evidence as well as chronology.

In fresh processes, check imports in both orders: validation before policy runtime,
and policy runtime before validation. Confirm that loading the pure helper does
not load the runtime modules listed above. Check existing public policy exports,
then run the minimal installed-package checks in
[`tools/schema/verify_install.py`](../tools/schema/verify_install.py).

Run the scenario and policy suite from `src/`:

```sh
.venv/bin/python -m pytest tests/test_scenarios_policies.py -q
```

Also run affected Specification, Run and import-boundary tests, followed by the
combined regression checks selected for the full intent list. Check that active
source and current guides contain no references to `model._availability` or the
retired path. Preserve historical records of the old structure.

Baseline observed on 2026-10-06, before this refactor: the scenario and policy
suite returned 11 passes and one setup failure before forged-evidence checks.
The 2026-10-07 review established missing Pyomo as that setup cause. After the
declared Pyomo/HiGHS installation, the combined scenario/policy and market suite
passed all 16 tests. Re-establish that baseline and the separate G1 regression
before claiming implementation acceptance; do not weaken the integration test.

### Completion criteria

- One pure implementation owns the date rule in `policies/_availability.py`.
- Observation construction and decision validation both use it.
- The old private module and its active imports are removed.
- Prior-decision handling and all listed availability behaviour are preserved.
- Pure-helper imports remain isolated from policy runtime and optional packages.
- Public policy imports and installed-package checks pass.
- Focused tests and the agreed regression checks pass; the baseline integration
  failure is resolved or explicitly dispositioned in the combined execution scope.
- Current guides describe the new ownership and import boundary.

### Implementation record

Implemented in the coordinated working-tree pass. `policies/_availability.py` owns native-date availability and its operation-local evidence index. Observation construction and independent outcome validation use the same rule; `model/_availability.py` is removed.

Controlled targets require an earlier outcome in both runtime and stored evidence, including Runs without outputs. G1 regressions are independent of the evaluator and solver. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-002 Use canonical enums for closed public choices

### Intent and scope

Use named enum members for fixed choices in the public Python API. Keep strings
for open text, extensible identifiers and serialized representations. This makes
valid choices discoverable and prevents unrelated concepts with the same text
from being treated as the same argument.

This is a deliberate Python API break. Methods, typed record constructors and
`replace()` accept the appropriate enum type, not an enum-or-string union.
Generated properties return enum members. JSON and YAML continue to contain the
existing string values. Enum conversion itself must preserve numerical behaviour,
permitted choices, stored document meaning and record field presence. Apply the
explicit operation-contract changes in RF-015 and RF-016 separately from that
conversion and verify them as deliberate behaviour changes. RF-017 separately
renames Period wire fields and timing option values while preserving their dates;
its explicit migration supersedes the existing-value rule for those names.

The scope includes generated records, handwritten public operations, public
runtime result fields, active callers, examples, typing fixtures and adapters.
It also includes the explicit conversion needed at existing external boundaries.
Do not change legacy implementations or historical artifacts to make them appear
to use the new API. Update active migration code that constructs current records.

### Design rules

1. Use standard-library `Enum` with explicit string values and uppercase member
   names. Use `@unique`; do not use `auto()` for serialized values. Retain Python
   3.10 support. Do not introduce `StrEnum`, `IntEnum` or string mixins for these
   choices. [Python enum reference](https://docs.python.org/3/library/enum.html).
2. Give each concept one canonical type. Public domain modules may re-export that
   type, but must not define copies. Equal text does not by itself mean two
   concepts should share a type.
3. LinkML remains the source of truth for persisted record choices. Generate
   Python enums from its permissible values. Runtime-only choices stay with
   their owning operation or domain and do not require new schema fields.
4. Validate enum types at public entry points, including dataclass construction.
   Type annotations alone do not enforce runtime arguments. Reject a raw string
   or an unrelated enum with `TypeError`; reject invalid combinations of valid
   options with the existing domain error or `ValueError`.
5. Parse text only at explicit input boundaries. `Choice(text)` may perform an
   explicit conversion; invalid text raises `ValueError`, wrapped in the existing
   codec error where required. Do not silently convert strings in every method.
6. Use enum members for typed dispatch and `.value` for an identified external
   string boundary. Keep raw mapping validation in its existing wire form. Do not
   mechanically replace every string comparison in the repository.
7. Small private implementation choices may retain `Literal` where a named
   runtime concept adds no value. Record those exclusions in the inventory.
   `Literal[SomeEnum.MEMBER]` remains useful for a restricted typed branch.
   [Python literal specification](https://typing.python.org/en/latest/spec/literal.html).

Proposed authoring style:

```python
from rangekeeper.duration import PeriodTiming
from rangekeeper.model import ValueKind

day = period.resolve(timing=PeriodTiming.LAST)
is_flow = value.kind is ValueKind.FLOW

# Text conversion is explicit at an input boundary.
timing = PeriodTiming(settings["timing"])
```

### Source inventory

The following inventory was inspected on 2026-10-06. It is the starting scope,
not a claim that all fixed strings have been found. Before implementation, scan
public signatures, dataclass fields, returned status fields, dispatch comparisons,
configuration schemas and callers. A search for `Literal` alone is insufficient.
Record each additional candidate as convert, retain with reason, or separate
intent before changing it.

#### Generated choices

[`tools/schema/generate.py`](../tools/schema/generate.py) currently emits 26
`Literal` aliases in
[`_schema/records.py`](../src/rangekeeper/_schema/records.py). Convert all 26 from
their existing LinkML definitions; preserve every permissible string value.

| Owning subject and intended public facade | Existing generated types |
| --- | --- |
| Model values and provenance through `model` | `ValueKind`, `ClaimKind`, `ReconciliationStatus` |
| Expressions and queries through `model.expression` | `ExpressionKind`, `Operator`, `SelectionKind`, `DomainKind`, `CollectionKind`, `ParameterKind`, `EmptyHandling`, `TraversalKind`, `Depth`, `Direction`, `ProjectionKind`, `Cardinality`, `MissingHandling`, `DuplicateHandling` |
| Distributions through `model.distribution` | `DistributionFamily` |
| Content through `model.content` | `ContentKind` |
| Policy declarations through lightweight `policies` facade | `ActionKind` |
| Objectives through `specification` | `ObjectiveKind` |
| Run evidence through `run` | `CompletionStatus`, `SolutionStatus`, `ImplementationKind`, `Severity`, `StepKind` |

Other public modules that accept these types can re-export the same class where
this improves use. No caller should need to import `_schema` to supply a public
argument. Re-exports must preserve class identity and static type information.

#### Handwritten choices

Names in this table are the proposed public names. Preserve existing value sets
and defaults except for the explicit account redesign in RF-015, duration
redesign in RF-016 and Period naming changes in RF-017. Define
operation-specific enums beside their operations or in a
lightweight sibling module; expose shared domain options through the named facade.

| Current location and argument | Proposed enum | Values |
| --- | --- | --- |
| `duration/period.py`, `timing` in Period and Movement methods | `duration.PeriodTiming` | `first`, `last`, `end`; FIRST, LAST, END; migrate existing start/last_day names under RF-017 |
| `duration/calendar.py`, `frequency` | `duration.Frequency` | `day`, `week`, `biweek`, `month`, `quarter`, `halfyear`, `year`, `biennium`, `quinquennium`, `decade` |
| Calendar offsets and anchored sequences, replacing `month_end` | `duration.MonthRoll` (working type name) | `preserve_end`, `clamp`; default PRESERVE_END; no MONTH_END member; see RF-016 |
| Calendar and financial operations, `day_count` | `duration.DayCount` | `actual/365`, `actual/360`, `actual/actual`, `30/360` |
| `_behaviors/flow.py` and `calculations/series.py`, `missing` | `model.flow.MissingValueHandling` | `error`, `propagate`, `skip`, `zero` |
| `calculations/series.py`, `join` | `calculations.series.AlignmentJoin` | `exact`, `union`, `intersection` |
| `Alignment.reduce()` and `aggregate()`, `reducer` | `calculations.series.AggregationReducer` | `sum`, `min`, `max` |
| `resample()`, `reduction` | `calculations.series.ResamplingReduction` | `sum`, `first`, `last`, `mean`, `min`, `max` |
| `resample()`, `weighting` | `calculations.series.MeanWeighting` | `observations`, `elapsed`; retain `None` separately |
| Account calculation/schedule, `balance` | `account.Balance` | `opening`, `closing`; OPENING/CLOSING; see RF-015 |
| Account calculation/schedule, `current_interest` | `account.CurrentInterest` | `excluded`, `included`; EXCLUDED/INCLUDED; see RF-015 |
| Account calculation/schedule, `treatment` | `account.InterestTreatment` | `separate`, `financed`; SEPARATE/FINANCED; INCLUDED requires FINANCED |
| `calculations/projection.py`, `method` | `calculations.projection.ProjectionMethod` | `recurring`, `linear`, `compound`, `dynamic` |
| Projection padding, `left` and `right` | `calculations.projection.PaddingMode` | `nil`, `unitize`, `extend` |
| `adapters/plotting.py`, partition `kind` | `adapters.plotting.PartitionKind` | `sunburst`, `treemap` |
| Layout `Preference.direction` | Layout-owned `PreferenceDirection` | `unspecified`, `horizontal`, `vertical`, `balanced` |
| Layout preference order axis | Layout-owned `Axis` | `x`, `y` |
| Layout `Arrangement.flow` | Layout-owned `ArrangementFlow` | `grid`, `row`, `column` |
| Layout `Arrangement.alignment` | Layout-owned `ArrangementAlignment` | `start`, `center`, `end` |
| Layout `Arrangement.spacing` | Layout-owned `ArrangementSpacing` | `uniform`, `packed` |

Use `ACTUAL_365`, `ACTUAL_360`, `ACTUAL_ACTUAL` and `THIRTY_360` for the DayCount
member names; retain the existing slash-delimited values. Generated names must
use a deterministic identifier conversion and fail on collisions or invalid
identifiers rather than silently renaming members.

Do not merge `MissingValueHandling` with schema `MissingHandling`: their options
and operations differ (`skip` versus `omit`, for example). Keep aggregation and
resampling choices separate because the supported sets differ. Account balance
selection is distinct from Period date selection; the legacy account timing
argument is removed under RF-015. Do not replace graph reducer callables with
an enum: their callable interface is a separate extension mechanism.

#### Additional public-result inventory from the integrated review

The following dispositions cover the review's returned fields as well as input
arguments. Define each converted enum at the named owner and export it beside its
public result type. Preserve these wire/display strings. Migrate constructors,
dispatch, return annotations, JSON/report encoders, tests and consumers together.

| Candidate | Disposition and public owner | Values or reason to retain |
| --- | --- | --- |
| `graph.reduction.Coverage.status` | Convert to `graph.reduction.CoverageStatus` | `empty`, `complete`, `incomplete` |
| `graph.hierarchy.Hierarchy.kind` | Convert to `graph.hierarchy.HierarchyKind` | `relationships`, `membership`; this is a closed construction mode, not a relationship type identifier |
| `graph.projection.FieldColumn.field` | Convert to `graph.projection.EntityField` | `model_id`, `entity_id`, `code`, `name`, `entity_kind`, `classification_id`, `classification_code`, `classification_name` |
| `workflow.checking.CheckResult.status` | Convert to `workflow.checking.CheckStatus` | `agree`, `difference`, `unavailable`; apply to RF-023's composed result too |
| `workflow.checking.CheckResult.category` | Retain string at `workflow.checking` | Authored report grouping is open; `comparison` and `invariant` are built-in labels, not the complete domain |
| `workflow.workbench.Inspection.status` | Convert to `workflow.workbench.InspectionStatus` | `invalid inputs`, `not built`, `previous output unavailable`, `unverified inputs`, `current`, `stale`, `invalid specification or environment` |
| `workflow.workbench.Attempt.status` | Convert to `workflow.workbench.AttemptStatus` | `completed`, `failed`, `interrupted` |
| `workflow.progress.Progress.phase` | Convert to `workflow.progress.ProgressPhase` | `workflow`, `step`, `composition`, `checks`, `export`; operation-specific step identifiers remain strings in `step` |
| `workflow.progress.Progress.status` | Convert to `workflow.progress.ProgressStatus` | `running`, `completed`, `failed`; retain observer-error isolation and interruption behavior |
| `workflow.source_checks.SourceCheck.status` | Retain string at `workflow.source_checks` | Deferred declarations and registered native source checks supply open assessment labels; retain their validation |
| Layout `Result.status` | Convert to `adapters.cytoscape.layout.result.ResultStatus` | `unknown`, `feasible`, `infeasible`, `optimal` |
| Layout `Result.strict_status` | Convert to `adapters.cytoscape.layout.result.StrictStatus` | `sat`, `unsat`, `unknown`; explicitly map solver-native results at each adapter boundary |
| Layout `Result.mode` | Convert to `adapters.cytoscape.layout.result.ResultMode` | `strict`, `diagnostic`; retain the current geometry export values |

Relationship type identifiers, authored categories and registered operation names
remain open strings. Do not infer an enum merely because a scan finds only a few
current values. Conversely, returned closed fields must not escape conversion
because they are absent from argument signatures or Literal aliases. W1 must
check additional candidates against this same rule and record any new disposition.

Do not combine these into one status enum because some values have the same
spelling. In particular, layout optimality, Run solution status, workflow checks
and graph coverage have different domains and acceptance meanings.

#### Existing enums and exclusions

- `evidence.ClaimKind` describes the same sourced, asserted and derived categories
  as the schema type. Replace the handwritten definition with a re-export of the
  generated `ClaimKind`. Keep transient evidence objects distinct from persisted
  Claims. Update workflow publication to pass the member into the typed Claim
  constructor instead of passing `claim.kind.value`.
- `operation.IssueSeverity` currently duplicates the schema's info, warning and
  error choices. Use canonical `Severity` for both, expose it from `operation`,
  and migrate active `IssueSeverity` imports. Remove the old type name without a
  compatibility alias. Sharing severity does not merge diagnostic record types
  or make severity decide operation availability.
- Keep names, keys, UUID text at wire boundaries, paths, labels, descriptions,
  diagnostic codes, unit expressions and registered operation identifiers as
  strings. Keep booleans as booleans and class-valued arguments such as codec
  `kind=Model` as classes.
- Retain scenario method identifiers as strings rather than closed enums. RF-021
  replaces version-suffixed names with stable method names and records calculation
  implementation provenance separately; old identifiers belong to explicit migration.
  They identify versioned implementations, including captured history; the
  currently supported methods are not the complete historical identifier space.
  Existing capability validation still rejects unsupported execution requests.
- Keep external library option strings inside their adapters. Convert an RK enum
  to the external vocabulary explicitly; do not expose a third-party enum as the
  canonical RK type.
- Do not edit legacy enum definitions, stored research results or historical
  walkthrough output. Update maintained walkthrough source and regenerate its
  current output only as part of the agreed verification work.

### Generator and package structure

Generate a new lightweight `_schema/enums.py` from LinkML. It contains only enum
definitions and an enum registry, for example `_ENUM_TYPES`, keyed by schema enum
name. It imports no records, behaviour mixins, validators or optional packages.
Have generated records import and re-export these classes. Keep the existing
record registry `_TYPES` separate from the enum registry.

Update generation manifests, output checks and package verification to include
the new file. Generation must remain deterministic. Do not edit generated output
by hand. Schema membership and JSON Schema constraints remain unchanged.

For handwritten enums, use modules that do not import the consuming service.
Flow behaviour needs its missing-value enum without importing `model/__init__.py`
while generated records are loading. A lightweight behaviour-side definition,
re-exported from `model.flow`, is acceptable. Duration choices can live in a
lightweight duration options module; use type-only or local imports in behaviour
mixins where package initialization would otherwise create a cycle. Verify the
actual import graph rather than assuming that a submodule bypasses `__init__.py`.

Coordinate duration enum ownership with RF-016. Frequency has one shared day/month
step definition used by calendar operations, not just an enum substituted into
scattered string branches. Keep this metadata independent of pandas frequency
codes and preserve RF-016's distinct offset, alignment and measurement contracts.

Match RF-001's import boundary: loading enum definitions or policy availability
must not load policy evaluation, a solver, dataframe, plotting library or random
generator. Preserve editor completion, `__all__` and `dir()` for public facades.

### Typed records and wire conversion

[`_records.py`](../src/rangekeeper/_records.py) already distinguishes schema slot
categories. Extend that mechanism; do not teach the general JSON copier to
serialize arbitrary enum objects.

| Boundary | Required behaviour |
| --- | --- |
| Typed constructor or `replace()` for an enum slot | Require the declared enum class; encode its explicit `.value` |
| Wrong enum with the same underlying text | Reject; matching text does not establish type compatibility |
| Raw string in a typed enum argument | Reject, including a string that is a valid wire value |
| `from_data()`, JSON or YAML input | Accept existing valid string values; retain current rejection of unknown values |
| Generated property access, including nested records | Decode the stored string to the canonical enum member |
| `to_data()`, JSON or YAML output | Emit exact built-in strings, never member names, enum objects or class-qualified representations |
| Omitted, null and empty fields | Preserve the existing distinctions and `UNSET` behaviour |
| Opaque Content or an ordinary string slot | Do not infer enums from matching text; retain strict JSON validation |

Keep the frozen `_data` representation as validated JSON-compatible values.
Property decoding does not mutate stored data. Constructors, replacement, nested
decoding and direct wire loading must agree on the public enum type.

No current enum slot was found to use a union, mapping or multivalued shape in
the inspected `slots.json`. Preserve the generic slot logic. Have generation fail
clearly if a future enum-bearing shape cannot be handled without ambiguity;
do not introduce an untested implicit conversion path for hypothetical shapes.

Update active constructor calls and comparisons throughout the package. Treat
each site according to its representation: `record.kind` becomes an enum, while
`record.to_data()["kind"]` remains a string. Replace string defaults, dispatch
tables and string-keyed lookups that operate on typed choices. Check f-strings,
logs, external requests and dynamically selected operations such as the Polars
reduction in `resample()`; these may need explicit `.value` or a dispatch table.
Use complete dispatch for supported members so an added enum does not silently
fall into an unrelated `else` branch.

### Other serialization and provenance boundaries

Layout uses its own dataclasses and versioned documents. Its current
[`Problem.document()`](../src/rangekeeper/adapters/cytoscape/layout/model.py)
starts with `asdict()`, which will not convert plain enums into JSON strings.
Add explicit field-aware conversion there and in `from_document()`, including
the axis inside each order tuple. Preserve v2, v3 and v4 documents and their
existing fingerprints for unchanged input. Migrate layout solver, checker,
renderer and viewer callers without changing their geometry or scoring rules.

Audit worker messages, adapter payloads, CSV/table projections and runtime result
serialization. These boundaries must continue to send their documented strings.
Do not depend on `str(member)`, which is not the enum's wire value.

`_encoding.py` and `_structured.py` use exact-type, type-sensitive fingerprint
encoding. Do not broaden them to accept any enum or encode Python class paths.
At known operation boundaries, serialize each declared choice to its stable
string value before recording a specification or computing a parameter digest.
Preserve parameter meaning and historical records. Source-based implementation
fingerprints may legitimately change with the code; distinguish those from
unchanged data fingerprints in verification evidence.

C# currently exposes schema enum fields as strings. This item changes the Python
API only. Keep C# wire behaviour and supported records unchanged, run its generation
check, and run the Python/C# round-trip checks. A native C# enum API would require
a separate intent covering its generator and serializers. Do not manually alter
the stock LinkML native classes to match the custom Python runtime.

### Implementation sequence

1. Finish the candidate inventory and public export map. Record retained strings
   and private Literals with reasons. Capture representative wire documents,
   layout fingerprints and relevant current test results before changing code.
2. Generate the schema enum module, registry and record annotations. Add the
   slot-aware encoder and decoder changes as one coherent foundation.
3. Add runtime-only enums, public exports and strict argument checks. Change
   defaults to enum members. Preserve existing default behaviour and `None`
   semantics. Reuse canonical ClaimKind and Severity.
4. Migrate typed callers through Model, Specification, Run, formulations,
   calculations, scenarios, policies, execution, graph, workflows and adapters.
   Update active migration paths, examples, tests and maintained walkthroughs.
5. Update explicit wire adapters, layout documents, parameter recording and
   external-library dispatch. Keep raw-wire validation on strings.
6. Integrate RF-001 with the enum changes. In particular, period resolution in
   observation code uses `PeriodTiming.LAST`; policy construction and decision
   code use generated `ActionKind`. RF-001's date-only helper remains enum-free.
7. Run focused checks, generated-artifact checks, typing, package checks and the
   combined regression suite. Update current guides and the upgrade guide with
   before/after Python examples and unchanged wire examples.

### Verification and completion criteria

| Area | Required evidence |
| --- | --- |
| Enum generation | Every schema choice produces one canonical member; explicit values and identifiers are stable; duplicate or colliding names fail generation |
| Runtime argument checks | Raw strings, unrelated enums with the same value, and other wrong types fail at the public boundary; valid enum arguments retain current results |
| Record construction and replacement | Required and optional enum slots accept the right type; nested reads return that same type; omission and null semantics remain unchanged |
| Persistence | Existing JSON/YAML fixtures round-trip to the same data; unknown wire values still fail; no enum object leaks into output |
| Static typing | Valid enum calls pass; raw-string calls and cross-enum calls fail; generated constructors, methods and facade re-exports remain typed |
| Calculations and policies | Existing date, missing-value, alignment, interest, projection and policy examples retain their numerical and causal results |
| Layout and external adapters | Explicit conversion preserves versioned documents, fingerprints, viewer payloads and solver inputs; supported layout checks pass |
| Imports and packaging | Fresh-process import orders pass; enums and record imports load no optional numerical or presentation packages; built wheel contains the new module |
| Open text | Custom names, keys, unit expressions and valid extensible identifiers still work; no blanket enum conversion reaches opaque data |
| Provenance | Fixed input data and parameters retain their established encodings; changed implementation fingerprints are identified separately |

Use existing tests as behavioural oracles, especially `test_records.py`,
`test_record_behavior.py`, `test_flow_dates.py`, `test_flow_operations.py`,
`test_calculations.py`, `test_calculation_equivalence.py`, `test_domain_model.py`,
`test_domain_specification.py`, `test_domain_run.py`, `test_domain_io.py`,
`test_scenarios_policies.py`, graph/workflow tests and the affected layout suites.
Add focused enum boundary tests where existing coverage does not exercise the
new contract. Do not replace useful numerical assertions with type-only tests.

Extend the valid and deliberately invalid fixtures used by
[`tools/schema/typecheck.py`](../tools/schema/typecheck.py). Update expected
diagnostic counts only after inspecting each intended rejection. Add the new
generated enum module and handwritten option modules to its checked source set;
do not rely on silently followed imports as proof that those modules type-check.
Run generation
checks for Python and C#, installed-wheel verification, cross-language round trips
and the final regression checks in [Verification](VERIFICATION.md). Verify Python
3.10 as well as the primary development interpreter; missing access to a supported
runtime is an explicit verification gap, not an assumed pass.

RF-002 is complete when the inventory is dispositioned, all selected choices use
their canonical enums, all active callers are migrated, wire contracts are
preserved, and the required checks pass. No `Enum | str` fallback, silent string
coercion, duplicate enum definition or compatibility alias may remain for a
converted public choice. Current documentation must state the Python API break
and the explicit text-input conversion path. No schema version change is needed
if the preserved wire contract checks pass; any proposed wire change requires
separate scope and migration planning.

### Implementation record

Implemented in the coordinated working-tree pass. The generator emits `_schema/enums.py` with unique plain Enums and public facade re-exports. `_records.py` encodes typed fields and decodes wire text. Handwritten calendar, account, calculation, graph, workflow and layout choices use enums at their own owners.

Typed constructors/replacement reject strings and wrong enums; JSON values remain text. Worker, profile and persisted workflow boundaries encode explicitly. Generated C# wire fields retain their existing string representation and shared schema constraints. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-003 Create the expression package and compose semantic analysis

### Problem and ownership

`model/_expression.py` contains active
semantic checks used by Formulation, Model, Specification and policy validation.
Its logic is required, but its current boundary mixes declaration indexing,
Value-content checks, Function validation, expression traversal, domain inference
and Constraint predicate checks. Moving the file alone will not resolve this.

`model/expression.py` exposes generated
record classes. Replace this module with an `expression` package whose initializer
preserves those exports. Keep generated definitions in `_schema/records.py` and
authoring constructors in
[`formulations/expression.py`](../src/rangekeeper/formulations/expression.py).

The expression package owns declarations and checks of their meaning within a
supplied scope. Shared scope construction belongs to `model/scope.py`, because
Formulations, Specifications and policies also use that scope. Numerical
evaluation, constraint satisfaction and solver capability remain separate.

RF-008 explicitly adds a separate pure numerical evaluation module to this
package. It does not merge evaluation with semantic analysis or make validation
depend on supplied runtime quantities. Policy truth evaluation and execution
acceptance retain their own owners under RF-008.

### Intended structure

```text
src/rangekeeper/
  model/
    scope.py
      Scope
      build_scope(...)
    expression/
      __init__.py                  preserve existing public record exports
      domains.py
        domain_of_value(...)
        numerical_units(...)
        compare_domains(...)
        infer_operator_domain(...)
        infer_selection_domain(...)
      validation.py
        ExpressionAnalysis
        validate_function_signature(...)
        bind_arguments(...)
        validate_query_references(...)
        infer_query_domain(...)
        analyze_expressions(...)
        validate_constraint_predicates(...)
    formulation/                   RF-005: local rules and resolved orchestration
    _formulation.py                RF-005: remove after migrating callers
    _expression.py                 remove after migrating callers
  formulations/
    expression.py                  retain expression constructors
```

Use descriptive module names without leading underscores for these reusable
components. Do not add a redundant `expression/expression.py`. Existing imports
such as `from rangekeeper.model.expression import Expression, Domain` must work.
Keep `__init__.py` limited to record exports so importing records does not load
validation, policy runtime or execution. The proposed helper names describe
responsibilities; finalize signatures during dependency reconciliation.

Use ordinary functions and small typed data classes. A visitor class hierarchy,
plugin registry or global cache is not required for this item.

### Composition within the modules

#### Scope construction and validation stages

Make the owning validator compose these stages explicitly:

```text
Validate record structure
  -> Build scope and check declaration identities
  -> Validate Value content and Function signatures
  -> Analyze expressions
  -> Validate Constraint predicates and other consumers
```

`build_scope()` constructs lookup tables from prepared declarations. Detect
identity conflicts during indexing. Move Value-content and Flow-content checks
out of the builder into explicit validation steps with an appropriate domain
owner. Derive Value domains only after their prerequisites pass. Function
signature checks must no longer be a hidden side effect of building the scope.
Skip dependent stages after a prerequisite failure.

Retain owner-local naming checks in Formulation orchestration. Preserve combined
Model/Specification mathematical scopes, including Relationship Values, local
Formulation Values and Movement references. Assess reuse of
`model/_index.py` for schema-directed traversal
and ownership rather than maintaining competing declaration rules. Its index
over one root is not, by itself, a replacement for a combined scope.

#### Traversal and domain rules

Use one expression-analysis traversal to manage recursion, node identities,
reference resolution, source paths and result collection. Delegate local domain
rules to functions in `domains.py`. For example, analyze the children of a binary
expression, pass their domains to `infer_operator_domain()`, then record the
result. Domain rules must not recursively walk expression trees or manage a
shared identity set.

Keep domain compatibility directional: an inferred argument domain is checked
against a declared parameter domain. Preserve the distinction between a quantity
and a Measurement's declared meaning. Arithmetic does not establish a Measure
identity merely because its units match.

#### Argument binding

Extract `bind_arguments()` from the call-expression branch. It checks excess
positional arguments, unknown names, duplicate bindings and missing required
arguments. Return explicit parameter-argument pairs, with source locations, for
the analyzer to check against declared domains. Binding does not evaluate or
analyze expressions. Keep omitted optional arguments absent unless their contract
explicitly defines defaults.

#### Reusable analysis results

Return an `ExpressionAnalysis` with read-only `nodes_by_id`, `domains_by_id` and
`paths_by_id` mappings. Analyze each declared expression once within its prepared
scope. Constraint validation then checks that a predicate exists in the analysis
and has a Boolean domain. Specification objectives can use the same result;
policy conditions can use the same analyzer within their appropriate scope.

Detect duplicate declarations before reusing results. Multiple Constraints may
reference the same expression, but repeated embedded declarations must still
fail. Keep analysis results local to one prepared scope and immutable for their
consumers. Do not reuse cached domains across different scopes or revisions.

#### Incomplete domain knowledge and query correctness

Distinguish declared domains from incomplete inference results. Domain comparison
must express compatible, incompatible and not established outcomes. Each caller
must define how it handles an unproven result; uncertainty must not silently pass
a required Function argument check. Missing units do not mean dimensionless.

Correct the existing query assumption as an explicit behaviour change. The
current `infer_query_domain()` labels Value projections as measurements, although
Values also support flows and properties. A read-only probe on 2026-10-06 created
a property Value selected by key: its scope domain was `property`, but the inferred
query item domain was `measurement`. Measure-based projections also need review
because flows carry Measures.

Separate query-reference validation from query-domain inference. If declarations
do not establish the result domain without traversal, represent that uncertainty.
Do not execute a graph query to make static validation appear complete. Keep this
correction distinct from the package move and behaviour-preserving extractions.

#### Required query acceptance matrix

Infer a query's item domain conservatively from statically eligible declarations:
apply declared key/Measure filters to the complete permitted Value inventory,
without following graph membership edges. A nonempty candidate set supports a
known item domain only when every candidate establishes the compatible domain,
units and shape required by the caller. Missing candidates, mixed kinds or
insufficient declarations yield unproven information; empty sets do not prove a
type. Preserve cardinality and collection-kind distinctions in the result.

| Query result knowledge | Required Function argument, predicate or objective | Standalone passive reporting query |
| --- | --- | --- |
| Proven compatible | Accept the domain check | Accept |
| Proven incompatible | Reject at the original source location | Retain only where no incompatible contract is imposed |
| Unproven, including mixed property/Flow/measurement candidates | Reject the required contract with an uncertainty diagnostic | Allow the declaration; do not claim a known numerical domain |

Apply that policy to these independent acceptance cases. A query collection is
not itself a Boolean predicate or scalar objective. Subsequent expression analysis
must establish the required result, including units and shape.

| Statically eligible Value candidates | Function collection argument | Predicate | Objective | Passive reporting query |
| --- | --- | --- | --- | --- |
| Homogeneous compatible measurements | Accept a matching measurement-item domain, including declared Measure/units | Accept only if the full expression proves scalar Boolean | Accept only if the full expression proves the required scalar numerical domain | Accept with the proven collection domain |
| Homogeneous properties with known declared domain | Accept only a matching property-item domain; reject a measurement requirement | Require a supported expression that proves scalar Boolean | Require an explicit supported operation that proves a numerical result; do not treat properties as measurements | Accept with the proven property domain |
| Homogeneous compatible Flows | Accept only a matching Flow-item domain; reject a scalar-measurement item requirement | Require a supported expression that proves scalar Boolean | Require a supported reduction or operation that proves the required scalar domain | Accept with the proven Flow domain |
| Mixed Value kinds, incompatible units/shapes or incomplete item declarations | Cannot satisfy a required homogeneous item domain | Reject where the Boolean result depends on that unproven item domain | Reject where the numerical result depends on that unproven item domain | Allow without claiming one known numerical item domain |
| Unknown or empty static candidate inventory | Cannot prove a required item domain; report uncertainty | Reject if the required Boolean domain cannot be established | Reject if the required numerical domain cannot be established | Allow as unproven; an empty inventory does not prove a type |

Reference validity and other structural checks still apply to passive queries.
Known incompatibility must not be reported as mere uncertainty. Do not infer the
runtime membership or result count from the static candidate inventory.

Freeze the expected handling of `schema/examples/model.yaml`'s `floor_area`
collection argument: the homogeneous eligible measurement declarations must
establish its required item domain without executing the query. Add a property
or incompatible Flow candidate with the same key and verify that the same proof
no longer succeeds. A Measure filter alone is not proof of a scalar measurement,
because Flow Values also carry Measures. Do not infer a type solely from the
Function's expected argument or execute queries during validation.

#### Diagnostics and fixture boundaries

Carry the source path through traversal, argument binding and domain checks.
Diagnostics should identify the failing operand or argument, including nested
Formulation ownership. Pass located Constraints to predicate validation so callers
need less translation from flattened positions back to original owners.

Move fixture-only `input_domains` preparation to schema-check or test helpers.
Review the illustrative `span` and `account` member rules: retain them as declared
production contracts only where supported, otherwise isolate them as fixture
behaviour. Do not remove supported member semantics solely because examples use
them. The production scope builder must not depend on a fixture envelope.

### Affected code and dependencies

Migrate direct consumers in `model/_formulation.py`,
`specification/_validation.py`, `specification/_policy_validation.py`,
`schema/checks/expressions.py` and `tests/test_validation_composition.py`. Review
Model validation adapters and the public Model initializer where they construct
or duplicate indexes. Update current architecture and API guides as needed.

RF-001 and RF-003 both affect Specification policy validation. Coordinate their
imports and tests in the combined pass; neither item authorizes moving all policy
validation. The new expression package must not introduce imports from its pure
checks back into Model, Specification or policy runtime initialization.

Coordinate domain and operator types with RF-002. Use its canonical enums for
closed choices rather than introducing parallel string constants or enum types
inside the expression package.

Coordinate traversal and reference checks with RF-004. Its index supplies
declaration lookup; this item's `Scope` still owns the combined mathematical
view. Reuse target-type checks before expression-specific eligibility and domain
inference. Do not create a second reference-rule registry.

RF-005 owns the Formulation package, located declaration collection and migration
of its callers. Consume its original locations during expression analysis and
return the analysis for reuse in Specification checks. Extract Value-content
checks from both old modules in one change, with one domain owner. Do not build
parallel collections, scope objects or diagnostic adapters for the two intents.

RF-009 consolidates target resolution and recorded scalar access alongside this
item's Scope. Keep expression-domain inference separate from scalar eligibility:
a whole Flow or property can be a valid reference without being a scalar solve
target. Reuse resolved targets without reading quantities during static analysis.

### Behaviour to preserve and exclusions

Preserve structural-validation prerequisites, duplicate-identity rejection,
owner-local names, reference type checks, Function parameter ordering, argument
binding rules, empty-collection contracts and Boolean predicate requirements.
Preserve non-mutation of inputs and keep predicate validity independent of current
truth or numerical feasibility.

Do not change generated record fields, persistent schemas or document versions.
Do not add full dimensional arithmetic, implicit unit conversion, query execution,
Function execution or solver support. Keep compiler and numerical acceptance
logic separate: a valid expression can exceed a solver's capabilities. A broader
migration of all dictionary-based validators to generated records is outside this
item unless separately agreed. Remove the retired private module without a
forwarding alias after migrating its callers.

### Implementation details to settle in W1

- Choose the typed representation for inferred domains and partial knowledge.
  Generated `Domain` records describe declared contracts; do not force unknown
  inference states into the persistent schema.
- Define the exact shared-scope inputs and the owner of extracted Value-content
  checks. Decide how much existing `Index` traversal can be reused without losing
  composed-scope support.
- Implement the required acceptance matrix above and freeze its diagnostic
  representation. Do not reopen permissive acceptance of unproven required types.
- Decide which member-selection rules are supported contracts and which belong
  only to schema fixtures.

### Verification

Baseline observed on 2026-10-06: `tests/test_validation_composition.py` returned
24 passes. This was a focused baseline, not a full regression run. Re-establish it
against the checkout used for implementation. The separate property-query probe
described above exposed behaviour not covered by that passing baseline.

Test argument binding independently, then test nested calls through the analyzer.
Cover duplicate declarations, shared predicate references, nested predicates,
Function signatures, selection rules, incomplete units and directional domain
compatibility. Check precise paths for failures inside positional arguments,
named arguments and nested Formulations. Verify that several Constraints and
objectives can consume one analysis without changing inputs or losing identity
checks.

Add query cases for property, flow and measurement Values, both key and Measure
selection, and cases where static knowledge is insufficient. Assert the agreed
unknown-domain behaviour and ensure validation performs no graph execution.

Run the expression schema checks, validation-composition tests and affected Model,
Specification and policy tests. In fresh processes, verify public record imports,
both relevant import orders and absence of eager runtime dependencies. Run the
minimal installed-package checks and the combined regression checks selected for
the full intent list. Check active imports and current guides for retired paths;
preserve historical documentation.

### Completion criteria

- The expression package preserves the existing public record import paths.
- Scope construction and semantic validation are explicit, composable stages.
- Argument binding and local domain rules are independently testable.
- One analysis supplies expression nodes, domains and source paths to consumers.
- Duplicate declarations still fail; shared predicate references remain valid.
- Query inference no longer assumes every projected Value is a measurement.
- Uncertain inference and fixture-only support have explicit boundaries.
- Diagnostics retain original source paths and inputs remain unchanged.
- Callers use the new modules, with no import cycles or retired active imports.
- Required focused, package and regression checks pass, and current guides match
  the implemented structure.

### Implementation record

Implemented in the coordinated working-tree pass. `model/expression/{domains,validation,evaluation}.py` replaces `_expression.py` and separates static analysis from arithmetic. One analysis indexes all nested nodes/domains and original pointers with UUID keys.

Query domains come from matching static declarations; mixed or absent candidates remain unproven. Required typed arguments reject uncertainty; passive expressions remain readable. The canonical area query and caller matrix have regressions. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-004 Separate record indexing from shared reference validation

### Problem and intent

`Index.check_known_references()` performs
semantic reference checking on a class that otherwise supplies declaration lookup
and containment ownership. Its only current caller is local validation in
[`specification/specification.py`](../src/rangekeeper/specification/specification.py).
The rule is required: a partial Specification may contain unresolved references,
but a locally declared target cannot have an incompatible record type.

Separate lookup, reference type checking and domain validation. Reuse target
definitions and checking logic across local and complete validation without
merging their different resolution requirements. Integrate semantic failures
with the existing structured diagnostic path.

Also consolidate [`definitions._lookup()`](../src/rangekeeper/model/definitions.py)
through the existing `Index.get()` operation. This helper currently collects and
scans Measures, Functions, Taxonomies and nested Classifications on every call,
then repeats UUID lookup and missing/wrong-type error handling. RF-004's planned
index relocation carries this shared operation to `RecordIndex.get()`; do not
create another lookup implementation or retain the old index module for it.

Consolidate Assembly lookup as well. The private
[`graph.membership._assembly()`](../src/rangekeeper/graph/membership.py) calls
`Model.entity()` and then repeats the record-type check for Assembly. Its callers
are `entities_in()`, `relationships_in()` and Assembly selection in `View`.
Expose this typed lookup as `Model.assembly()` and use the existing Model index.

### Existing behaviour

The method walks embedded records using schema slot metadata. It derives allowed
target classes for each typed UUID reference, checks whether the target exists in
the index, and rejects an incompatible local target. It leaves absent targets
unresolved. For example, an unknown may refer to a local Value or Movement but
cannot refer to a local Formulation. A target outside the contribution is deferred
until the investigation has a complete scope.

Most target types come from schema metadata: `Binding.value` targets Value,
`Value.measure` targets Measure, and `Constraint.predicate` targets Expression.
`Reference.target` is a special case: its schema range is UUID, but its documented
contract permits only Value or Movement. The method hardcodes that pair.

Failures currently raise `ReferenceTypeError` with a path embedded in the message.
`bounded()` catches only `ContractError`, so this error escapes local Specification
validation instead of becoming an Issue. The existing test
`test_locally_known_role_target_cannot_masquerade_as_value` expects that exception.

### Intended ownership and interfaces

| Responsibility | Owner |
| --- | --- |
| Schema-directed traversal, duplicate-ID detection and containment lookup | Shared internal `RecordIndex` and `walk()` |
| Typed UUID lookup within one Definitions catalogue | `RecordIndex.get()` on a catalogue-scoped index; existing public Definitions helpers delegate to it |
| Assembly UUID lookup within one Model revision | `Model.assembly()` delegates to its existing index's `get(id, Assembly)` |
| Check known references against their allowed target types | Shared semantic check in the existing `_validation.py` infrastructure |
| Decide whether a target must resolve at this stage | The calling Model, Specification or Run validator |
| Load an external document revision | The explicitly supplied resolver |
| Check numerical eligibility, units, roles, ownership restrictions and expression domains | The relevant domain validator |

Proposed structure:

```text
src/rangekeeper/
  _record_index.py
    walk(...)
    RecordIndex
      build(root)
      get(identity, kind)
      records
      owners
      paths                     original root-relative declaration pointers
  _validation.py
    validate_known_reference_types(root, *, index)
    ... existing semantic primitives and orchestration
  model/scope.py                  RF-003's combined mathematical scope
  specification/specification.py partial contribution checks
  specification/validation.py    complete investigation checks
  run/validation.py              local and resolver-backed checks
```

Move generic traversal and indexing out of `model/_index.py`, rename `Index` to
`RecordIndex`, and migrate active imports. Keep this private; remove the retired
path without a forwarding alias. Preserve read-only mappings, encounter order,
revision isolation and nearest identified containment ownership. UUID references
are not embedded records, and opaque Claim content remains opaque.

The semantic check consumes the caller's existing index. It performs no IO and
does not rebuild the index for each field. Expected record types remain Python
classes, not an enum of record kinds. Share a small target-type primitive with
complete validators only where this replaces equivalent checks. Do not add a
reference service, visitor hierarchy or general validation framework.

RF-009 owns the domain-specific Value/Movement resolution and scalar-access
consolidation. It consumes this index and reference checks; it must not add
numerical units or recorded-quantity rules to the generic RecordIndex. Preserve
the distinction between direct lookup exceptions and semantic diagnostics.

Keep record infrastructure independent of Model facades, policy execution,
storage and optional numerical libraries. Reconcile imports with RF-003 before
moving the index; shared validation must not introduce a dependency cycle.

RF-005's located Formulation collection should reuse this traversal where its
representation permits. Retain source-document paths and sibling collection
boundaries above the generic index. Do not add a second generic record walker
or repeat complete reference checks inside Formulation validation.

Retain paths yielded by `walk()` instead of discarding them during index
construction. Located collections add the source document UUID; composition must
not replace the original pointer with a flattened effective-record location.
For anonymous records, preserve their traversal location even though UUID lookup
does not index them. Reuse a Model's existing index for repeated catalogue reads;
standalone Definitions lookup still uses its own narrower catalogue scope.

### Definitions catalogue lookup

Retain `definitions.measure()`, `taxonomy()`, `classification()` and `function()`
as typed public entry points. Replace their manual record collection and search
with the generic index's `get(identity, kind)` operation. Keep expected types as
record classes. No separate catalogue resolver or record-kind enum is needed.

Build the index from the supplied Definitions record. Include Measures, Functions,
Taxonomies and nested Classifications through the shared schema-directed walker.
Do not substitute an unrestricted Model index: a UUID outside this catalogue must
remain missing, even when it identifies a record elsewhere in the Model. Search
all catalogue record kinds so an existing UUID of the wrong kind still raises
`ReferenceTypeError` rather than `MissingReferenceError`.

Preserve `None` and empty Definitions as empty catalogues. Validate the UUID
argument before catalogue preparation or missing-reference reporting, including
when the catalogue is empty. Keep this small input boundary separate from the
shared lookup implementation; an empty index can use the same `get()` error path.
Do not reinterpret UUID strings or codes as identities.

Adopt duplicate-UUID rejection explicitly. The current helper returns the first
matching record; index construction raises `IdentityConflictError` for any
duplicate declaration in the supplied catalogue. This includes duplicates across
record kinds and Taxonomies, even when the requested UUID is unrelated. Document
this stricter standalone Definitions behaviour and test it. Preserve the index's
existing duplicate rejection for Model and Specification construction.

For repeated catalogue access, prepare the catalogue index once and reuse it
within the owning preparation or revision. Coordinate ownership with RF-006.
Standalone convenience calls may build a temporary index; do not claim that this
improves their lookup cost. Settle the smallest reuse interface before migration,
while retaining existing public helper signatures. Do not add a global cache,
mutate generated Definitions records or create a second index class. Do not reuse
an index for a different catalogue or revision.

Leave `find_measures()`, `find_taxonomies()`, `find_classifications()` and
`find_functions()` as code searches. Preserve case-sensitive matching, declaration
order, multiple results and empty tuples for no match. Code search and UUID
resolution have different contracts.

### Assembly lookup through Model

Add the following method alongside `Model.entity()` and `Model.relationship()`:

```python
def assembly(self, id: UUID) -> Assembly:
    return self._index.get(id, Assembly)
```

This uses the existing revision-local index, which becomes `RecordIndex` under
this intent. It does not build another index or scan System assemblies. Keep
`Model.entity()` unchanged: Assembly inherits from Entity, so that broader lookup
must continue to accept both ordinary Entities and Assemblies.

Replace `_assembly(model, assembly)` with `model.assembly(assembly)` in
`graph.membership.entities_in()`, `graph.membership.relationships_in()` and
`graph.view.View`. Remove `_assembly()` and the private cross-module import from
`View`. Remove imports used only by the retired helper.

Preserve the explicit Model argument checks at the public graph boundaries.
`entities_in()` and `relationships_in()` currently obtain this check through the
helper; retain it before calling the new method. `View` already checks its Model
argument, so reuse that check. Preserve existing argument-check order, including
lookup before the `recursive` check in `entities_in()`.

Preserve strict UUID input, `MissingReferenceError` for an absent identity and
`ReferenceTypeError` for an ordinary Entity or another record kind. Adopt the
index's standard wrong-type message, which names the actual and expected types;
do not retain a second message formatter for Assembly lookup. The result must be
the canonical Assembly record from the current Model revision, with no history
or resolver fallback.

Keep graph semantics unchanged: direct and recursive membership, root exclusion,
shared-descendant deduplication, declaration order and View selection rules.
This change adds a typed Model accessor, not graph traversal to Model or graph
dependencies to the index. Coordinate typed API checks and documentation with
the existing Model lookup methods.

### Resolution boundaries to preserve

| Context | Required result |
| --- | --- |
| Partial Specification, compatible local target | Pass this type check; retain other local rules |
| Partial Specification, incompatible local target | Reject immediately with `reference.kind` |
| Partial Specification, target absent locally | Defer resolution; do not contact a resolver |
| Complete Model, required internal target missing | Reject in the applicable semantic stage with `reference.missing` |
| Complete investigation, target supplied by Model or contributors | Resolve in that leaf's combined scope, then check type and domain eligibility |
| External revision reference | Retain exact revision and document-kind checks through the existing resolver |
| Sibling batch cases | Keep scopes separate; a sibling cannot supply missing declarations |

Keep the extracted function at the existing partial-validation stage. Complete
validators can reuse target-type checks after resolving in their correct scope.
Map each overlapping check's type, existence, scope and diagnostic responsibilities
before removing it. Sharing a reference does not make two domain checks redundant.

A single-root index does not replace RF-003's combined Model/Specification scope.
Retain collision checks across contributors. Avoid converting all dictionary-based
validators into typed-record validators as an incidental part of this item; use
the smallest explicit boundary needed for shared checking.

Keep numerical-role and unit checks after target resolution. An Expression target
still needs Boolean-domain validation before it can serve as a Constraint
predicate. Preserve the separate restrictions on `model`, `includes`, `cases`
and `metadata.previous`: Metadata as a target type does not establish the kind of
its owning document or permit a reference to a local declaration.

### Reference definitions and diagnostics

Derive allowed types from generated slot metadata wherever the schema declares
them. For `Reference.target`, prefer a machine-readable schema annotation carried
into generated metadata, while retaining the current UUID wire shape. Verify its
support in the pinned LinkML tools and preserve Python/C# schemas and fixtures.
If this requires a wire change or disproportionate machinery, retain one explicit
semantic rule in shared validation and record the reason. Do not duplicate the
Value-or-Movement rule across validators or infer types from names or UUID text.
Plain identity UUID fields without a target rule are not references to resolve.

Coordinate any metadata changes with RF-002's generator work. Do not broaden
structural JSON validation into external-reference resolution.

Semantic checks raise `ContractError` with `reference.kind` or `reference.missing`
and a structured JSON Pointer in `path`. Include the target UUID, permitted types
and actual type when known in the message. Preserve the source path, including
collection indices and escaped field tokens. The caller supplies the document ID
when converting the failure into an Issue.

Keep `bounded()` prerequisite gating and first-error behaviour. Do not make it
catch every TypeError or LookupError, which could hide programming errors.
Direct `RecordIndex.get()` and Model lookups retain `MissingReferenceError` and
`ReferenceTypeError`. Resolver failures retain their existing diagnostic mapping.

Local Specification construction deliberately changes from a bare
`ReferenceTypeError` for an incompatible target to `ValidationError` containing
an Issue with `reference.kind`, document ID and path. Update the targeted test
and upgrade guide. The Definitions consolidation above separately adopts existing
index duplicate rejection for standalone catalogue lookup. Do not change other
argument-type or duplicate-identity exceptions as part of this item.

### Deletion targets and implementation sequence

Remove `Index.check_known_references()` and the old private index module after
migrating their callers. Replace equivalent target-type branches with shared
checks; remove duplicate special-case definitions if found. Extend existing
validation and reporting mechanisms instead of adding another reporting layer.
Delete the manual catalogue list, scan and duplicate resolution errors from
`definitions._lookup()`. Remove the helper if direct delegation suffices; retain
only minimal input preparation if required, with all resolution in `get()`.
Remove `graph.membership._assembly()` and `View`'s import of it after migrating
all three callers to `Model.assembly()`. Retain public Model argument checks.
The index move is relocation, not a line-count reduction. The target is neutral
or lower handwritten code size for this item, with fewer mixed responsibilities.
Record any necessary diagnostic or metadata growth under the overall strategy.

1. Inventory current reference checks, their scopes, diagnostics and callers.
   Agree traversal and resolved-target interfaces with RF-003. Record the size
   baseline and the exact branches to remove.
2. Extract the shared record index and migrate Model construction, validation,
   unit checks, diff, Specification local checks, execution preparation and
   acceptance, plus direct tests and schema checks. Migrate Definitions helpers
   to catalogue-scoped typed lookup; establish index reuse with RF-006 and record
   the explicit standalone duplicate-identity change. Add `Model.assembly()` and
   migrate membership and View callers to the existing revision-local index.
3. Extract the semantic check into existing validation infrastructure and
   centralize `Reference.target` semantics. Integrate structured local diagnostics.
4. Reuse equivalent checking in complete validation without losing domain,
   history or external-document rules. Remove only mapped duplication.
5. Update current architecture, reference and upgrade guides. Run focused checks
   and the combined regression, import and applicable generation checks.

### Verification and completion

Before this refactor, the two focused tests for locally incompatible role targets
and duplicate local references passed on 2026-10-06: 2 passed, 19 deselected. This
is evidence for those cases only. No implementation acceptance checks have run.

Add or extend tests for:

- Local Value and Movement targets, an incompatible Formulation target, and
  an absent target accepted by a partial Specification.
- Deferred resolution after composition, a target still missing from a complete
  scope, a wrong-type target supplied by another contributor, and isolated batch
  case scopes.
- Schema-derived Binding, Measure and predicate references, including permitted
  subclasses. A correct target type must not bypass numerical or Boolean-domain
  checks.
- Exact diagnostic code, document ID and path, including collection indices, and
  the new local-construction `ValidationError` contract.
- Unchanged lookup errors, duplicate-ID rejection, containment ownership,
  read-only mappings, encounter order and independent revision indexes.
- Definitions lookup for every supported record kind, including Classifications
  in different Taxonomies; missing UUIDs and wrong-kind catalogue entries.
- `None`, empty Definitions and invalid UUID arguments, including argument-error
  precedence. A UUID found only outside the supplied catalogue remains missing.
- Standalone catalogue duplicate rejection within and across record kinds and
  Taxonomies, including duplicates unrelated to the requested UUID.
- Repeated catalogue lookup reuses its prepared index, while another catalogue
  or revision has isolated results. Standalone temporary construction remains
  correct. Code searches retain their order, case sensitivity and multiplicity.
- Opaque content containing apparent IDs or references; traversal must ignore it.
- `Model.assembly()` returns the canonical Assembly record; `Model.entity()`
  still accepts that record. Cover missing and invalid UUIDs, ordinary Entities,
  other record kinds, revision isolation and the standard wrong-type message.
- Invalid Model arguments retain TypeError at membership and View boundaries.
  Preserve argument-check precedence, direct and recursive membership results,
  shared-descendant deduplication, declaration order and View Assembly selection.
- External Model/include/case/history references, wrong resolver document kinds,
  and absence of resolver calls during local checking.
- Fresh-process import order, installed-package inclusion of moved modules and
  absence of optional imports. Run generation and cross-language checks if
  reference metadata changes.

Use the affected Model, graph membership/View, Specification, Run, expression,
execution and schema conformance suites. Preserve RF-001 and RF-003's behavioural checks. Follow
[Verification](VERIFICATION.md) for the combined pass.

Completion requires removal of semantic checking from the index, one source of
reference target rules, structured semantic diagnostics, preserved direct lookup
errors and all required checks passing. Partial and complete validation must
share equivalent logic while retaining their different scope requirements.
Definitions helpers must use the shared typed lookup without a separate record
scan, preserve catalogue scope, and enforce the documented duplicate-ID rule.
Assembly callers must use `Model.assembly()` through the shared index, with the
private helper removed and graph behaviour preserved.
Record the metadata decision, removed code and final size comparison, and update
current documentation with the ownership and exception-contract changes.

### Implementation record

Implemented in the coordinated working-tree pass. `_record_index.py` owns record traversal, identity lookup, owners and source pointers; `references.py` owns scoped reference checks. The old Model index/reference modules are removed.

Schema-directed raw traversal excludes opaque property and Claim payloads. Prepared declaration lookup uses UUID keys throughout. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-005 Separate Formulation rules from scope preparation

### Problem and ownership

`model/_formulation.py` contains active
checks used by Model validation, composed Specification validation and schema
checks. Partial Specification validation also calls its local naming helper.
The module's references to a fixture scope no longer describe its production role.

The current 138-line module checks local names, containment ownership, Binding
targets and Constraint predicates. It also checks Characteristics on Entities,
Assemblies and Relationships, collects Relationship Values, checks all recorded
Value magnitudes and constructs the shared expression scope. These general domain
responsibilities should not belong to Formulation validation.

Keep Formulation naming, Binding checks and resolved orchestration together.
Move Characteristics key checks to their domain validator and finite quantity
checks to Value validation. Coordinate those extractions with RF-003's Value and
Flow checks. Shared scope preparation must gather Values from all supported
owners, replacing the current split between Relationship collection here and
Entity/Assembly collection in `_expression.py`.

### Intended structure

```text
src/rangekeeper/
  model/
    formulation/
      __init__.py                  expose Formulation and Binding records
      traversal.py                 collect declarations with original locations
      validation.py                local rules and resolved orchestration
    scope.py                       RF-003: shared mathematical scope
    expression/                    RF-003: domain and expression analysis
    _formulation.py                remove after migrating callers
  _record_index.py                  RF-004: generic traversal and lookup
  formulations/                    retain authoring builders
```

Replace `model/formulation.py` with the package initializer and preserve
`from rangekeeper.model.formulation import Formulation, Binding`. Keep generated
record definitions in `_schema/records.py`; importing the public records must
not load validation, policy runtime or execution. Use descriptive module names
without leading underscores for the reusable Formulation components. Do not add
a redundant `formulation/formulation.py` or a forwarding alias for the old private
module.

The module split must replace existing work. Prefer one small collection result
and direct functions. Do not introduce a separate visitor framework, generic
validation pipeline or result wrapper for each stage.

### Composition and shared results

#### Local and resolved checks

Preserve two distinct validation stages:

```text
Local checks
  ownership, sibling Formulation codes, Binding names,
  local Value keys and Constraint codes

Resolved checks
  Binding targets, expression references and domains,
  Constraint predicate references and Boolean domains
```

Reuse RF-004's ownership index and known-reference type checks at their existing
boundaries. Partial Specifications must permit absent external targets without
contacting a resolver; incompatible locally known targets still fail. Retain the
independently callable local naming check. Full Model or composition validation
owns required target resolution and the combined mathematical scope.

#### Located declaration collection

Replace separate Formulation collectors with one collection of located
Formulations, Values, Bindings, root Expressions and Constraints. Each location
retains the source document, owning collection or Formulation, and original path.
Preserve collection boundaries for sibling-code checks; flattening must not make
owner-local codes globally unique. Use RF-004's schema-directed traversal where
possible, with only the Formulation-specific projection needed by these callers.

Reuse the collection for scope construction and validation. In particular, remove
the nested `collect()` in
`specification/_validation.py`,
which currently collects expressions and Constraints again after Formulation
validation has already done so. Replace its rebuilt expression lookup and repeated
objective-domain inference with RF-003's analysis result.

The internal coordinator result retains the located declarations, Scope and
ExpressionAnalysis directly. Do not introduce a parallel FormulationAnalysis
wrapper around the same three objects. Keep results local to one prepared
composition, read-only for consumers and uncached across revisions.

#### Source diagnostics

Pass original locations into Binding, Value and predicate checks. Remove the
exception handler that recognizes `/constraints/`, parses a flattened position
and reconstructs the owning Formulation path. RF-003's expression analyzer must
consume the same locations. Use the existing structured diagnostic mechanism,
including document identity when available, rather than adding an error layer.

Read-only probes on 2026-10-06 confirmed that an invalid Binding reports an empty
path, while a missing predicate in Specification additions reports
`/additional_formulations/0/constraints/0/predicate`. Replace that temporary-envelope
location with the originating document and path. Preserve contributor provenance
through composition so two documents with `/formulations/0` remain distinguishable.

#### Collection input contract

Normalize iterable inputs once and reuse the materialized sequence. Currently,
`validate_formulations()` converts `additional_formulations` to a list only for
ownership checking, then reuses the original input. A one-shot iterator is empty
for later semantic checks. A probe with the same invalid Binding was rejected
when additions were a list but accepted when additions were an iterator. The
production callers inspected use lists; this is a helper-contract defect, not
evidence that those caller paths currently skip validation.

Apply the same rule to `validate_formulation_names()`, which also makes multiple
passes. Accept iterable input and normalize it to one tuple at the entry boundary;
reuse an existing tuple. Type and document that contract, and test one-shot
iterators. Do not omit checks because an iterator has already been consumed.

### Behaviour to preserve and exclusions

Preserve the rules in [`schema/formulation.yaml`](../schema/formulation.yaml):

- Containment defines ownership and local naming, not private visibility or
  execution order. UUID references can cross sibling Formulations.
- Containment is finite and acyclic. Mathematical dependencies are not required
  to form a directed acyclic graph.
- Bindings are optional interface names, not exhaustive expression dependencies.
  Binding targets are Values; Movement targets remain valid for expression
  references where permitted, not for whole-Value Bindings.
- Value keys, Binding names and Constraint codes belong to separate collections.
  Model and Specification root Formulation codes have separate name scopes, while
  declaration identities remain unique across the composed scope.
- Descendant Constraints are imposed with their containing Formulation. An
  Expression does not assert itself merely because it is present.
- Recorded local Value content does not imply a fixed assignment. Solve roles
  belong to the Specification.
- Empty Formulations and Formulations containing only children remain valid.
  Preserve non-mutation and collection-order-independent reference resolution.

Do not change persistent schemas, authoring builders, numerical execution or
independent acceptance. Do not cache validation across revisions or convert all
dictionary-based validators to generated records as an incidental cleanup.
Changes to query-domain inference remain explicit behaviour changes under RF-003.

### Dependencies, deletion targets and implementation order

RF-003 owns scope and expression analysis; RF-004 owns generic indexing and shared
reference checks; this item owns Formulation collection, local rules and their
orchestration. Agree their result and location interfaces together. Use RF-002's
canonical choices where relevant. Apply shared caller edits once.

Before implementation, record these deletion targets and the implementation-size
baseline across all affected modules and callers:

- The old `model/_formulation.py` and superseded collection code.
- The duplicate Specification Formulation collector, rebuilt expression lookup
  and repeated objective-domain inference.
- Flattened Constraint error-path reconstruction.
- Split domain Value gathering and equivalent repeated ownership checks, where
  the shared prepared scope demonstrably covers the same declarations.
- General Characteristics and Value checks in the Formulation orchestrator,
  replaced by one domain implementation rather than copied to another layer.

First agree locations and scope inputs, then extract shared domain checks and
collect declarations. Migrate expression analysis and resolved orchestration
together, retain local Specification checks, and finally remove old paths and
duplicate work. Do not remove repeated checks until their prerequisite, scope
and diagnostic contracts are accounted for. Target a net reduction across
RF-003, RF-004 and RF-005; explain any necessary growth under the overall strategy.

### Implementation details to settle in W1

- Finalize the located collection fields in the existing internal result; retain
  Scope and ExpressionAnalysis directly without another wrapper.
- Select the domain owners for Characteristics and Value validation jointly
  with RF-003, including the smallest typed/encoded boundary needed.
- Implement contributor UUID plus original pointer attribution through
  Composition and every semantic consumer.
- Normalize iterable input once to a tuple, including one-shot iterators.

### Verification and completion criteria

Baseline observed on 2026-10-06: `tests/test_validation_composition.py` returned
24 passes. The diagnostic and iterator probes above were separate from that
suite. Re-establish the baseline before implementation; this is not evidence of
a full regression pass.

Add focused regression cases for list/iterator handling, precise Binding and
Constraint locations, and source identity across composed contributors. Exercise
the local naming helper on partial Specifications with unresolved external
references, then check complete resolution separately. Verify cross-sibling
references, separate owner-local names, duplicate identities, containment cycles,
Relationship/local Values, Value-only Bindings and empty Formulations.

Run `tests/test_validation_composition.py`, `schema/checks/formulations.py`, the
expression checks and affected Model, Specification and composition suites.
Check that objective and predicate consumers agree when using one shared analysis.
Run fresh-process public imports and installed-package checks, then the combined
checks in [Verification](VERIFICATION.md). Check active imports and current guides
for retired paths while preserving historical documentation.

Completion requires a smaller, cohesive Formulation validator, preserved local
and resolved boundaries, one reusable located collection and expression analysis,
correct source diagnostics, an explicit collection input contract, and removal of
the listed duplicate work. All required checks must pass and current guides must
describe the new ownership. Record removed code and final size comparisons; a
package move alone does not satisfy this intent.

### Implementation record

Implemented in the coordinated working-tree pass. `model/formulation/{traversal,preparation,validation}.py` separates located declaration discovery, Scope preparation and rule checks. `model/scope.py` owns shared mathematical lookup and recorded scalar access.

The old mixed Formulation helper and repeated recursive walks are removed; failures retain original document/pointer locations. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-006 Consolidate validation, compose domain checks and reuse prepared results

### Intent and scope

Keep `model/validation.py` as the public Model validation entry point. Simplify
input preparation and reuse the semantic checks, indexes and scope analysis
needed by Model construction, Specification validation and execution preparation.
Extend the same discipline to Run validation where equivalent work is repeated
within one operation. Keep `UnitSystem` and its name unchanged.

Remove `model/_validation.py` as a separate Model-validation layer. Distribute its
domain rules to existing owners and consolidate orchestration in
`model/validation.py`. Move the shared recorded-unit operation there too, then
remove `model/_unit_validation.py`. Retain the operations and their contracts;
do not combine both old files into one long function.

The target is fewer conversions, repeated checks and discarded results. Use small
functions and the existing record, Composition, Scope and Prepared boundaries.
Do not add a validator hierarchy, universal pipeline framework or a second
validation context alongside the results defined by RF-003 through RF-005.

### Observed duplication and baseline evidence

The following traces were made on 2026-10-06 before implementation. Counts refer
to function calls in representative inputs, not timing or a whole-suite profile.

| Entry path | Observed work |
| --- | --- |
| `model.validation.validate()` with a minimal valid raw mapping | Three Model schema checks |
| The same entry point with an existing generated Model record or Model facade | No additional Model schema checks |
| Validation of an existing forward-fixture Composition | Two calls to `compose_specification()`, four Specification schema checks, two Model schema checks and one Model resolver call |
| Execution preparation of that existing Composition | The same repeated composition/schema work and two Model resolver calls; four Quantity schema checks also occurred |

For the raw Model path, [`checked()`](../src/rangekeeper/_validation.py) validates
the mapping, constructs a generated record that validates again, then exports a
mapping. [`model.validation.validate()`](../src/rangekeeper/model/validation.py)
constructs another Model record from that mapping, causing the third schema check.
Both construction/export round trips are visible in the source.

The Model constructor builds an index and calls private `_validate()`. The lower
`validate_model()` builds mathematical scope and returns it, but this wrapper
discards that result. Model and combined-investigation scopes have different
contents; two scope builds are not automatically redundant. Identify reusable
declarations and analysis while preserving that distinction.

[`specification.validation.validate()`](../src/rangekeeper/specification/validation.py)
receives a Composition but exports its contributors and routes them through the
raw-catalogue path. That path composes to find the Model pin, then the lower
validator composes again. [`execution.prepare()`](../src/rangekeeper/execution/preparation.py)
calls this validator, discards its resolved Model and analysis, and loads the Model
again before collecting declarations.

The focused Model, Specification and validation-composition suites passed in the
same review: 65 tests passed. This is not a full regression result. Re-establish
these baselines before implementation. Additional Quantity checks may represent
new normalized values and must not be removed solely to lower a call count.

A further review on 2026-10-07 found that `model/_validation.py` contains 221
lines spanning temporary document adaptation, Definitions, System, provenance,
Formulations and revision history. `model_documents()` manually relocates Functions
and System collections and removes Claim content to prepare generic identity
checks. A separate recursive `ids()` walk then reconstructs identities. The typed
index already distinguishes schema declarations from opaque content.

The same review reran the Model, Specification and validation-composition suites:
65 tests passed. A separate focused selection covering unit dimensions, conversion,
Model recorded units and Specification-local recorded units returned eight passes.
These are focused baselines, not full regression evidence.

### Consolidated ownership and rule composition

Use existing domain modules and direct functions:

```text
model/
  validation.py
    validate(...)                 public Model validation
    check_model(...)              internal semantic orchestration
    recorded_unit_issues(...)      shared Model/Specification unit checks
  definitions.py
    check_definitions(...)        catalogue names and Taxonomy rules
  system.py
    check_system(...)             classification, endpoints and membership
  provenance.py
    check_provenance(...)         Sources, Claims, Facts and support
  formulation/validation.py       RF-005: local and resolved mathematics
  expression/                     RF-003: expression analysis
  scope.py                        RF-003/RF-009: prepared declaration access
  _validation.py                  remove after migrating callers
  _unit_validation.py             remove after migrating both callers
```

The names above identify responsibilities; finalize signatures with the prepared
results from RF-003 through RF-005. Keep checks together unless reuse or a clear
dependency boundary requires another module. Each check consumes prepared records,
narrow lookups and original locations. It must not construct a Model, recursively
call public validation or create its own complete catalogue. Keep imports directed
from orchestration to domain checks; domain checks must not import orchestration.
Do not introduce validator classes, a stage registry or a universal pipeline.

Retire `model_documents()` and its two temporary dictionary envelopes. Build the
mathematical scope from canonical prepared declarations, and use RF-004's index
for declaration identities and ownership. Migrate its Specification and Run
callers, including Run diagnostic-target identity checks. Opaque Claim content
must remain excluded by schema-directed traversal, not by manual removal of a
particular field before scanning arbitrary dictionary keys. Remove the nested
`ids()` collector once the prepared index covers the required identity set.

Use RF-004 for equivalent existence and target-type checks, then apply each
domain's additional restrictions. Preserve Taxonomy-local parent membership,
one root and acyclic parents; the combined Entity/Assembly code namespace;
Relationship endpoint eligibility; Assembly membership uniqueness, endpoint
closure and containment acyclicity; required support for sourced/derived Claims;
Claim dependency acyclicity; eligible and unique Fact targets; and selected Claims
belonging to the Fact's support set. Keep Movement Claim checks and scenario
realization checks at their applicable prerequisites. These restrictions are not
made redundant by a generic reference check.

For shared Entity/Assembly code checks, pass located records to the uniqueness
operation. Remove the catch/parse/rethrow block that extracts a combined ordinal
from an error path and reconstructs `/system/entities/...` or
`/system/assemblies/...`. Use the same original-location mechanism as RF-005 to
improve Taxonomy, Relationship, membership and Claim diagnostics. Preserve shared
name scopes without flattening away source locations.

Keep optional revision-history checking as an explicit operation after metadata
and declaration identities are available. Preserve absent-history handling,
self-predecessor rejection, current-content restrictions, duplicate supplied
history identities and history-cycle checks. Compare Model and Specification
history contracts before sharing any further logic; similar loops do not establish
equivalent rules.

### Model validation flow

Retain the three responsibilities currently coordinated by `model/validation.py`:
prepare the input, check Model semantics and optional history, and check recorded
units against Measures. Make their dependencies explicit:

```text
Prepare structurally valid Model and supplied history records
  -> establish ownership and prepare or reuse declaration lookup
  -> check Definitions, System and provenance prerequisites
  -> prepare mathematical scope and check Formulations/expressions
  -> check recorded units
  -> return the report and reusable internal analysis
```

This is a dependency outline, not a requirement to defer all scope lookup until
after provenance checks. Supply declaration lookup when a rule requires it; run
scenario checks after their referenced declarations are ready. Revision-history
checks need metadata and identities. Skip dependent checks on failed prerequisites.
The public `validate()` still returns `ValidationReport`.

Use one structurally validated record for a raw input. Rework the existing shared
preparation helper rather than adding a parallel conversion path. Generated
record construction can provide structural validation; retain its resulting
record and contextualize its diagnostics without constructing it again. Do not
add a public unchecked constructor or bypass validation by assigning `_data`.

For an existing generated record, verify the expected record kind and reuse the
immutable record. For a Model facade, reuse its record and declaration index.
When lower checks still require mappings, produce a detached representation once
for those checks and pass it through. Do not turn a record into a mapping merely
to reconstruct the same record at the next layer. RF-002's enum decoding must
remain consistent across all three input forms.

Prepare the supplied history in one place. Keep history optional and perform no
implicit predecessor loading. Report structural issues in supplied history even
when the Model structure is invalid, as the current implementation does. Skip
dependent semantic and unit checks after failed prerequisites. Preserve history
paths such as `/history/0`, document identities and independent structural issues.

The Model constructor and explicit validation must use the same semantic work.
The constructor receives or retains the resulting index and publishes `_record`,
`_index` and `_units` only after success. Explicit validation returns the report.
Use a small internal return contract for the report and any reusable preparation
results; settle its exact shape with RF-003/RF-004 rather than introducing another
stateful service.

### Construction and validation contracts

| Boundary | Required behaviour |
| --- | --- |
| Raw input | Validate structure before record-dependent checks; retain the prepared record |
| Existing generated record | Reuse structural validity after checking its kind; still run applicable semantic checks |
| Existing Model | Reuse its immutable declarations/index; apply the requested history and unit context |
| Model construction | Preserve documented argument, unsupported-version and duplicate-identity exceptions; publish no partial object |
| Explicit `validate()` | Return structured findings for invalid document content, preserving source paths and prerequisite gating |
| Unit checks | Run after reference checks so a missing Measure is reported as a reference problem |
| Independent structural errors | Retain useful findings for malformed Model and history inputs in the same report |

Sharing the underlying checks does not require construction and inspection to
have identical failure interfaces. Map existing exception and report behaviour
before changing orchestration; preserve `IdentityConflictError` and
`UnsupportedVersionError` at the documented constructor boundaries. Coordinate
intentional reference-diagnostic changes with RF-004. Do not broaden exception
catching to hide programming errors.

Move `recorded_unit_issues()` into
`model/validation.py` as a shared operation for Model and composed Specification
validation. Update both callers and remove the old module without a forwarding
alias. Its narrow Measure lookup callback remains useful: do not replace it with
a Model, resolver or storage dependency.

Keep `units.py` responsible for unit parsing, compatibility and conversion. Add a
small `UnitSystem.validate_units(text)` operation to replace
`compatible(text, text)` when only unit-string validity is needed; parse once and
retain the private lazy Pint registry and existing UnitError contract. Do not move
document traversal, Value/Measure relationships or diagnostics into `units.py` or
the domain-independent `_validation.py` infrastructure.

Reuse existing located record traversal for unit checks where this removes a
complete repeated walk without a new collection framework. Preserve schema-directed
traversal and exclusion of opaque Claim content. Locate unit errors at the actual
`/units`, `/quantity/units` or `/flow/units` field where appropriate, retaining
source-document identity. Catch only unit failures as unit diagnostics; missing
Measures must fail at the reference stage, and programming errors must not be
silently recategorized.

These checks validate recorded units, not expression result units or automatic
conversion. Preserve the caller's explicit UnitSystem, currency restrictions and
current default behaviour. Apart from explicit single-string validation, this
item does not change the UnitSystem interface or unit-policy selection.

### Composition and execution preparation

RF-022 owns the Specification package consolidation, single Composition result,
direct local checks and graph preparation. Apply this section through those same
operations; do not introduce a separate preparation layer for each intent.

Give existing typed compositions a direct semantic validation path. Consume their
effective requirements and contributor snapshots without recomposing them from
exported data. The raw catalogue entry point must still prepare untrusted records,
check catalogue key/identity agreement and compose each required investigation.
Both paths then call the same semantic stages rather than implementing parallel
rules. Retain raw catalogue APIs used by conformance checks and synthetic Runs.

Resolve the pinned Model once during one validation/preparation operation. Check
its document kind and exact revision, then pass that same object to all dependent
stages. Expose the necessary results through an internal operation consumed by
the public report-returning validator and execution preparation. Public
`validate()` need not change its return type to enable this reuse.

Reuse the declaration scope, located records and expression analysis supplied by
RF-003 through RF-005. Let execution add its own supported-capability checks,
normalized assignments and imposed assertions to the existing Prepared result.
It must not repeat complete validation just to obtain information already checked.
Keep preparation deadline checkpoints and capability rejection intact.

Preserve these distinctions:

- A valid saved partial Specification may still lack a Model or complete roles.
- Complete investigation validity does not imply support by a particular solver.
- Only imposed mathematics enters execution preparation; unused reporting queries
  remain passive.
- Recorded values and estimates do not become fixed assignments implicitly.
- Model-only scope differs from a combined investigation scope. Preserve
  contributor ownership, source paths and collisions across the combined scope.
- Batch leaves retain separate scopes, pins and failure outcomes.

Execution planning and policy evaluation are part of the same preparation audit.
Retain the exact Models loaded and checked in `execution/planning.py`; pass them
through validation and `execution/preparation.py` rather than loading again.
Thread the caller's UnitSystem into the internal policy path and the standalone
public evaluator. The current implicit `default_units` in policy evaluation must
not override a supplied context. Test both fresh public operations and internal
reuse, including restricted supported-currency sets and failed preparation.

Retain contributor UUID plus original pointer through Composition and located
declarations. Use the common preparation table above for result fields and
structural-error gating; do not create a separate context for each consumer.

### Run validation and deliberate rechecking

Apply the shared preparation improvements to `run.validation.validate_records()`
and resolver-backed validation. Reuse exact documents and equivalent local results
within the current validation call. RF-019 owns the detailed Run package redesign.
Retain separate report, tree and output-conformance responsibilities: they
establish different facts, but do not require the current Tree/Publication classes
or file split. A failed or not-assessed Run can validly
record an invalid investigation when it has the required evidence; simplifying
the pipeline must not force every historical Run through successful-execution
requirements.

Reuse is limited to the same immutable document content, revision, scope, units,
history and applicable settings. Do not cache by UUID alone before conflicting
content has been rejected. A later independent operation must establish its own
resolver context. Do not add a global validated flag or cross-operation semantic
cache. New scopes and changed validation settings require their relevant checks.

Keep explicit trust-boundary checks. In particular,
[`io._document.snapshot()`](../src/rangekeeper/io/_document.py) revalidates detached
content before IO, and numerical acceptance reconstructs and checks candidate
output independently. These checks must not be removed as duplicate preparation.
Stored input, imported data and proposed output are distinct validation events.

Independent numerical acceptance must continue to evaluate original requirements,
not trust compiled rows, backend flags or a previous semantic-validation result.
Generic preparation and Model/Specification validation must not evaluate quantities,
execute policies, solve equations, publish data or perform IO beyond an explicitly
supplied resolver. Run evidence validation retains the existing targeted checks
of recorded policy observations and first-matching-rule outcomes through RF-018
and RF-008. That independent evidence check does not execute a new investigation
or replace numerical acceptance; RF-019 must not remove it under a blanket ban
on predicate evaluation.

Workflow declaration and ingestion validators check their own input formats and
evidence relationships. Audit their use of the shared helpers when those change,
but do not merge their rules into Model validation simply because both use the
word validation. RF-023 owns the broader workflow/Evidence redesign and reuses
matching preparation without changing these domain validation boundaries.

### Dependencies and deletion targets

| Item | Integration with RF-006 |
| --- | --- |
| RF-001 | Use the shared policy availability rule without making generic preparation execute policies |
| RF-002 | Keep typed enum properties and wire strings consistent through the single preparation path |
| RF-003 | Reuse Scope and expression analysis within the correct semantic context |
| RF-004 | Reuse RecordIndex, reference rules and structured diagnostic boundaries |
| RF-005 | Consume located Formulation declarations and resolved analysis without rebuilding collections |
| RF-009 | Reuse resolved target metadata within one scope; read quantities from the correct input, output or candidate revision |
| RF-022 | Use one Composition and shared graph preparation; migrate Specification methods and local checks without a second validation pipeline |

Remove the redundant `checked()` validate/construct/export sequence, the additional
raw-Model reconstruction, duplicate history-preparation branches, repeated
composition inside validation, and the second Model load inside preparation.
Remove superseded declaration collection and analysis only when the shared result
contains the same scope and source information. Consolidate exception-to-diagnostic
mapping where the contracts match.

Also remove `model_documents()`, its temporary mathematical/identity envelopes,
the recursive Model identity collector, reconstructed Entity/Assembly diagnostic
paths, and the retired `model/_validation.py` and `model/_unit_validation.py`
modules. Migrate imports in Model validation, Specification validation, Run tree
and publication checks, policy evaluation, and any direct schema-check callers.
Do not rerun complete Model validation only to obtain a scope already available
under the same checked context. Preserve candidate/output validation as distinct
events and keep domain restrictions when removing equivalent reference checks.

Update existing entry points and private helpers; do not layer a new orchestration
system over the old one. The expected result is a net reduction in handwritten
runtime code. Record the affected size baseline, exact deleted paths/branches and
final comparison under the overall reduction strategy.

### Implementation sequence

1. Inventory entry points, accepted representations, outputs, exception contracts,
   trust boundaries and current preparation counts. Include constructor and raw
   catalogue paths, not only the public `validate()` functions.
2. Agree minimal reusable outputs with RF-003 through RF-005. Define which facts
   each stage guarantees and which context changes invalidate reuse.
3. Rework shared structural preparation and Model orchestration. Consolidate
   history preparation, move domain checks to their existing owners and remove
   temporary envelopes. Move recorded-unit checks into `model/validation.py` and
   preserve prerequisite ordering, import boundaries and constructor behaviour.
4. Make typed and raw Specification paths converge on the same semantic stages.
   Retain compositions and exact resolved Model snapshots for execution preparation.
5. Apply equivalent reuse in Run validation; audit shared-helper consumers in IO,
   schema checks, workflow and adapters. Preserve deliberate boundary rechecks.
6. Remove superseded conversions, collectors and wrappers. Update current guides,
   run focused and combined checks, and compare counts and code size to baseline.

### Verification and completion criteria

| Area | Required evidence |
| --- | --- |
| Raw Model preparation | One root structural check for the same successful input boundary; no validate/construct/export/reconstruct cycle |
| Equivalent input forms | Raw mapping, generated record and Model facade produce equivalent applicable semantic findings under the same context |
| Construction | Invalid content never publishes a Model; documented version, identity and argument exceptions remain intact |
| History and gating | Malformed history is reported even with malformed Model structure; semantic and unit stages do not run after failed prerequisites |
| Unit validation | Missing Measures fail before unit lookup; incompatible units produce `semantic.units`; explicit currency restrictions still apply |
| Domain composition | Taxonomy, System, provenance and history restrictions remain active after their rules move; invalid prerequisites do not trigger dependent checks |
| Source locations | Combined Entity/Assembly name checks and recorded-unit failures retain original document and field paths without ordinal reconstruction |
| Existing Composition | Validation does not recompose the already prepared view; contributor identity, ownership and source diagnostics remain correct |
| Raw catalogue | Structural, catalogue identity, composition-cycle and complete-reference errors still fail with correct context |
| Execution preparation | One load of the pinned Model within the preparation operation; the exact checked instance reaches dependent stages |
| Scope reuse | Analysis is reused only for matching immutable inputs and context; different leaves, units, history and revisions remain independent |
| Run records | Failed/not-assessed Runs retain valid evidence paths; local report, tree and publication checks all remain active |
| Trust boundaries | IO snapshot and candidate-output checks still run; acceptance remains independent of compiler and solver claims |

Repeat the representative traces to demonstrate the intended reduction. Use
focused tests or spies for the preparation contracts; do not freeze incidental
private call order or assert one global check count across distinct trust
boundaries. Check both valid and invalid inputs, including a wrong generated
record type and conflicting content under one revision ID.

Extend `test_domain_model.py`, `test_domain_specification.py`,
`test_domain_run.py`, `test_domain_io.py` and `test_validation_composition.py`,
plus affected execution tests. Check declaration/reference error paths, failed
prerequisite behaviour, deferred references, contributor paths, batch isolation,
missing and incompatible units, opaque content, and non-mutation of inputs.
Retain useful numerical assertions and conformance fixtures. Run typing,
installed-package and relevant schema checks, then the combined checks in
[Verification](VERIFICATION.md).

Cover opaque Claim content containing apparent IDs and units, empty and cyclic
Taxonomies, out-of-Taxonomy parents, shared Entity/Assembly codes, invalid Assembly
endpoints and membership, Claim support/cycles, Fact eligibility/reconciliation,
and optional history. Exercise Model and Specification unit consumers after the
move, including invalid unit syntax, Flow/Measure mismatches and compatible units
with different scales. Check both import orders in fresh processes and active
imports for the retired modules. Preserve historical documentation of old paths.

RF-006 is complete when Model validation remains a small public coordinator,
raw input is prepared once, construction and inspection share semantic work,
history preparation is unified, and compositions/resolved inputs/analysis reach
their consumers without the identified repeated work. Domain checks must have
clear owners, recorded-unit checking must remain shared, and both retired Model
validation modules and temporary envelopes must be removed. Required failure interfaces,
source diagnostics, unit behaviour and independent acceptance must be preserved.
Document any unresolved gap; passing call-count tests alone is not acceptance.
Record deletion and size evidence and update current architecture and validation
guides to describe the final flow.

### Implementation record

Implemented in the coordinated working-tree pass. Model, Composition and Run validation now coordinate bounded domain checks through operation-local prepared results. Execution reuses the exact resolved Model and Composition from planning.

Independent store snapshots, candidate acceptance and stored-outcome checks still revalidate at their own boundaries. No trusted flag or persistent validation cache was added.

The final Model owners are definitions.py, system.py and provenance.py, coordinated by model/validation.py. Both old Model validation modules, model_documents, its identity envelope and generic identity collector are removed. Raw Model validation constructs one checked record; existing compositions are not recomposed, and validation retains the exact resolved Model after later semantic failure. Changed UnitSystem contexts recheck recorded units; source paths survive combined mathematical and unit checks.

Size exception for the coordinated RF-003/004/005/006/009/019/020/022 package: 47 to 44 handwritten runtime files, 4,770 to 5,456 physical lines, 192 to 216 functions and 30 to 32 classes. This counts shared helpers and callers once and excludes the separately owned policy, availability, predicate, scenario and numerical-evaluation moves on both sides. Fifteen retired modules are replaced by twelve files. The net 686-line growth is not a reduction: explicit unknown-domain handling, immutable analysis/path maps, contributor source attribution, prepared failure results, UUID scalar access, strict comparison and child diagnostic context add responsibilities; final signature formatting also expands physical lines. The removed duplicate preparation paths and indexed diff reuse have focused call-count checks. No timing improvement is claimed.
See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-007 Use py-moneyed directly for the currency catalogue

### Problem and decision

[`units.py`](../src/rangekeeper/units.py) reads `_currencies.json` at import time
and assumes its `codes` field is valid. The file declares a py-moneyed 3.0 source,
but the loader ignores its source and version fields. `UnitSystem.implementation`
duplicates that provenance as a hard-coded string. The repository tools inspected
do not provide a reproducible catalogue regeneration process.

Use py-moneyed's documented
[`list_all_currencies()` API](https://py-moneyed.readthedocs.io/en/latest/usage.html#list-all-currencies)
directly. Remove the local JSON snapshot and loader. This supersedes the earlier
suggestion to generate a Python catalogue: no local dataset generator, catalogue
service or duplicate currency enum is needed for the present requirement.

A read-only comparison on 2026-10-06 found an exact match between the bundled
308-code snapshot and installed py-moneyed 3.0. Installed Babel 2.17.0 instead
returned 307 codes: it added `XCG` and `ZWG` and omitted `IMP`, `TVD` and `ZWN`
relative to the snapshot. These are comparisons of the installed catalogues, not
claims about which currencies are currently in circulation. Use py-moneyed 3.0
initially to preserve the existing supported set, including historical codes.

### Intended implementation and dependency

Use the library's Currency objects only to obtain their code strings:

```python
from moneyed import list_all_currencies

_CURRENCIES = tuple(currency.code for currency in list_all_currencies())
```

Add `py-moneyed==3.0` as a direct core dependency in
[`src/pyproject.toml`](../src/pyproject.toml) and update the relevant lock or
environment declarations. Its current optional legacy declaration does not supply
a core dependency. Reconcile duplicate dependency declarations without removing
packages still required by the legacy acceptance boundary. Import `moneyed`
directly; do not route core code through `rangekeeper.legacy`.

The accepted tradeoff is an additional core dependency, including its Babel
dependency, in exchange for removing a locally maintained dataset and its loading
and packaging code. Verify the installed dependency closure and supported Python
versions. Treat later catalogue upgrades as explicit dependency changes with a
code-set comparison; do not silently broaden the initial pin.

Keep Pint responsible for dimensional units and expressions such as `AUD/year`.
Retain the lazy private Pint registry. This item does not adopt Money objects,
Decimal arithmetic, currency formatting, exchange rates or conversion rules.

### Provenance, fingerprints and affected code

Derive the catalogue source version from installed package metadata rather than
repeating a version literal in runtime code. Retain the existing unit-algorithm
identity separately from the catalogue dependency identity.

[`workflow/implementation.py`](../src/rangekeeper/workflow/implementation.py)
currently hashes `_currencies.json` into its implementation manifest. Replace
that resource dependency with an explicit catalogue fingerprint that includes
the installed py-moneyed version and a deterministic digest of the supported
codes. Use the existing fingerprint machinery; do not add a parallel manifest
framework. A changed catalogue must still change the applicable implementation
fingerprint even when Rangekeeper's Python source is unchanged. Do not rewrite
historical stored manifests or pretend the new implementation has the old hash.

Remove `_currencies.json` from package-data declarations and replace its presence
assertion in [`tools/schema/verify_install.py`](../tools/schema/verify_install.py)
with an installed-package check of the library-backed catalogue and unit behaviour.
Update [Domain core](DOMAIN_CORE.md), relevant dependency guidance and any active
catalogue references to describe the new ownership. Preserve historical records.

Coordinate with RF-002 by keeping the external currency catalogue out of the
generated domain-enum inventory. Currency selection continues to use code strings;
compound units remain strings. Coordinate with RF-006 so its prepared validation
paths preserve the same explicit currency restrictions.

### Behaviour to preserve and exclusions

- Preserve all 308 initially supported codes, including historical codes.
- Keep deterministic currency ordering and immutable `UnitSystem` configuration.
- Allow explicit selections to restrict the catalogue; reject unsupported codes.
- Keep each currency as a separate dimension. AUD and USD remain incompatible,
  and this change introduces no exchange-rate inference.
- Preserve compound-unit parsing, physical-unit conversion and the independent
  dwelling dimension.
- Keep operation free of network access. Catalogue discovery uses the installed
  package, with no live ISO lookup or automatic data update.
- Preserve the existing lazy Pint import and absence of legacy-module imports
  from the core domain path.

Do not change persistent Quantity fields, document versions, solver behaviour or
financial calculations. Do not retain the JSON as a runtime fallback or replace
it with an equally maintained local Python list.

### Deletion targets and verification

Delete `_currencies.json`, its import-time JSON/resource loading, duplicate
runtime provenance literals, and obsolete package-data and fingerprint resource
handling. Report the dataset deletion separately from handwritten code reduction.
Record dependency growth as well as code reduction; do not count third-party
implementation as removed Rangekeeper code. No custom generator is planned.

Before deleting the snapshot, compare its full set against the pinned library and
record the result. Retain focused tests for common and historical codes, invalid
codes, restricted currency selections, deterministic ordering and immutable
configuration. Exercise AUD/USD incompatibility, compound units and physical-unit
conversion through `UnitSystem`, not just catalogue enumeration.

Test fingerprint stability for unchanged catalogue inputs and sensitivity to
changed version or code-set inputs without changing installed dependencies during
the test. Build and install the package with core dependencies only; verify that
unit operations work without the legacy extra or the deleted JSON resource. Check
fresh-process imports for the preserved Pint and legacy boundaries. Run affected
`test_domain_model.py`, workflow fingerprint and installed-package checks, then
the combined checks in [Verification](VERIFICATION.md).

### Completion criteria

- The pinned py-moneyed API supplies the catalogue with the original code set.
- Core dependency installation is sufficient; no legacy import is required.
- The local snapshot, loader and obsolete resource declarations are removed.
- Provenance uses the installed version and fingerprinting covers catalogue data.
- Currency restrictions, dimensions, compound units and lazy Pint behaviour pass
  their checks.
- Current guides and packaging checks describe the library-backed catalogue.
- Deletion, dependency and verification evidence is recorded.

### Implementation record

Implemented in the coordinated working-tree pass. `units.py` uses pinned `py-moneyed==3.0`; `_currencies.json` and its loader/package-data entry are removed. The active catalogue was checked against all 308 old codes before removal.

Pint remains lazy. Workflow, scenario and execution provenance name the catalogue dependency; installed core imports do not load numerical packages. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-008 Share numerical expression evaluation and give policy predicates a clear owner

### Problem and decision

`model/_predicate.py` evaluates finite
policy expressions against explicitly supplied quantities. Its two callers are
[`policies/evaluation.py`](../src/rangekeeper/policies/evaluation.py), which selects
the first matching rule, and
`specification/_policy_validation.py`,
which checks recorded decisions against their observations and rule order. The
operation is required, and both callers should continue to share it.

The duplication is numerical evaluation in
[`execution/evaluator.py`](../src/rangekeeper/execution/evaluator.py). Both modules
implement quantity literals, reference lookup, negation, addition, subtraction,
multiplication, division, powers and unit handling. Maintaining these operations
twice risks different results or error handling for the same numerical tree.

Extract one pure numerical evaluator. Move policy Boolean evaluation to policies.
Keep comparison residuals, tolerances and acceptance diagnostics in execution.
This is a separate runtime-evaluation intent; RF-003 retains ownership of semantic
expression analysis.

| Operation | Owner and contract |
| --- | --- |
| Semantic analysis | RF-003 checks references, domains and expression meaning within a supplied scope; it does not calculate current truth |
| Numerical evaluation | A shared pure operation calculates a Quantity from an expression and supplied quantities |
| Policy truth evaluation | Policies evaluate exact comparisons and Boolean logic, including short-circuit behaviour |
| Numerical acceptance | Execution evaluates original comparison sides, calculates residuals and applies its documented tolerances while retaining each diagnostic |

### Intended structure and composition

```text
src/rangekeeper/
  model/
    expression/
      __init__.py             RF-003: retain record exports only
      evaluation.py          pure numerical evaluation and arithmetic
      validation.py          RF-003: semantic analysis; no runtime evaluation
    _predicate.py            remove after migrating both policy callers
  policies/
    predicate.py             pure policy truth evaluation
    evaluation.py            observations, ordered rules and decisions
    validation.py            RF-018: check evidence, then reuse policy truth evaluation
    __init__.py              RF-001: isolate pure helpers from eager runtime imports
  execution/
    evaluator.py             comparison traversal and execution error adaptation
    acceptance.py            residuals, tolerances and acceptance diagnostics
  specification/
    _policy_validation.py    remove after migrating checks to policies
```

The module names describe the intended ownership. Finalize function names and
signatures with RF-003 before implementation. Use a typed mapping of reference
keys to Quantity records and an explicit UnitSystem in the shared evaluator.
RF-008 adds no UnitSystem changes beyond RF-006. Standalone policy calls retain
their default but accept the supplied unit context; execution must pass its
UnitSystem through instead of silently using the default.

The numerical evaluator returns a Quantity. It accepts only the currently
supported numerical tree forms. Policy evaluation handles Boolean literals,
logical negation, conjunction, disjunction and comparisons; numerical operands
delegate to the shared evaluator. Preserve Boolean equality and inequality as
well as numerical comparisons. Require a Boolean result at the policy-condition
boundary; reject a bare numerical condition through the caller's error contract.

Execution comparison traversal uses the shared evaluator for numerical operands.
Retain traversal order and its supported predicate subset. Acceptance still
calculates signed residuals in the left operand's units and records all required
constraint diagnostics, even after an earlier constraint fails. Policy logical
short-circuiting must not suppress execution diagnostics.

Keep the shared evaluator independent of Model construction, stores, resolvers,
policy orchestration, execution errors, compilers and solver backends. Keep the
policy predicate module similarly free of orchestration imports. Do not export
evaluation eagerly from the expression package initializer. Use ordinary
functions; do not add a visitor hierarchy, evaluation service, plugin registry,
global cache or mode flag that combines policy and solver semantics.

### Behaviour and error contracts to preserve

- Read only the supplied quantity mapping. A missing reference must not fall back
  to Model amounts, load history or fetch additional observations. Reconcile the
  existing reference-key helpers through RF-009 and preserve Value and Movement
  identity. The shared evaluator must not call Scope or recorded-quantity readers.
- Keep policy observation dates, availability and evidence checks at their
  existing boundaries. The evaluator receives values after those checks; it does
  not decide which observations a policy may access.
- Preserve policy rule order, first-match selection, no-match handling, actions,
  termination and recorded-decision verification. Both policy callers must use
  the same truth evaluator.
- Preserve exact policy comparisons after unit conversion. Do not introduce
  solver tolerances into policy equality, inequalities or rule selection.
- Preserve Boolean type checks and short-circuit evaluation: an unused branch
  must not trigger a missing-reference or arithmetic error.
- Preserve addition, subtraction and comparison conversion to left-side units;
  product and quotient units; and dimensionless power exponents. Cover negative,
  zero and fractional powers without accepting complex or non-finite results.
- Preserve execution's supported comparison subset, conjunction order, exact
  Boolean acceptance and absolute/relative tolerance formula. Do not broaden
  backend capabilities as a side effect of a more capable policy evaluator.
- Preserve caller-facing errors, including PolicyCapabilityError, NumericalError
  and UnsupportedProblem where they currently apply. The shared evaluator must
  not import these higher-level packages. Define a minimal neutral failure
  contract and translate only at the existing caller boundaries.
- Keep numerical acceptance independent of compiled rows and solver success
  flags. It must continue to evaluate the original expression trees against the
  supplied candidate quantities.
- Preserve input immutability. This intent does not add Function calls, queries,
  collection evaluation, expression solving or new persistent schema fields.

Before extraction, record how each caller handles missing references, invalid
units, unsupported operators, division by zero, overflow and complex powers.
The existing evaluators use different exception translation and finite-result
checks. Do not assume that identical operator names imply identical error paths.
Any required correction to observable behaviour must be documented explicitly
with its regression case; do not silently broaden exception handling.

RF-015 adds one bounded consumer requirement: strict rate predicates with only
fixed assigned/literal operands. Execution preparation and independent acceptance
must evaluate those normalized numerical sides and compare them exactly, without
tolerance or policy truth reuse. Keep the original assertions and reject strict
predicates with unknown dependencies. Do not expand the affine solver to strict
unknown bounds or approximate them with epsilon. Test invalid fixed rates before
solve and independent rejection during candidate acceptance. This addition is
separate from the behavior-preserving arithmetic extraction described above.

### Dependencies, deletion targets and implementation sequence

RF-003 supplies the expression package and keeps semantic analysis separate.
RF-001 supplies pure policy import isolation. RF-002 supplies canonical expression
kind and operator enums. RF-004 supplies the agreed reference identity contract;
the evaluator still receives a mapping, not a new declaration index. RF-006 must
retain its validation/execution boundary: explicit decision-evidence verification
can recompute policy truth, but generic Model or Specification preparation must
not start executing policies. RF-007 must preserve the units behaviour used here.

1. Record current results, errors, import dependencies and implementation size for
   both evaluators and their callers. Establish focused test baselines.
2. Agree the shared numerical input, output, reference-key and error contracts.
   Resolve package initialization with RF-001 and RF-003 before moving code.
3. Extract numerical evaluation once. Migrate execution comparison traversal and
   policy numerical operands to it, preserving each caller's error interface.
4. Move policy truth evaluation to `policies/predicate.py`. Update both decision
   production and recorded-decision validation to use it.
5. Delete `model/_predicate.py` and the duplicate numerical branches from execution
   and policy code. Remove obsolete imports and tests tied only to the old path.
   Do not leave forwarding modules or compatibility aliases.
6. Update the relevant architecture and policy guides, then run focused and
   combined verification. Record deletion and size evidence under the overall
   reduction strategy.

The target is a net reduction in handwritten implementation across all affected
modules and callers. A new shared module must replace both numerical
implementations. Keep execution's remaining comparison traversal only where it
serves acceptance; do not retain a redundant forwarding evaluator. Explain any
necessary size increase caused by error-contract preservation before implementation.

### Verification and completion criteria

Use small explicit fixtures with independently stated expected results. Testing
policy production against its own validation alone is insufficient because both
will share the same evaluator.

- Cover literals, supplied references, negation and every arithmetic operator,
  including mixed compatible units and dimensionless exponents.
- Cover incompatible units, missing references, Boolean/numerical type mismatch,
  unsupported expression forms, zero division, overflow and complex powers at
  both caller boundaries.
- Cover every policy comparison, Boolean equality, logical negation and both
  short-circuit operators. Use unused branches that would fail if evaluated.
- Verify first-match and no-match decisions, termination and rejection of forged
  recorded decisions. Preserve observation availability and evidence checks.
- Use a near-equality fixture to show exact policy equality differs deliberately
  from numerical acceptance within tolerance. Verify residual values, units,
  signs, tolerance thresholds and complete diagnostic order for conjunctions.
- Verify evaluation uses candidate quantities even when recorded Model quantities
  differ. Confirm that no fallback or resolver access occurs.
- Check fresh-process imports in both orders: Specification validation before
  policy runtime, and policy runtime before validation. Confirm pure helper and
  expression-record imports do not load policy orchestration, execution, compilers
  or optional solver dependencies.
- Run affected policy, Specification validation and numerical acceptance tests,
  then the applicable combined checks in [Verification](VERIFICATION.md). Record
  pre-existing failures separately and leave unresolved checks explicit.

RF-008 is complete when one numerical evaluator serves both consumers, policy
truth evaluation has its own clear owner, and the old Model module and duplicate
arithmetic are removed. Exact policy truth, numerical acceptance evidence, error
contracts and import boundaries must pass their checks. Record net size changes
and update current documentation before marking the intent complete.

### Implementation record

Implemented in the coordinated working-tree pass. `model/expression/evaluation.py` owns pure supplied-value arithmetic. `policies/predicate.py` owns exact truth and short-circuiting; execution evaluates original comparisons and retains independent acceptance.

Fixed strict predicates are checked before lowering and again without tolerance on the candidate. Unknown references are rejected before cancellation. Compiler/evaluator manifests include shared arithmetic and have sensitivity tests. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-009 Consolidate scoped target resolution and recorded scalar access

### Problem and decision

`model/_references.py` is a 45-line
adapter over encoded References and a prepared target index. Its four functions
extract a target UUID string, resolve the owning Value and optional Movement,
read declared numerical units, and obtain recorded scalar content. These rules
are active across Model, Specification, Run and policy code.

Equivalent scalar-unit and recorded-quantity rules occur in
`execution/symbols.py` and
[`policies/observation.py`](../src/rangekeeper/policies/observation.py). The main
differences are dictionary versus generated-record representation, scope and
caller-facing errors. Consolidate equivalent domain rules while preserving those
boundaries. Do not create a new reference service or `references` package.

### Intended ownership and composition

| Responsibility | Owner |
| --- | --- |
| Declaration lookup, record types and containment ownership | RF-004's RecordIndex and semantic reference checks |
| Resolve a Value/Movement target in the supplied mathematical scope | RF-003's Scope, extended by this intent |
| Scalar eligibility, declared units and recorded quantity extraction | One small domain implementation alongside scoped access |
| Backend token encoding and decoding | `execution/symbols.py`, where still needed |
| Observation availability and prior-decision access | Policies, coordinated with RF-001 |
| Expression evaluation using supplied quantities | RF-008; no Model or Scope access |
| Diagnostic context and exception translation | Existing validation and runtime caller boundaries |

Use this flow:

```text
Target UUID
  -> resolve in the explicit scope
  -> obtain the target and its owning Value
  -> check scalar eligibility when required
  -> read declared units or recorded quantity
```

Initially place cohesive scoped-access helpers with `model/scope.py`. Finalize
their names and representation with RF-003 and RF-006. The current Value/optional
Movement pair may suffice; introduce a named resolved-target result only if it
replaces enough positional handling to reduce complexity across callers. Do not
add another generic resolver protocol or duplicate target registry.

Expression validation may resolve any eligible Value or Movement without asking
for scalar content. Scalar-role checks admit measurement Values and individual
Movements, while rejecting whole Flow Values and property Values. These are
domain rules, not responsibilities of the generic record index. Expression-domain
unit inference is a separate operation and must not be merged merely because it
also has a function named `numerical_units`.

### Identity and representation simplification

Remove `reference_key()`, which only returns `reference["target"]`. Encoded
validators can access that field directly. Typed callers should use
`reference.target`; when a string token is required, use an explicit conversion at
that boundary. Remove calls such as `reference_key(target.to_data())` and temporary
`dict(target=identity)` values created only to recover or resolve the same identity.

Retain `execution.symbols.key()` and `reference()` only as useful backend token
encoding/decoding boundaries. Agree RF-008's supplied-quantity map key type and
migrate producers and consumers together. Avoid a helper accepting arbitrary
strings, UUIDs, dictionaries and records through implicit coercion. Keep an
explicit typed/encoded boundary without converting complete Models per lookup.

### Resolve once and share the scalar rules

`recorded_quantity()` currently resolves a measurement target, then calls
`numerical_units()`, which resolves it again. The execution path repeats Model
lookup through `read()`, `units_for()` and `owner()`. Resolve once and pass that
result to the relevant domain operations.

Replace duplicate unit and quantity extraction in execution and observation
construction with this shared implementation. Keep policy availability checks,
permitted observation sets and prior-decision precedence outside it. Do not make
policy code import execution merely to read a quantity. Reduce execution's symbol
module to backend-specific work; migrate generic owner/unit/content readers
rather than leaving forwarding wrappers without a distinct contract.

Share metadata only within the prepared scope that establishes it. Acceptance
must resolve and read the candidate Model's quantities independently of the input
Model. Run publication checks must read the selected output revision. A stable
Value or Movement UUID across revisions does not imply stable content. Do not
cache quantities globally or reuse an input reading as candidate evidence.

### Behaviour and errors to preserve

| Case | Required result |
| --- | --- |
| Target absent from the required scope | Resolution error |
| Target exists but has an invalid reference record type | Reference type error at the applicable boundary |
| Whole Flow or property requested as a scalar | Numerical eligibility error |
| Valid scalar with absent or null recorded content | `None`; retain unresolved state |
| Recorded magnitude is zero | Return a valid zero Quantity |
| Declared units for a measurement | Read its Measure's units |
| Recorded measurement Quantity | Preserve its actual magnitude and units; do not convert implicitly |
| Declared units or constructed Quantity for a Movement | Use its owning Flow's units |
| Recorded content exists | Do not infer an assignment, estimate or solve role |

Preserve no-IO, no-mutation and no-evaluation behaviour. Maintain missing versus
invalid versus unresolved distinctions; do not convert all failures to `None`.
Retain public direct Model lookup exceptions. Semantic checks should supply
document/path context through RF-004's structured diagnostics. Runtime callers
must retain their established capability and numerical errors. Inventory the
current error paths before extraction, especially policy handling of unsupported
or unresolved observations; translate narrowly at the existing boundary.

The shared scalar implementation must not load revisions, perform unit conversion,
calculate policy truth, inspect backend variables or depend on compiled rows.
Independent numerical acceptance remains independent even when basic record
reading is shared.

### Affected code, deletion targets and dependencies

Migrate `_references.py` callers in Model expression, scenario and availability
checks; Specification composition, validation and decision checking; Run tree and
publication validation; and policy observation/evaluation. Coordinate removal of
the old predicate caller with RF-008 and availability caller with RF-001. Inspect
execution preparation, publication and acceptance when migrating symbol helpers.

RF-003 owns combined mathematical scopes. RF-004 supplies index/type checking and
diagnostic boundaries. RF-006 supplies prepared inputs and revision-local reuse.
RF-001 owns availability; RF-008 owns evaluation and its supplied-quantity mapping.
Apply overlapping caller edits once. No schema or persistent Reference change is
required: target UUIDs retain their existing wire representation.

Delete the trivial key wrapper, serialization-only identity extraction, repeated
resolution and equivalent scalar-unit/quantity branches across the three current
implementations. Remove `model/_references.py` after its responsibilities and
callers are migrated, without a forwarding alias. Keep distinct validation and
acceptance checks. Record net size changes across all helpers, adapters and
callers; consolidation must not replace 45 lines with a larger framework.

### Implementation details to settle in W1

- Select the smallest resolved-target representation shared by prepared scopes
  and typed Model access without repeated serialization or parallel algorithms.
- Use UUID keys internally under the shared preparation contract. Coordinate
  RF-008's supplied-quantity mappings and keep backend/wire string conversions
  explicit at their boundaries.
- Map caller error contracts to the shared operations without changing public
  lookup failures or masking programming errors.

### Verification and completion criteria

Baseline on 2026-10-06: `tests/test_reference_identity.py` returned 10 passes and
one failure. `test_alignment_uses_coordinates_while_results_have_independent_ids`
could not run because `polars` was absent; the failure occurred in Flow alignment.
This was not evidence of a reference regression. Re-establish the baseline with
the required calculations dependencies for that test before completion.

Test the behaviour table through the relevant validation, execution and policy
callers. Cover measurement quantities with units compatible with, but different
from, their Measure units to prove that recorded content is not silently converted.
Check missing and wrong-kind targets, unresolved content, zero, Movement ownership,
Model and composed Specification scopes, and changed amounts under stable target
UUIDs in different revisions. Verify original document/path diagnostics and
non-mutation.

Exercise policy availability and prior-decision restrictions after consolidation.
Keep RF-008's missing-observation tests: evaluators must not use the new readers
as a fallback. Test candidate and output readings separately from input readings.
Run reference-identity, affected Model/Specification/Run, policy and temporal
execution suites, installed-package/import checks, and the combined checks in
[Verification](VERIFICATION.md).

Completion requires one scalar-access implementation, scoped resolution without
the identified repeated lookups, removal of trivial identity wrappers and old
imports, preserved error and revision boundaries, and passing required checks.
Update current guides and record deletion and size evidence before marking this
intent complete.

### Implementation record

Implemented in the coordinated working-tree pass. Standalone Definitions helpers use a catalogue-scoped RecordIndex; repeated Model assembly/value/scalar access reuses the Model index. Prepared mathematical roles use UUID keys and `model.scope` helpers rather than execution-owned symbols.

The old `execution/symbols.py` and redundant lookup wrappers are removed. Resolution keeps wrong-kind, missing and wrong-revision failures distinct. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-010 Consolidate graph table projection around View or Hierarchy input

### Problem and decision

[`graph/projection.py`](../src/rangekeeper/graph/projection.py) exposes `to_table()`
for Views and `to_tree_table()` for Hierarchies. The tree function already reuses
flat projection, but constructs an intermediate Table and Rows before rebuilding
them in preorder with a `parent_id` column.

Use one `to_table()` function whose input type selects the projection. Do not add
a `tree` flag. A View does not specify whether a tree should use Relationships or
Assembly membership; Hierarchy already owns that choice and validates topology.
The benefit is one public projection entry point and one construction path, not
elimination of a large duplicated projection algorithm.

### Intended API and composition

```python
def to_table(
    source: View | Hierarchy,
    *,
    columns: Iterable[Column] = DEFAULT_COLUMNS,
    units: UnitSystem = default_units,
) -> Table:
    ...
```

```python
to_table(view)             # Flat rows in View order.
to_table(hierarchy)        # Preorder rows with parent_id.
to_table(hierarchy.view)   # Flat projection of the same selected Entities.
```

Compose the implementation through direct steps:

1. Validate the input type and obtain its View and optional Hierarchy.
2. Materialize columns once. Validate supported column types and unique names.
3. Validate requested unit strings and Measure references once, including when
   the View is empty or every selected Value is missing.
4. For a Hierarchy, reject a requested column named `parent_id` before projecting
   cells. Preserve that name's availability for ordinary flat projection.
5. Use View order for flat output or the existing hierarchy preorder for tree
   output. Project each Entity's cells once, adding its parent UUID for tree rows.
6. Construct one set of Rows and one output Table.

Keep the existing column-value rules shared. Extract a small row helper only if it
reduces complexity; do not add a strategy hierarchy, dispatch registry or mode
object. Reuse existing column-name validation where practical. The current empty
Table used to validate names is also a deletion target if its rule can be reused
directly without duplicating Table invariants or adding a forwarding layer.

Use RF-006's `UnitSystem.validate_units()` instead of `compatible(text, text)` for
requested units. Use RF-004's agreed Measure lookup without building an index for
each column or row. Fix the unsupported-column error message to include
`PropertyColumn`, which the implementation already accepts.

RF-012 owns Value selection preparation within this flow. Prepare each Value
column once for the supplied Model, then use the shared owner-local selection
rule on canonical View Entities. Remove per-cell selector construction and
repeated Measure existence checks without weakening per-Value Measure assertions.

Coordinate the final step with `table.py` and RF-023. Table currently rebuilds
every Row, including an already normalized Row. Retain such a Row when its keys
exactly match the Table column order; otherwise normalize once. Mapping inputs
must be copied/frozen before reuse. Preserve missing/extra-column diagnostics,
duplicate identified-row checks, declared column order and the existing shallow
cell immutability contract. Do not introduce an unchecked Table constructor or
claim that removing the intermediate projection alone constructs each Row once.

### Contracts to preserve

| Input or case | Required result |
| --- | --- |
| View | One row per selected canonical Entity, in View order |
| Hierarchy | One row per Entity in preorder, with parent_id and None for the root |
| Hierarchy.view | Flat projection, without an implicit parent column |
| Row identity | Preserve the Entity UUID; do not substitute row position or an occurrence ID |
| Model identity | Preserve explicit model_id projection and the default columns |
| Missing or unresolved measurement | None; preserve recorded zero |
| Property content | Detached decoded content; preserve false and zero; reject a non-property Value |
| Labels and classification fields | Preserve current UUIDs, field values and missing-value behaviour |
| Value units and Measure assertions | Validate requests and apply explicit conversion as before |
| Empty View or missing Value column | Still reject invalid unit strings and invalid requested Measure references |
| Unsupported source or column | Raise the appropriate existing type/column error |

Preserve both Relationship and membership Hierarchies, their parent mappings and
their existing sibling order. Do not infer a Hierarchy inside projection or relax
its cycle, multiple-parent, parallel-edge or connectivity checks. Overlapping
membership still requires an occurrence-based representation outside this format.
Do not change Model data, perform IO, evaluate mathematics or make a Table reload
a Model. Keep the caller's explicit UnitSystem and default behaviour.

The new source type and removal of `to_tree_table()` are explicit API changes.
Audit keyword calls using `view=` as well as calls to the removed function; migrate
them to the selected `source` signature. No compatibility alias is planned. Moving
the reserved-name check before cell projection can change which error is reported
for multiply invalid requests; make this ordering explicit in the tests.

### Affected code, dependencies and deletion targets

Update `graph/projection.py`, its exports, all direct imports/calls of
`to_tree_table()`, and current examples and guides. Start with the tree projection
case in [`test_model_consumers.py`](../src/tests/test_model_consumers.py), then
search active source, typing fixtures and notebooks for further callers. Preserve
unrelated adapter functions also named `to_table()`; they have different input
contracts and are outside this item.

Coordinate unit preflight with RF-006 and Measure lookup with RF-004. Keep column
choice changes, if any, aligned with RF-002 without broadening this item into a
column-system redesign.

Delete the old tree entry point and export, intermediate flat Table, second Row
construction pass and lookup-based reorder. Do not retain the old path behind the
new function. Measure changes across projection and callers under the overall
reduction strategy; the smaller public API must also leave simpler control flow.

### Verification and completion criteria

Compare flat output with the existing projection behaviour. Verify tree preorder,
parent UUIDs, root None, Entity row identities and model_id for both Hierarchy
construction modes. Compare `to_table(hierarchy.view)` with ordinary flat output
to prove that the input type controls the format without extra state.

Cover columns supplied by an iterator, duplicate names, PropertyColumn acceptance,
unsupported objects, the reserved parent name in tree versus flat mode, invalid
units on empty Views, missing Values, Measure mismatch, conversions, zero, false,
null properties and non-mutation. Retain useful adapter and Table contract tests.
Run the affected model-consumer and adapter tests, typing and installed-package
checks, then the combined checks in [Verification](VERIFICATION.md).

Completion requires one type-directed public function, one row/output construction
path, preserved flat and tree semantics, migrated callers, removal of the retired
export and no obsolete active examples. Record baseline and final checks, deleted
code and size changes in the implementation record.

### Implementation record

`graph.projection.to_table` accepts View or Hierarchy and constructs one row
sequence. Value-column preflight validates units and resolves each requested
Measure once through the Model's existing index, including empty Views. Cells use
shared owner-local selection. Hierarchy `parent_id` conflicts fail before units
or cell projection. Classification fields also use the existing Model index.

`Table` retains normalized Rows with the declared column order and copies raw
mappings once. Constructor-count, preflight-count, ordering and immutability
regressions verify both paths. The old tree projection/export and intermediate
Table are removed. See the [combined acceptance record](#combined-implementation-record)
for final verification, size accounting and platform limits.

## RF-011 Simplify graph reducer names

### Decision and intended API

Rename the four public functions in
[`graph/reducers.py`](../src/rangekeeper/graph/reducers.py). The module and Quantity
type annotations supply the context; remove the redundant and inconsistent
singular/plural suffixes.

| Current name | Replacement |
| --- | --- |
| `sum_quantities()` | `sum()` |
| `mean_quantities()` | `mean()` |
| `min_quantity()` | `min()` |
| `max_quantity()` | `max()` |

Prefer module-qualified calls and reducer selection in active code and examples:

```python
from rangekeeper.graph import reducers

total = reducers.sum(quantities)
# In a Reduction constructor, use reducer=reducers.sum.
```

Keep these functions in `graph.reducers`; do not add top-level `rangekeeper.sum`
or `graph.sum` exports. Retain the existing Quantity input/output annotations,
shared `_reduce()` implementation and support for caller-supplied reducer
callables. Do not introduce reducer enums, a registry or a new class hierarchy.

### Built-in names and behaviour to preserve

Import `builtins` in the reducer module and pass `builtins.min` and `builtins.max`
to `_reduce()`. After renaming, bare `min` and `max` in that module would resolve
to the Quantity reducers themselves and invoke the wrong function. Audit other
affected modules for built-in shadowing; use `reducers.sum`, `reducers.min` and
`reducers.max` rather than unqualified imports where a conflict can occur.

Preserve all numerical and aggregation contracts:

- Sum uses `math.fsum`, not Python's ordinary built-in sum.
- Mean retains the current calculation over raw contributor quantities; do not
  replace it with an average of intermediate subtree averages.
- Inputs must contain schema Quantities with identical unit spellings. Callers
  continue to normalize units before reduction.
- Empty input remains an AggregationError, including for sum. Invalid element
  types, incompatible unit spellings, non-finite inputs, arithmetic overflow and
  non-finite results retain their existing error interfaces.
- Results remain Quantities in the input units. Preserve contributor selection,
  completeness rules, coverage, ordering and input immutability.

RF-013 supersedes the earlier proposal to preserve sum-function identity checks.
Remove `_is_sum`, its identity check and `Aggregation.known_subtotal()` with that
intent. Migrate callers to `available_value()`; for sum reductions this remains
the available subtotal. Do not introduce recognition of renamed or wrapped
reducers, or infer additive semantics for arbitrary callables.

### Affected code, deletion targets and sequence

1. Record the focused graph-test and typing baseline. Recheck all active uses of
   the four names, including imports, defaults, callable identity checks and
   examples. Do not infer the reducer from a function-name string.
2. Rename definitions and `__all__` in `graph/reducers.py`. Add explicit built-in
   references for minimum and maximum, retaining one implementation per operation.
3. Migrate `graph/reduction.py`, `src/tests/test_model_graph.py`,
   `tools/schema/typing_graph_valid.py`, `tools/schema/typing_graph_invalid.py` and
   the graph smoke check in `tools/schema/verify_install.py`. Keep invalid typing
   fixtures invalid for their intended argument error, not an obsolete import.
4. Update the API tree and examples in `docs/GRAPH_MODEL.md` and any other active
   callers found by the inventory. Document the breaking names in the upgrade
   guide. Preserve historical records and this plan's migration mapping.
5. Remove old exports and names without forwarding functions or compatibility
   aliases. Run the focused checks and relevant combined verification.

This intent is a naming simplification. Expect approximately neutral handwritten
code size, with only the necessary built-in qualification; do not claim deleted
runtime logic from shorter identifiers. Record size changes under the overall
strategy. It requires no schema or persisted-data migration. Coordinate shared
graph-file edits with RF-004 and RF-010 without extending their scope.

### Verification and completion criteria

Verify all four renamed functions on small fixtures with explicit expected
magnitudes and units. Include mixed-sign cancellation for accurate summation,
mean over unequal subtree populations, minimum and maximum, empty input, invalid
elements, mismatched unit spellings and finite-result failures. Exercise minimum
and maximum directly to catch accidental self-calls after renaming.

With RF-013, verify available results for the canonical `reducers.sum`, a wrapper
around it, mean, minimum and maximum through `available_value()`. Preserve the
numerical and coverage assertions from existing subtotal tests while migrating
their API calls. Run graph typing fixtures and installed-package checks to verify
public import paths and reducer callable types.

Completion requires all active callers to use the new names, no old exports or
aliases, unchanged numerical/coverage behaviour, updated documentation, and
passing applicable checks from [Verification](VERIFICATION.md). Record any
pre-existing failures separately from refactor results.

### Implementation record

`graph.reducers` exposes `sum`, `mean`, `min` and `max`; no old names or
compatibility aliases remain. Active callers use module-qualified names. The
implementation retains `math.fsum` and explicit `builtins.min`/`builtins.max`.

Independent numerical tests cover all four functions, empty inputs and cancellation.
Existing invalid-input, unit and finite-result checks remain. The upgrade guide
maps the four retired names. See the [combined acceptance record](#combined-implementation-record)
for final verification, size accounting and platform limits.

## RF-012 Simplify graph Value selection preparation while preserving revision safety

### Problem and decision

Retain [`graph/selection.py`](../src/rangekeeper/graph/selection.py), its
`select_value()` factory and the `ValueSelector` callback contract. They provide
shared owner-local Value selection for reduction and projection. Immutability
does not remove this responsibility: an Entity from an earlier revision can
remain in memory with the same UUID and different content.

The public selector currently resolves the supplied Entity UUID against the
supplied Model before reading its Characteristics. Thus
`select_value("net")(new_model, old_entity)` reads the new Model's Value. Preserve
this deliberate revision behaviour. An unknown Entity UUID still fails; the
selector must not read the supplied object's fields as a fallback.

The duplication is preparation at graph call sites. Projection builds and invokes
a selector for every Value cell, even after checking requested Measures during
column preflight. Both projection and reduction obtain canonical Entities from
their pinned Views before the public selector resolves them again. Consolidate
the shared selection rule and remove redundant work where the caller can establish
the required context directly.

### Intended composition and boundaries

Keep a small shared operation for owner-local key selection and the optional
Measure assertion. Reuse `model.characteristics.value()` for exact key lookup;
do not add another Characteristics scan. Keep graph SelectionError translation
and callback orchestration in graph code.

Separate the public input boundary from internal use on canonical records:

| Caller | Required work |
| --- | --- |
| Public `select_value()` factory | Validate the key and optional Measure UUID; return the existing callable shape |
| Public selector invocation | Check Model/Entity arguments, resolve the Entity in that Model, validate the requested Measure and apply shared local selection |
| Projection preflight | Validate each Value column once for its Model, including requested Measure existence even for an empty View |
| Projection cell | Read the canonical View Entity, select by key and check the selected Value's Measure; reuse completed column preparation |
| Custom reduction selector | Invoke the callable and validate its returned Value against the current Model and owner |

Finalize the smallest helper and prepared-column representation with RF-010.
Prepare selection once per Value column and Model, rather than once per row.
Keep this preparation local to the operation; do not attach a Model-bound cache
to reusable column definitions or reuse it across revisions. RF-004's catalogue
index must not be rebuilt for each column or cell.

Internal selection may omit Entity re-resolution only when its input comes
directly from the same pinned View. Keep that prerequisite internal; do not add
a public `trusted=True` flag, duck-typed bypass, callback registry or function-name
test. Retain the public callable path for Reduction unless a small direct design
can establish an equivalent prepared path without changing arbitrary callbacks.
Do not add a second selector framework merely to save one indexed lookup.

### Contracts to preserve

- A key is an exact, case-sensitive owner-local key. A Measure is a type assertion,
  not a unique Value key. Do not guess from codes or select the first Value with
  a matching Measure.
- An absent key returns None. A present key with a different requested Measure
  raises SelectionError. A missing or wrong-kind Measure fails even when the key
  is absent; projection must also check this when there are no rows.
- Selection returns a Value record or None, not a calculated quantity. Keep
  scalar eligibility, unresolved quantities and explicit unit conversion in their
  existing reduction/projection stages. Preserve recorded zero and missing-value
  semantics.
- Preserve public argument checks and their ordering. Document any deliberate
  projection error-order change with RF-010 rather than silently changing it.
- Preserve `Reduction.execute()` checks on custom selector results: require a
  Value, resolve it in the current Model, check owner identity and compare its
  content with the canonical record. Immutable callback inputs do not prevent a
  callback from returning an old Value, another owner's Value or a Formulation
  Value. Do not replace these checks with UUID equality alone.
- Preserve selected Value IDs, coverage and contributor behaviour. Preparation
  must not invoke custom selectors early, for ineligible Entities, or more often
  than the existing callback contract.
- Keep Models and records immutable. No history loading, resolver calls, implicit
  latest revision, expression evaluation or cross-revision cache is introduced.

### Affected code, deletion targets and sequence

1. Establish baselines for `test_revision_pinning_and_stale_selector_rejection`,
   owner/Measure rejection, invalid callbacks and projection behaviour. Inventory
   selection use in `graph/selection.py`, `graph/reduction.py`,
   `graph/projection.py`, tests, typing/install fixtures and `docs/GRAPH_MODEL.md`.
2. Reconcile shared local selection and projection preparation with RF-010,
   catalogue access with RF-004, and revision-local reuse with RF-006. RF-009
   scalar access must not replace owner-local key selection or weaken ownership.
3. Reuse one local selection rule from the public selector and prepared projection
   path. Remove per-cell factory calls, repeated argument preparation and repeated
   requested-Measure existence checks from projection. Retain the per-Value
   Measure match check.
4. Review Reduction's canonical-input lookup separately from callback-result
   validation. Remove only preparation with an established equivalent boundary;
   retain callback-result checks and document any retained indexed lookup.
5. Update graph documentation and run focused and combined checks. Public selector
   names and signatures remain unchanged, so no compatibility aliases are needed.

Expect fewer per-cell operations and neutral or lower handwritten code size.
Measure new helpers, preparation and all callers together. Do not claim a smaller
implementation from moving checks into another module. Explain any necessary
growth under the overall reduction strategy.

### Verification and completion criteria

Test old and new Models containing the same Entity and Value UUIDs with changed
contents. Public selection must read the supplied Model, while each View continues
to read its pinned revision. A custom callback returning stale content must fail;
also retain cross-owner, Formulation-local and invalid-return-type cases.

Compare public selector and internal projection results for valid and absent
keys, wrong Measures, missing/wrong-kind Measure references and unresolved Values.
Test empty Views, multiple rows and multiple Value columns, including reuse of
the same column definition with different Models. Verify preparation occurs at
the column/Model boundary and is not repeated for each cell. Keep expected
results independent of the shared helper so both paths cannot validate the same
mistake against each other.

Run affected graph and model-consumer tests, typing fixtures and installed-package
checks, then the applicable checks in [Verification](VERIFICATION.md). Record
existing failures separately. Completion requires retained public selection and
revision contracts, no per-cell selector construction, shared local selection,
preserved custom-selector validation, current documentation and recorded size and
verification evidence.

### Implementation record

Public `select_value` still resolves an Entity UUID in the supplied Model,
validates its requested Measure, and returns that revision's existing Value.
Projection uses shared `_local_value` on canonical View Entities after column
preflight. It creates no per-cell selector and builds no second Model index.

Custom reduction results retain type, owner and canonical-content checks. Content
comparison uses strict ordered, type-sensitive record equality from RF-020, not
schema equivalence. Regressions cover stale/cross-owner results, empty-column
preflight and callback order. See the [combined acceptance record](#combined-implementation-record)
for final verification, size accounting and platform limits.

## RF-013 Compose graph reduction and aggregation results

### Problem and decision

Keep [`graph/reduction.py`](../src/rangekeeper/graph/reduction.py) as one cohesive
module. `Reduction` owns reusable selection and reduction configuration,
`Aggregation` owns an immutable result pinned to a Hierarchy, and `Coverage`
describes selected contributors. These responsibilities do not require a new
package or a class hierarchy.

The current result stores `_values`, `_available` and `_coverage` in separate
mappings with identical keys. `_values` is derived from the other two and
`require_complete`, but the result does not retain that policy. Independent
construction can therefore supply contradictory values. The current constructor
copies and freezes the mappings correctly; retain that protection.

`_is_sum` also couples a generic result to one callable's identity. A wrapper
around the sum reducer produces equivalent results but cannot use
`known_subtotal()`. Remove this special case and use `available_value()` for all
reducers. This is an explicit public API change, coordinated with RF-011; do not
retain compatibility aliases or introduce a reducer registry.

### Intended result composition

Use one entry per hierarchy Entity, with the following conceptual fields:

```python
@dataclass(frozen=True)
class AggregateEntry:
    available: Quantity | None
    coverage: Coverage


@dataclass(frozen=True)
class Aggregation:
    hierarchy: Hierarchy
    entries: Mapping[UUID, AggregateEntry]
    value_ids: Mapping[UUID, UUID]
    require_complete: bool
```

This sketch omits validation and accessors. Finalize entry visibility and naming
during implementation; a new top-level public export is not required. Copy and
freeze the entries and provenance mappings, and validate the completeness policy.
Derive `value(id)`, `__getitem__()` and `root_value` from the entry and policy.
Keep `coverage(id)` and `available_value(id)` as direct access to the entry's data.
Retain the existing error boundary for an Entity outside the pinned View.

Keep `hierarchy`: it supplies the topology and pinned Model context. Keep
`value_ids`: an unresolved selected Value has an identity, while an absent key
does not. `require_complete` remains a useful Boolean policy; do not replace it
with a strategy object merely because `_is_sum` is removed.

Assign structural validation to the data owner:

- Coverage validates unique UUIDs and the measured/missing partition of selected
  contributors.
- An entry validates its types and the relationship between measured coverage
  and an available result: measured contributors require a Quantity, while no
  measured contributors require None under the current reducer contract.
- Aggregation requires exactly the hierarchy's Entity keys, coverage within each
  corresponding subtree, and consistent owner-to-Value provenance. Measured
  contributors require selected Value identities; unresolved selected Values may
  also have identities. Preserve ownership checks against the pinned Model.

These checks establish structural consistency, not mathematical correctness of
an arbitrary reducer. Do not rerun callbacks during result construction. Avoid
repeated subtree reconstruction when checking membership; review the cost of
these checks with the traversal representation.

### Execution composition and validation

Extract a few cohesive operations from `Reduction.execute()` while leaving the
postorder traversal and subtree assembly visible:

| Operation | Responsibility |
| --- | --- |
| Select a contribution | Check eligibility, invoke selection, validate the owner-local canonical Value, retain its identity and normalize a resolved measurement |
| Reduce quantities | Return None for an empty population; otherwise invoke the reducer, require a Quantity and normalize its output units |
| Assemble a subtree result | Combine the Entity's contribution with raw child contributions and coverage, then construct one result entry |

Use a small internal contribution record only if it makes the selection result
clearer and replaces scattered state. Do not create a class for each stage or a
generic pipeline. The reduction helper should remove the duplicated invalid
reducer-return branches, while preserving callback exceptions.

Coordinate owner-local selection with RF-012. Custom selectors still require
type, owner and canonical-content checks even when their input Entity comes from
a pinned View. Extract a shared canonical-Value check only if another caller has
the same contract. Do not replace content comparison with object identity or UUID
equality. `Record.__eq__` currently serializes to JSON and has different comparison
semantics from `to_data()` dictionary comparison; using `==` is not an established
optimization or an automatically equivalent replacement.

Use RF-006's `UnitSystem.validate_units()` instead of
`compatible(self.units, self.units)`. Preserve unit validation at construction,
including reductions that later select no contributors. Keep both input and
output conversion: custom reducers may return compatible alternative units.

Centralize coverage assembly. Retain the three stored tuples initially unless a
smaller representation improves the full implementation. Storing selected and
missing IDs and deriving measured IDs is an option, but adds repeated filtering.
Never reconstruct selected order by concatenating measured and missing IDs.

### Behaviour to preserve and exclusions

- Call contributors and selectors in the existing postorder sequence. Do not
  invoke selectors for ineligible Entities. Preserve strict callback return-type
  checks, callback counts and the interleaving of selection and reduction.
- Pass raw measured contributions to each subtree reducer, with the Entity's own
  quantity first, followed by child subtrees in hierarchy order. Do not pass child
  aggregate results: that changes means over unequal populations, custom reducer
  inputs and potentially floating-point results.
- Reduce every nonempty measured population even when complete coverage is
  required and unavailable. Preserve the available result separately from the
  policy-filtered reported value. Never call a reducer with empty input.
- Preserve zero, missing keys, unresolved Values and excluded contributors as
  distinct cases. Empty selected coverage remains empty rather than complete.
- Retain the default contributor policy, including eligible parent Entities.
  Do not infer leaf-only populations or prevent double counting by silently
  excluding recorded parent values.
- Retain scalar Measurement eligibility, owner/revision safety, immutable inputs,
  selection errors, unit errors and propagation of user callback exceptions.
  Do not broaden selection to Formulation-local Values or other scalar kinds.
- Retain both relationship and membership Hierarchy support. No Model mutation,
  solver execution, persistence, schema migration or cross-revision cache is added.

Keep traversal performance as a separate measured opportunity. Retaining raw
quantities and coverage for every subtree can store quadratically many references
on a deep chain. Releasing a child's raw buffer after its parent consumes it may
reduce temporary storage; a shared contributor sequence with subtree ranges is a
larger alternative. Fully materialized per-node coverage still has its own storage
cost. Do not claim linear total storage merely by removing the raw buffer map, or
introduce associative folding for arbitrary reducers. Defer larger representation
changes until profiling and order-sensitive tests justify them.

### Affected code, deletion targets and sequence

1. Recheck `graph/reduction.py`, `graph/reducers.py`, `graph/selection.py`,
   `graph/hierarchy.py`, `graph/view.py` and active result consumers. Establish
   implementation-size and behaviour baselines before editing runtime code.
2. Finalize the entry representation and constructor checks. Replace the parallel
   result mappings with entries, retain the policy and derive reported values.
3. Remove `_values`, `_is_sum`, `known_subtotal()`, the concrete sum import and
   function-identity check. Replace reflective validation across parallel mappings
   with entry validation. Migrate subtotal consumers to `available_value()`.
4. Compose selection and reduction operations with RF-012 and RF-006. Remove
   duplicated reducer-return checks and scattered coverage construction without
   changing traversal or callback behaviour.
   RF-023 may reuse the matching per-population selection, conversion and coverage
   work for flat workflow totals; keep hierarchy Aggregation and workflow-specific
   missing-business-key/source-evidence results distinct.
5. Coordinate renamed reducers with RF-011. Update graph tests, consumer tests,
   typing/install fixtures, `docs/GRAPH_MODEL.md`, active examples and the upgrade
   guide where affected. Keep historical records intact.

Expect fewer independent state containers, result-construction arguments and
special branches, with neutral or lower handwritten implementation size across
the full change. Count the new entry type, validation and all migrated consumers.
Explain any net growth required by stronger constructor invariants under the
overall reduction strategy; moving code into helpers is not itself a reduction.

### Verification and completion criteria

The review baseline on 2026-10-07 was 37 passing tests from
`tests/test_model_graph.py`, run from `src` with
`.venv/bin/python -m pytest tests/test_model_graph.py -q -p no:cacheprovider`.
This verifies the reviewed implementation, not the proposed refactor. Re-establish
the baseline at implementation time.

Preserve the current numerical, coverage, selection and immutability assertions.
Add or adapt focused cases for:

- Complete, incomplete and empty populations under both completeness policies;
  unresolved Values, absent keys, recorded zero and excluded contributors.
- Equivalent available results for the canonical sum and a wrapper around it;
  available mean, minimum and maximum without sum-specific recognition.
- Unequal subtree populations, order-sensitive custom reducers, callback order
  and counts, invalid returns, compatible output conversion and visible errors.
- Stale, cross-owner and Formulation-local callback results; equivalent
  reconstructed canonical Values must remain accepted.
- Direct construction with inconsistent entry state, foreign or out-of-subtree
  coverage, invalid mapping keys or provenance; caller-owned mapping mutation
  must not change a constructed result.
- Relationship and membership trees and results pinned to different revisions.

Run affected graph/consumer tests, typing fixtures and installed-package checks,
then applicable combined checks from [Verification](VERIFICATION.md). Use expected
quantities and coverage independent of the new helpers. If temporary-buffer
optimization is included, also verify deep-chain and branching trees and report
measured storage effects separately from remaining coverage costs.

Completion requires one entry mapping, derived policy-filtered values, no sum
identity special case or subtotal compatibility alias, cohesive execution helpers,
preserved callback and numerical contracts, documented constructor invariants,
migrated consumers, passing checks and recorded size evidence.

### Implementation record

`Aggregation` stores one immutable mapping of `AggregateEntry` values plus
selected Value identities and completeness policy. Entries hold the available
result and coverage; `value()` applies completeness, while `available_value()`
works for every reducer. Parallel result maps, `_is_sum` and `known_subtotal()`
are removed.

Reduction separates contribution validation, quantity reduction and subtree
assembly. Shared graph population collection normalizes recorded quantities and
retains Value IDs and contributor coverage for both hierarchy and flat workflow
callers. Hierarchy traversal retains raw contributor order and callback
interleaving; workflow retains its flat filters, missing business keys and ordinary
summation. It does not manufacture a Hierarchy or use graph summation implicitly.
Constructor checks validate subtree ownership without rerunning reducers. Tests
cover wrapped reducers, immutable copies, invalid coverage and cancellation under
each caller's policy. See the [combined acceptance record](#combined-implementation-record)
for final verification, size accounting and platform limits.

## RF-014 Simplify formulation authoring, identity and operation names

### Problem and decision

The review covered every module in `src/rangekeeper/formulations/`: `__init__`,
`_construction`, `_identity`, `_alignment`, `expression`, `flow`, `growth`,
`financial` and `account`. Retain the package's purpose: declare passive equations
over explicit Model Values and Movement coordinates. Numerical operations on
known data remain in `calculations`; semantic validation remains with RF-003 and
RF-005. Authoring must not evaluate recorded amounts, choose unknowns, invoke a
solver, mutate a Model or load history.

The current private files contain useful work, but the split adds unnecessary
boundaries. `build_formulation()` checks duplicate equation keys and then calls
`_construction.construct()`. Specialized operations call `construct()` directly,
so they bypass that check. `_identity` is shared with `policies/resale.py`, despite
being presented as a private formulation detail. `_alignment` mixes Flow shape
matching, reference ownership and a redundant reference constructor.

Consolidate those responsibilities into cohesive existing owners and one authoring
module. Remove the `build_` prefix where the module already establishes that the
operation creates declarations. This is a deliberate API change without aliases.

### Intended structure and shared construction

```text
formulations/
  __init__.py       small facade; re-export declare and the domain modules
  authoring.py      declare, identify, identify_tree
  expression.py    small ordered Expression constructors
  flow.py          shape, aligned, sum, scale, accumulate
  growth.py        compound, linear
  financial.py     discount, present_value, reversion
  account.py       standalone interest and the agreed nonnegative account schedule
```

1. Combine `_construction.py` and `_identity.py` into `authoring.py`. Implement
   `declare()` there and re-export that same function as `formulations.declare`.
   Do not retain a second forwarding constructor in `__init__.py`.
2. Route generic and specialized Formulation authoring through `declare()`.
   Preserve the public `id`, `name`, `equations` and `values` concepts. Specialized
   operations pass their existing operation token as `name`. Share equation-key
   uniqueness, occurrence identity, Constraint construction and ordered,
   deduplicated whole-Value bindings in this path.
3. Normalize equation keys to the text used by identity generation before checking
   uniqueness. Existing specialized callers use UUID keys as well as text keys;
   a UUID and its string representation must not silently generate colliding IDs.
   Materialize equation entries once if needed and reuse that collection. Preserve
   supplied order and the existing duplicate-key error contract where applicable.
4. Move shape-only `shape()` and `aligned()` into `formulations/flow.py`. Resolve
   each source shape once and reuse it for duplicate detection and matching. Keep
   these operations usable by growth, financial, account and resale authoring.
5. Replace `_alignment.owner()` with RF-009's shared scoped target/Value ownership
   operation. Preserve the distinction between a Value and a Movement owned by a
   Value. Do not add another ownership lookup implementation here.
6. Delete `_alignment.target(value, item)`: `value` is unused and the function only
   returns `Reference(target=item.id)`. Construct that reference directly where
   needed. Ownership is established by Model resolution and validation, not by the
   discarded argument.
7. In `account.interest()`, prepare the principal Flow and its units once rather
   than resolving its shape for every nonnegative-principal constraint. Reuse the
   prepared shape in alignment where the final small helper interface permits it.

Apply RF-015's narrow coordinate-index reuse rule when extracting shape matching.
RF-017 preserves the underlying coordinate tuple contract. Share duplicate
detection and lookup only where this replaces code; keep symbolic destination
order, account transaction order, numerical sorting and join policy separate.

`authoring` owns deterministic declaration identity because both Formulations and
policy declarations need it. Under RF-018, move the resale strategy to the
investment example and have that model-local authoring use this explicit shared
module and the shape helpers in `formulations.flow`. Do not create a repository-wide UUID
utility or merge migration/scenario identity code merely because it also uses
`uuid5`; its namespace and provenance contracts can differ. Coordinate package
initialization with RF-001 so these imports do not create cycles or eager imports
of execution and optional numerical dependencies.

### Public naming and caller migration

| Current operation | Planned operation |
| --- | --- |
| `formulations.build_formulation()` | `formulations.declare()` |
| `formulations.flow.build_sum()` | `formulations.flow.sum()` |
| `formulations.flow.build_scale()` | `formulations.flow.scale()` |
| `formulations.flow.build_accumulation()` | `formulations.flow.accumulate()` |
| `formulations.growth.build_compound()` | `formulations.growth.compound()` |
| `formulations.growth.build_linear()` | `formulations.growth.linear()` |
| `formulations.financial.build_discount()` | `formulations.financial.discount()` |
| `formulations.financial.build_present_value()` | `formulations.financial.present_value()` |
| `formulations.financial.build_reversion()` | `formulations.financial.reversion()` |
| `formulations.account.build_interest()` | `formulations.account.interest()` |
| `formulations.account.build_balance()` | Remove; call `formulations.flow.accumulate(source=movements, ...)` |
| New account schedule composition | `formulations.account.schedule()`; explicit RF-015 addition, not a compatibility wrapper |
| `formulations.expression.sum_expressions()` | `formulations.expression.sum()` |

Use module-qualified calls where `sum` or other operation names could be ambiguous.
Keep the existing small arithmetic constructors (`literal`, `reference`, `add`,
`subtract`, `multiply`, `divide`, `power`, `equal`). Type `binary()` with RF-002's
canonical Operator enum and migrate its callers. Avoid a second operator enum.
Audit Python built-in name use during the rename; qualify a required built-in
instead of accidentally recursing into the declaration operation.

`account.build_balance()` adds no account-specific rule: it forwards directly to
Flow accumulation. Remove it rather than rename a redundant wrapper. The agreed
RF-015 schedule has distinct continuity, interest-base, treatment and rate rules.
It is a new composed operation with explicit supported scope. This intent does
not rename unrelated policy builders or all `build_*` functions in the repository.

### Identity, shape and mathematical contracts to preserve

- Retain the exact UUID5 owner namespace and compact JSON encoding of stringified
  identity parts. Retain existing operation tokens, including `accumulation` and
  `compound`, even when Python function names change. These tokens currently also
  supply the Formulation name; do not change serialized declarations incidentally.
- Preserve equation keys, Constraint suffixes, the `expression` root path and
  ordered nested paths such as `/operands/0`. Each owned Expression occurrence
  gets its own identity even when input trees reuse the same symbol. Reference
  targets remain unchanged. The supplied Expression tree remains unchanged.
- Identity remains independent of recorded magnitudes. Existing equation IDs must
  survive insertion of another distinctly keyed equation. Operand order and
  occurrence paths remain significant; do not promise IDs survive tree rewrites.
- RF-003 may provide reusable traversal, but its use must preserve all current
  nested owned IDs and path spelling. Keep the existing export/rebuild mechanism
  until a simpler record traversal is proven equivalent. File consolidation alone
  does not justify changing identity semantics or introducing a visitor framework.
- Shape alignment accepts unresolved amounts. It checks exact coordinate sets,
  rejects duplicates, preserves destination Movement order and keeps explicit
  mapping requirements for lagged relationships. It neither interpolates nor
  silently matches by position. Empty-source and empty-expression rejection
  remains explicit where currently required.
- Do not replace symbolic alignment with `calculations.series.align()`: that
  operation has numerical, missing-value, ordering and optional Polars contracts
  which do not belong in passive authoring.
- Flow accumulation remains signed continuity with an explicit initial symbol.
  It does not clamp overdrafts or insert a hidden zero. Growth `compound` uses the
  initial amount for the first coordinate, then the prior amount times `1 + rate`.
  Growth `linear` uses an amount increment, with the first index zero.
- Financial `discount` retains its explicit nonnegative `first_period`, periodic
  dimensionless rate and exponent sequence. `present_value` sums an already
  discounted Flow; it does not apply another discount. `reversion` keeps its
  complete result-Movement-to-income-Movement mapping and explicit capitalization
  units. No annualization, day count or next-period income is inferred.
- Standalone account `interest` continues to declare `interest = principal *
  rate` and `principal >= 0`, with `nonnegative_principal is True`. Keep this
  primitive distinct from the new `schedule()` composition agreed in RF-015.
  The schedule uses explicit initial/rate/result references and all three shared
  choices, constructs one Formulation, and supports the nonnegative fixed-rate
  execution subset. It does not add loan caps or piecewise overdraft solving.
  Preserve primitive identities; freeze new schedule relation keys separately.

### Affected code, dependencies and deletion targets

Migrate all formulation modules, resale authoring moved from `policies/resale.py`
to the investment example under RF-018, `examples/design.py`,
`examples/investment.py` and their imports. Update `tests/test_temporal_execution.py`,
scenario/policy and example consumers, `docs/SCENARIOS_AND_POLICIES.md`, relevant
calculation/expression guides, and typing/installed-package fixtures. Search source,
tools and maintained notebooks for remaining names during implementation; preserve
historical evidence as historical rather than claiming it uses the new API.

RF-002 supplies canonical operators. RF-003 owns semantic expression analysis and
any shared traversal. RF-005 owns Formulation semantics: `declare()` must not grow
a competing Model validator. RF-009 supplies scoped ownership. RF-001 owns policy
availability and import isolation. RF-015 owns the shared account conventions,
numerical fixes and schedule equations; RF-008 coordinates the bounded execution
support. Neither authoring nor the shared account choices import calculations.

Delete `_construction.py`, `_identity.py` and `_alignment.py` after their callers
migrate. Delete the separate `build_formulation` wrapper, `build_balance`, `target`
and all superseded exports. Three removed private modules and one new authoring
module reduce the package by two modules. Expect a net reduction in handwritten
code after wrappers and repeated preparation are removed. Count shared helpers
and policy caller changes as part of the result; a move alone is not a reduction.

The new account schedule is an agreed exception to a rename-only scope. Count its
implementation and necessary execution support separately from authoring
consolidation. Reuse prepared shapes, equation construction and one `declare()`
call. Do not add intermediate persisted Values or a generic expression backend
solely to share numerical and symbolic account arithmetic.

### Verification and completion criteria

Before implementation, freeze representative declaration and resale identity
fixtures from the current checkout. Verify generic and specialized authoring
produce equivalent records after renaming, including IDs, operand order,
Constraints, bindings and reference targets. Cover repeated symbol occurrences,
distinct equation insertion, normalized duplicate keys and unchanged input trees.

Verify exact and mismatched coordinates, duplicate coordinates, reordered source
coordinates with destination order retained, unresolved magnitudes, empty inputs,
unit constraints and complete/incomplete reversion mappings. Use independent
expected equations and existing forward/inverse execution checks, not assertions
which only mirror the new helper implementation. Verify the account nonnegative
boundary and periodic growth/discount starting-point conventions.

Run temporal execution, scenario/policy and affected example tests, then applicable
typing, import and installed-package checks. Confirm declaration imports work
without optional numerical engines and that no live imports refer to the deleted
private modules or old public names. During the earlier review, a focused temporal
selection returned five passes and one failure:
`test_finite_balance_interest_scaling_sum_and_explicit_reversion_mapping` reported
`not_assessed` instead of `feasible`. That is a prior observation, not a current
baseline or a diagnosed authoring defect. Recheck it before implementation and
record its cause separately; do not weaken acceptance to make the refactor pass.

Completion requires one construction path, preserved deterministic identities,
reused shape and ownership preparation, migrated public names and policy consumers,
deleted redundant files/functions, passing applicable checks and measured size
evidence. No full symbolic construction-loan schedule is implied.

### Implementation record

Implemented in the coordinated working-tree pass. `formulations.authoring` exposes `identify`, `identify_tree` and `declare`; operation modules use direct verbs. Shared shape/alignment helpers live in `formulations.flow`.

`_identity.py`, `_construction.py` and `_alignment.py` are removed. The shared coordinate index has no sorting or join policy. A fixture recovered from the preserved pre-implementation runtime covers standalone interest, accumulation, growth and resale declarations. A separate fixture fixes the new schedule's relation and occurrence identities. Independent numerical oracles cover the renamed builders. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-015 Compose account conventions, calculation and formulation

### Agreed account contract and ownership

The user approved this composed design on 2026-10-07. Replace the earlier
combined InterestBasis proposal and its unresolved capitalized/arrears mapping.
Preserve all six existing numerical combinations. Add the bounded symbolic
schedule explicitly with RF-014; do not describe that addition as a rename.

`calculations/account.py` currently mixes base selection and charge treatment in
`method="simple"`, `"compound"` and `"capitalized"`; `timing="advance"` or
`"arrears"` controls transaction inclusion. Replace them with three named choices:

| Argument | Canonical enum in `rangekeeper.account` | Members and wire values |
| --- | --- | --- |
| `balance` | `Balance` | OPENING = `opening`; CLOSING = `closing` |
| `current_interest` | `CurrentInterest` | EXCLUDED = `excluded`; INCLUDED = `included` |
| `treatment` | `InterestTreatment` | SEPARATE = `separate`; FINANCED = `financed` |

The lightweight `account.py` module owns these enums and combination validation.
Both numerical calculation and symbolic schedule authoring import this same
contract; neither imports the other. Keep this one small module free of Model
loading, calculation/formulation runtimes and optional dependencies. No combined
four-member basis enum, TransactionTiming enum, positional Boolean flags,
Convention class, strategy registry or mutable account engine is needed.

`balance` selects the opening balance or the balance after principal transactions
but before the current charge. `current_interest` then selects whether that charge
enters its own calculation base. Earlier financed interest is already in opening
debt under every combination. `treatment` specifies whether the calculated charge
is added to this account. SEPARATE does not assert payment; do not call it PAID.

These are separate concepts with an explicit combination rule: INCLUDED requires
FINANCED, for either balance selection. Reject both INCLUDED + SEPARATE cases
before calculation or authoring, including on empty input. There are six supported
combinations. Do not silently downgrade an invalid choice to another formula.

The existing default becomes CLOSING + EXCLUDED + SEPARATE. Preserve the
`Account.calculate()` entry point and result fields; replace only its ambiguous
method/timing arguments and retain its numerical `rate=0` default. Expose the
same named choices on the new symbolic
`formulations.account.schedule()` composer. The standalone `account.interest()`
authoring primitive still accepts an explicit principal; it needs no schedule
options because the caller has already supplied its base.

Accounting treatment stays outside this operation. Adding borrowing costs to an
asset, paying accrued interest and financing it into a loan are different actions.
Do not add an accounting-treatment enum, ledger, funding waterfall, loan cap or
reserve schedule as part of this refactor.

### One period expressed as composed operations

Let `B` be the signed opening balance, including previously financed interest;
`T` the signed net principal transactions; `r` the per-period rate; `I` the current
interest; and `C = B + T` the balance before adding that interest. A draw increases
T and a principal repayment reduces T. T excludes any charge that FINANCED will
add automatically.

1. **Apply transactions:** calculate `C = B + T`.
2. **Select the base:** `A = B` for OPENING; `A = C` for CLOSING.
3. **Calculate interest:** use `max(A, 0) * r` for EXCLUDED, or
   `max(A, 0) * r / (1 - r)` for INCLUDED.
4. **Apply treatment:** next signed balance is C for SEPARATE or `C + I` for
   FINANCED. Carry that signed balance into the next period.

The included-interest equation on a nonnegative base is `I = r * (A + I)`.
Its closed form preserves the existing formula, including capitalized arrears.
Financing prior-period interest alone does not imply division by `1 - r`.

The equations are the semantic contract, not a requirement to change floating
evaluation order incidentally. Preserve characterized numerical behavior and
document any justified rounding-level differences against independent tolerances.
Do not claim byte-identical results from an algebraic rearrangement without proof.

Preserve the existing signed internal recurrence and zero interest on a
nonpositive base. Report opening and closing as their nonnegative parts; report
the negative closing part as overdraft balance. Derive overdraft movements from
successive negative balances, with initial zero so the first movement includes
any initial deficit. Never feed the clamped display balance into the recurrence.
Keep `Account.difference()` as the change in nonnegative reported balance.

Rates are explicit per-step ratios, scalar or dimensionless Flow; convert percent
units explicitly. Do not infer annual rates or day count. Require finite numerical
rates greater than -1, excluding booleans. INCLUDED also requires r < 1. Preserve
negative-rate behavior within these bounds. Validate invalid scalars even when
there are no transactions, and retain finite-result checks for arithmetic overflow.

### Complete legacy mapping

| Existing method | Existing timing | balance | current_interest | treatment |
| --- | --- | --- | --- | --- |
| simple | advance | CLOSING | EXCLUDED | SEPARATE |
| simple | arrears | OPENING | EXCLUDED | SEPARATE |
| compound | advance | CLOSING | EXCLUDED | FINANCED |
| compound | arrears | OPENING | EXCLUDED | FINANCED |
| capitalized | advance | CLOSING | INCLUDED | FINANCED |
| capitalized | arrears | OPENING | INCLUDED | FINANCED |

The final row uses `I = r * max(B, 0) / (1 - r)`, then applies transactions and
the financed charge to the signed balance. It is retained, not approximated by
ordinary opening interest or closing-base interest. Remove old arguments, strings
and exports after migrating active callers; do not retain compatibility aliases.
A principal repayment remains a principal movement, not a total debt-service
payment requiring allocation between principal and interest.

### Numerical preparation, recurrence and result construction

Keep three cohesive stages in `calculations/account.py`; use small functions
where they remove repeated work, not a result wrapper for every stage.

1. **Prepare once.** Validate the choice combination, resolved transactions,
   starting Quantity, units, rates and coordinate correspondence. Normalize the
   starting amount to transaction units and Flow rates to dimensionless ratios.
   Scalar validation precedes expansion. Prepare exact coordinate-to-rate lookup.
2. **Calculate in original transaction order.** Select each rate by coordinate,
   then apply the period operations above. Maintain only the signed running
   balance and output amounts. Do not sort the recurrence to match another API.
3. **Construct results once.** Build opening, closing, interest, overdraft balance
   and overdraft movement Flows. Preserve input records, units, coordinates,
   encounter order and existing new-output Movement identity conventions.

Remove the dependency on `calculations.series.align()` for rate pairing. That
operation has sorting and dataframe contracts this recurrence does not need.
For this refactor, preserve its currently required exact input coordinate order
at the account boundary, then use coordinate lookup internally. A reordered rate
Flow still fails rather than introducing an unrelated acceptance change. Cover
same-day distinct coordinates, duplicates, missing and extra coordinates explicitly.

RF-014's symbolic matching retains its own rule: exact coordinate sets with
destination order preserved. Share a low-level duplicate-aware coordinate index
only if it reduces both callers without hiding these different order contracts.
Keep such matching below calculation/authoring, with no Polars or Model IO. Do
not merge the full numerical and symbolic alignment APIs.

### Passive symbolic schedule and bounded execution support

Add `formulations.account.schedule()` as an explicit RF-014/RF-015 scope addition.
It returns one Formulation over caller-declared Values. Use one small interface:

- Model and Formulation `id`;
- `transactions` Flow Value UUID and `starting` scalar Reference;
- `rate` as a scalar Reference or a Flow Value UUID matched to the schedule;
- caller-declared `closing` and `interest` result Flow Value UUIDs;
- the three convention arguments and explicit `nonnegative_principal=True`.

The transaction Flow supplies schedule order. Require both result Flows to
use that same coordinate order; match rate Movements by coordinate. Reuse exact
shape alignment after these recurrence-specific checks. Prepare each shape/units
once and bind Movement references directly. An empty
schedule is rejected because it has no recurrence to declare; numerical empty
input remains supported after validation. Do not invent intermediate persisted
Values, read magnitudes, resolve history, assign unknowns, or execute a solver.

For each period, compose opening from the starting Reference or prior closing
Movement, express C and A, and declare:

- `I = r * A` for EXCLUDED, or `I = r * (A + I)` for INCLUDED;
- `closing = C` for SEPARATE, or `closing = C + I` for FINANCED;
- nonnegative opening, selected pre-interest base A and closing constraints;
- explicit per-period rate predicates `r > -1` and, for INCLUDED, `r < 1`.

This is the overdraft-free subset of the numerical operation. It does not encode
`max(A, 0)`, clipped display balances or overdraft output Flows. A negative selected
base or closing balance violates its declared constraints. The full signed
calculator remains available for known data. Do not disguise piecewise execution
as supported by merely recording an overdraft flag.

Keep the existing standalone `interest()` equation and nonnegative-principal
guard. Reuse its equation-construction logic where practical, plus RF-014's
expression constructors, prepared shapes and `declare()`. Collect equations and
call `declare()` once; do not construct several temporary Formulations and merge
their serialized records. Preserve old primitive IDs and tokens. Give the new
schedule its own token and stable keys based on destination Movement UUID plus
relation role, independent of recorded magnitudes.

With every rate fixed by explicit Specification assignments or literals, the
interest and continuity equalities are affine, including `I = r * (A + I)`.
Recorded rates and estimates are not fixed assignments. Unknown-rate products
and piecewise overdraft execution remain unsupported by the scalar executor.
Inspect reference dependencies before simplification, so a zero coefficient does
not silently turn an unsupported unknown-rate case into an accepted one.

The existing scalar compiler/evaluator support only equality and nonstrict
bounds. Complete this necessary integration with RF-008 and execution preparation:
strict rate predicates whose operands depend only on fixed assignments/literals
are checked exactly after unit normalization, before solving. Preserve their
original assertions and scoped evidence. False fixed predicates prevent a
feasible result; strict predicates involving unknowns remain unsupported. Do not
replace strict bounds with an epsilon or use policy truth as numerical acceptance.
Independent acceptance must recheck these original fixed predicates exactly on
the reconstructed candidate, without trusting the compiler's result or tolerances.
Keep this a bounded fixed-predicate capability, not a general nonlinear backend
or an account-name special case in the compiler.

### Construction-loan evidence and scope boundaries

The following workbooks were inspected read-only during the discussion. Formulas
and saved values were read separately; VBA was inspected as text and was not run.
Neither workbook was modified or recalculated. Capture small synthetic regression
cases from these equations; do not make tests depend on local attachments or
distribute the workbooks as fixtures.

**RLV workbook:** `25.1.24_RLV Model_1801 Tib_CF.xlsx`, `Cash Flow!Z13:Z28`, with
rate and funding parameters in `Model!M28:M34`.

- Row 22 is opening senior debt, row 23 is the draw, row 24 is principal paydown,
  row 25 is closing debt and row 27 is interest on that closing debt.
- Row 27 feeds development costs through financing costs; those costs feed the
  debt draw after equity. Current interest therefore enters the balance on which
  that same interest is calculated. Once equity is exhausted and the loan limit
  does not bind, this is `CLOSING + INCLUDED + FINANCED`.
- The workbook also has equity-first funding, fees, a loan-to-cost limit and
  iterative project sizing. These cannot be reduced to an unconstrained account
  recurrence. Row 20 records the loan commitment at origination, not an immediate
  draw of the entire facility.
- For the inspected February column, opening debt was about `412,477.357445`,
  non-interest funded cost `166,360.516150` and `r = 0.085 / 12`. The closed-form
  charge is about `4,129.351175`, close to the cached `4,129.351190`. Saved linked
  balances contained small inconsistencies, so cached values are not proof of a
  freshly converged whole-workbook calculation.

**Operating-cash workbook:** `Operating Cash During Construction.xlsm`,
`Financial Model!125:149`, funding rows `112:123`, annual rate `E46`, and the
`project_cost` VBA function used by `F109:H109`.

- Row 128 is opening debt, row 129 draws, row 130 principal repayment and row 131
  closing debt. Row 134 calculates interest from opening debt and the period rate
  in row 132. Current draws do not earn a full period of interest immediately.
- Row 135 sends construction interest to the project-cost schedule. Project debt
  and equity fund that budget; the loan balance does not separately add row 134
  as another interest draw. For the account calculation this is
  `OPENING + EXCLUDED + SEPARATE`, with a separately reported charge and an
  explicit funding schedule.
- The VBA function iterates total cost and debt sizing, calculating construction
  interest on debt outstanding before each new construction draw. Its global
  funding feedback does not imply the RLV same-period `r / (1 - r)` convention.
- Rows 140 onward include debt-service reserve funding. A reserve top-up is a
  separate cash-reserve movement, not another name for adding interest to loan
  principal. The post-construction schedule separates interest and principal.
- An independent sizing equation reproduced the saved total project cost
  `1,009,006.599872`, debt `857,655.609891` and construction interest `37,170.238862`
  in workbook units. This confirms the inspected equations, not a new Excel/VBA
  execution or a full commercial model audit.

Do not infer that either workbook defines a universal construction-loan convention.
Partial debt/equity funding, interest reserves, fees, caps, draw dates and repayment
allocation belong in explicit schedules. If an input draw already includes funded
interest, do not add that charge again through `FINANCED`. Daily or average-balance
interest needs an explicit timing/day-count contract; do not add unsupported enum
members during this refactor. The agreed symbolic schedule above is a bounded
addition to RF-014. It does not add these project-funding features or piecewise
overdraft execution.

Terminology references checked during the discussion:

- [Edfinancial: payments, interest and fees](https://edfinancial.studentaid.gov/payments-interest-and-fees)
  distinguishes accrued interest from unpaid interest added to principal.
- [NAB Home Loan General Terms](https://www.nab.com.au/content/dam/nabrwd/documents/terms-and-conditions/loans/home-loan-general-terms.pdf)
  illustrates daily balance calculations and monthly charges. It is a product
  example, not a rule governing every construction facility.
- [IAS 23 Borrowing Costs](https://www.ifrs.org/issued-standards/list-of-standards/ias-23-borrowing-costs/)
  addresses including eligible borrowing costs in asset cost. It does not choose
  the loan's interest-base formula.

### Confirmed preparation defects to correct

1. **Rate alignment can change the recurrence.** `Account.calculate()` obtains
   rates from `series.align()`, which sorts coordinates, but loops over the original
   transaction sequence. Distinct same-day event keys can therefore pair a
   transaction with the wrong rate. For ordered keys `z`, `a`, transactions
   `100`, `100`, opening debt `0` and respective rates `0.1`, `0.2`, the current
   compound/advance case produces final debt `242` instead of `252`.
   Prepare rate lookup by explicit coordinate and consume it in the original
   transaction order. Do not sort a stateful recurrence to match an incidental
   alignment order. Retain exact coordinate validation, dimensionless conversion
   and unresolved-rate rejection; retain the existing rejection of input
   coordinate-order mismatches as specified above. Test that rejection separately
   from same-day internal sorting.
2. **Empty transactions bypass scalar-rate validation.** Repeating a scalar into
   an empty list means the later `any(...)` check sees no values. Invalid scalars
   such as `NaN`, `True`, `-2`, or `1` for the including-interest formula can be
   accepted. Validate the scalar once before expansion or iteration. Validate
   every supplied Flow rate and its units/coordinates through the Flow boundary.

Share only preparation with matching contracts. A small ordered coordinate lookup
can remove the account's dependence on numerical alignment, but do not broaden
`series.align()` or import the symbolic authoring layer to fix this bug. If a
shared lower-level coordinate operation materially reduces duplication, establish
its owner and order/error contract before using it in either layer.

### Affected code, verification and completion criteria

Update `account.py`, `calculations/account.py`, `formulations/account.py`, RF-002's
choice inventory, account callers, financial examples, guides and typing/install
checks. RF-014 owns shared declaration construction and identity. RF-008 and
execution preparation/compiler/acceptance own the bounded fixed-predicate
integration required for the symbolic rate contract. Keep Model declarations,
Specification assignments and execution capabilities separate.

Delete mixed method dispatch, superseded transaction-timing arguments and
branches, positional pairing of sorted rates with original transactions, repeated
scalar validation and the unused numerical alignment import. Preserve the Account
result and remove RF-014's trivial `build_balance()` wrapper. The new schedule
adds account-specific equations and constraints; it is not that wrapper renamed.

Three small enums, correctness checks and a new symbolic composer can add lines.
Count this growth explicitly across all owners. Reduce ambiguous branches and
repeated preparation; do not claim the new capability is a mechanical size saving.
Do not add a shared numeric/symbolic arithmetic framework to avoid a few explicit
equations with different return types and validation responsibilities.

Required verification:

- Check every row in the six-case legacy mapping against independently stated
  equations, including the retained capitalized/arrears case and default parity.
  Reject both INCLUDED + SEPARATE combinations at both public entry points.
- With opening 100, two periods of zero transactions and rate 0.1, separate
  interest totals 20 and debt stays 100; ordinary financed interest closes at
  121; included financed interest closes at approximately 123.456790. Check
  each period's charge and balance, not only the final amount.
- Test balance selection independently of treatment: nonzero draws/paydowns,
  signed balances, zero crossings, negative/zero rates and principal-only
  repayments. Preserve first-period deficits and `Account.difference()`.
- Reproduce the same-day z/a regression with distinct rates: the existing
  compound/advance case must close at 252 rather than 242. Include per-period
  checks where an incorrect pairing could cancel in the final balance.
- Test scalar/Flow rates, percent conversion, incompatible units, exact input
  coordinate-order rejection, missing/extra/duplicate coordinates, unresolved
  amounts, empty input, Boolean/nonfinite rates and the -1/1 boundaries. Preserve
  inputs, coordinates, order, units and current output identity conventions.
- Test passive schedule construction with unresolved magnitudes; explicit initial
  symbols; scalar and Flow rate references; shared transaction/result ordering;
  shape errors; duplicate IDs; stable relation keys; and untouched input Models.
- Solve all six conventions on the nonnegative fixed-rate subset. Compare both
  implementations with independent expected schedules, not only with each other.
  Check original-equation acceptance and exact fixed strict bounds independently
  of compiler lowering. Invalid bounds must fail without an accepted output;
  unknown rates/strict bounds and overdraft cases must not silently pass.
- Preserve old standalone interest/accumulation identities and existing error
  contracts. New schedule IDs have their own frozen fixtures and do not claim to
  preserve a previously nonexistent schedule representation.
- Keep synthetic RLV and operating-cash examples to distinguish same-period
  interest inclusion from opening-balance interest plus explicit funding. Do not
  make tests depend on local workbooks or add funding caps/accounting assertions.
- Run affected cases in `tests/test_calculations.py`, `test_flow_operations.py`,
  `test_calculation_equivalence.py`, `test_formulas.py`, `test_temporal_execution.py`
  and `test_execution.py`, then applicable combined typing, package and regression
  checks. Update source fingerprints for the changed calculation and execution
  behavior. Check import isolation for both account entry points.

Prior audit evidence: the focused account/financial selection passed 30 tests
with 68 deselected after optional Polars was supplied in a temporary audit
environment. Independent positive-balance checks covered 120 combinations of
method, timing, transactions and variable rates. This supports the old formulas;
it does not negate the two preparation defects or establish acceptance of the
new choices, schedule composer or execution support. Record fresh results.

Completion requires the six-case mapping and default, signed numerical behavior,
both preparation fixes, passive schedule and bounded execution capability,
migrated callers/docs, independent verification and complete size evidence.
No product decision remains open on whether to retain capitalized arrears.

### Implementation record

Implemented in the coordinated working-tree pass. `account.py` owns Balance, CurrentInterest and InterestTreatment. Numerical Account recurrence and `formulations.account.schedule` use these same choices; `interest` remains an explicit-principal operation.

All six legacy mappings retain their numerical oracle. Tests cover same-day rate pairing, empty invalid rates, signed debt/overdraft recurrence, six actual solves, strict fixed-rate bounds and unsupported symbolic cases. Synthetic construction cases distinguish same-period included interest from opening-based interest with explicit later funding. Required schedule contracts add implementation code. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-016 Compose duration operations around Frequency and explicit calendar rules

### Problem and decision

Review the duration package against the useful domain structure of the retired
`duration.py`, rather than renaming individual functions in isolation. The legacy
`Type` enum connected offsets, whole-period measurement, containing-period
alignment, sequences and Span operations. Its pandas-specific codes and repeated
branches are not required to recover that cohesion.

The current [`duration/calendar.py`](../src/rangekeeper/duration/calendar.py)
retains all ten frequencies as a Literal and dispatch mappings. Its companion
[`duration/period.py`](../src/rangekeeper/duration/period.py) constructs Periods
from anchored offsets, but frequency preparation and boundary generation are not
shared consistently. Empty period requests can bypass frequency validation.

Restore one canonical `Frequency` under RF-002 and compose the operations around
one frequency step definition. Major domain decisions below are agreed. Exact
signatures, enum member spelling and helper placement remain implementation
details, not an invitation to reopen the contracts or expand scope. Earlier
suggestions such as `shift_date`, `periods_from`, `covering_span` and
`DayCountConvention` are not approved renames under this intent.

### Capability scope and ownership

Include these capabilities in the coordinated refactor:

| Capability | Contract and composition |
| --- | --- |
| Date offset | Apply a signed number of frequency steps to an explicit date |
| Period sequence | Generate adjacent half-open intervals from one anchor, bounded by count or endpoint |
| Whole-period measurement | Count complete anchored frequency steps; use the signed contract below |
| Containing-period alignment | Return the half-open calendar Period containing a date under explicit alignment rules |
| Extension | Compose existing offset and sequence primitives where required; retain the original anchor and rules |

Keep immutable `Period` and `Span` records in `model.duration`. Calendar arithmetic
belongs in duration operations; record boundary interpretation remains shared
Period behaviour. Keep the current calendar/period separation where it expresses
this dependency. File reduction alone is not a reason to merge them, and this
intent does not require a new package hierarchy.

Do not add a `Sequence` class merely as a namespace for static functions. Existing
sequences can remain tuples of Periods. Extension callers must supply the anchor
and rules that cannot be reliably recovered from intervals alone. A sequence
object would require a demonstrated need to retain that information and an
explicit implementation rationale; do not infer frequency from recorded dates.

### Frequency definitions and shared primitives

Use domain enum values rather than pandas aliases. Retain all ten frequencies
and define their steps once:

| Frequency | Step |
| --- | --- |
| Day | 1 calendar day |
| Week | 7 calendar days |
| Biweek | 14 calendar days |
| Month | 1 calendar month |
| Quarter | 3 calendar months |
| Half-year | 6 calendar months |
| Year | 12 calendar months |
| Biennium | 24 calendar months |
| Five years | 60 calendar months |
| Decade | 120 calendar months |

Expose this metadata through the enum or one small associated mapping. Do not
introduce frequency subclasses, a strategy registry or approximate conversion
of calendar months to days. Offsets interpret the step; sequence generation uses
cumulative steps from the original anchor; Period construction pairs boundaries.
Measurement uses the same offset rules. Alignment supplies the separate grid
phase and calendar boundaries described below.

Validate public configuration before iteration, including requests for zero
periods or an empty interval. A lazy iterator must not defer required input
checks until its first yield. Retain date-only inputs, integer counts excluding
Booleans, and validate Boolean options such as `include_partial` explicitly.
Preserve count/end-bound distinctions and the explicit partial-final-period rule.

Keep one shared exact-date guard. Place it with existing Python argument guards
in `validate.py` if this simplifies its many consumers without changing errors.
Do not replace the exact-date check with an `isinstance(date)` check that admits
datetime values. Keep semantic interval checks on Periods rather than building
a generic calendar validation framework.

### Month-end policy and deliberate behaviour changes

Replace the `month_end` Boolean with a named rule. `MonthRoll` is a working type
name; the two agreed members are:

| Rule | Behaviour |
| --- | --- |
| PRESERVE_END, default | If the original anchor is a month end, target month ends; otherwise preserve its day number and clamp only invalid dates |
| CLAMP | Preserve the original anchor's day number and clamp only invalid target dates, even when the anchor is a month end |

Apply these rules only to month-based steps. Day/week/biweek offsets retain exact
calendar-day steps and do not snap to month ends. Do not add a MONTH_END offset
member. Deliberately selecting a month-end date belongs to alignment, followed
by an offset or sequence with PRESERVE_END.

Examples for 2026, always evaluated against the original anchor:

- Under PRESERVE_END, 31 January produces 28 February and 31 March.
- Under PRESERVE_END, 30 January produces 28 February and 30 March. The clamped
  February result must not change the sequence into a month-end schedule.
- From 30 April, PRESERVE_END produces 31 May; CLAMP produces 30 May.
- From 15 January, both rules produce 15 February and 15 March.

Zero offsets return the input date unchanged after argument validation. Sequence
construction also preserves its supplied starting boundary. Alignment is the
explicit operation when the start itself must move.

PRESERVE_END restores the legacy default and intentionally changes the current
default. The current `month_end=True` option can force month ends from mid-month
anchors, including at count zero; it has no direct replacement flag. Inventory
those callers and express their intended alignment and first boundary explicitly.
Do not mechanically substitute PRESERVE_END and silently change their schedules.

### Containing-period alignment

Alignment returns a half-open `Period` containing the supplied date. Reuse
`PeriodTiming.FIRST`, `.LAST` or `.END` under RF-017 to select its first included
day, last included day or exclusive end when a date is needed. Do not introduce
another set of date-selection flags or confuse
the last included date with the exclusive boundary.

| Frequency | Alignment rule |
| --- | --- |
| Day | The containing calendar day |
| Week | Monday start by default; keep any supported override explicit |
| Month | Calendar month starting on day one |
| Quarter, half-year, year | Configurable year-start month; January default, with July–June equally supported |
| Biweek | Explicit origin on the intended fortnight grid; no epoch default |
| Biennium, five years, decade | Explicit origin specifying the year grouping and calendar/fiscal boundary |

An alignment origin defines the grid in both directions; it need not precede the
date being aligned. Validate consistency with the selected week start or fiscal
boundary. Reject conflicting origin and alignment settings rather than silently
choosing one. Keep the parameter representation small; a new persisted calendar
record is not required by this intent.

Monday alone cannot select between two alternating fortnight grids. Require an
origin for containing-fortnight alignment and reuse it for repeated operations.
Do not use 1 January 1970, 5 January 1970, odd/even week numbers or an annual reset
as an implicit convention. Fortnight boundaries remain continuously 14 days apart.

Multi-year alignment likewise needs an origin: biennia beginning 1 January 2020
and 1 July 2021 define different valid grids. The origin must agree with the
year-start month when both are supplied.

These origin requirements apply to containing-block alignment. Ordinary offsets
and sequences already supply their anchor and need no additional epoch or grid
origin. Do not silently align a user-supplied sequence start to a containing block.

### Whole-period measurement

Count complete steps under the same frequency and month-end rule as anchored
sequence generation. For increasing endpoints, the result is the largest
nonnegative integer count whose offset from the starting endpoint does not pass
the ending endpoint. An exact boundary counts; an incomplete remainder does not.
Return zero for identical endpoints or an interval shorter than one complete step.

For reversed endpoints, swap them, compute the forward result and negate it.
Thus `measure(a, b) == -measure(b, a)`. Use half-open boundary semantics without
an inclusive-end flag. This operation counts steps anchored at the earlier
endpoint; it does not count independently aligned calendar bins crossed.

Do not promise that measurement inverts every signed offset. Calendar clamping
loses information, and the chosen sign-symmetric measurement rule need not undo
a negative offset from a different anchor. Document and test this limit instead
of introducing special cases to force incompatible properties.

Exclude fractional months/quarters and nearest-period rounding. Keep financial
fractions in `year_fraction()` with an explicit day-count convention. Retain one
PyXIRR convention mapping shared by accrual and financial operations; actual/actual
remains ISDA and 30/360 remains European 30E/360. Preserve lazy financial imports.
Do not restore the legacy fixed annual counts of 365 days or 52 weeks as exact
calendar conversions, or duplicate backend financial arithmetic.

### Dependencies, deletion targets and implementation sequence

1. Establish baselines for calendar/period operations, their consumers and import
   behaviour. Use legacy source as capability evidence, not as a numerical oracle
   for contracts that deliberately changed, including half-open intervals.
2. Implement the canonical duration enums with RF-002 and one shared step
   definition. Keep lightweight imports and one public enum identity.
3. Consolidate offset and anchored boundary preparation. Remove the frequency
   Literal, repeated frequency dispatch/preparation, duplicated boundary loops
   where they share a contract, and the `month_end` Boolean path.
4. Implement containing-period alignment and complete-step measurement using
   those primitives. Keep distinct stopping, alignment and measurement policies
   explicit; do not conceal them in a generic sequence engine.
5. Migrate duration exports, Period/Flow behaviours, policies, calculations,
   financial callers, tests, typing/install fixtures, active examples and guides
   where affected. Audit unchanged calls too: the month-end default changes.
   Preserve historical evidence and document deliberate migration choices.
6. Update the upgrade guide's string-frequency replacement advice, document the
   enum-based API and calendar contracts, and run focused and combined checks.

Affected implementation includes `duration/calendar.py`, `duration/period.py`,
`duration/__init__.py`, `_behaviors/period.py`, `_behaviors/flow.py`, `validate.py`
if the guard moves, and calendar consumers in `calculations` and `policies`.
Coordinate enum imports with RF-002 and shared argument-guard ownership with
RF-006 without making document validation execute calendar calculations.

Expect less duplicated dispatch and sequence preparation. The added measurement
and alignment capabilities may cause net runtime growth; report that separately
from simplification of existing operations and justify it by this agreed scope.
Count new metadata, helpers and all consumers. Do not claim savings by comparison
with the already-retired legacy file, or add compatibility aliases and wrappers
to preserve obsolete names or pandas codes.

### Verification and completion criteria

Review evidence on 2026-10-07: 44 focused calendar/date/financial tests passed.
A broader run had 97 passes and 16 failures involving missing Polars. These are
review baselines, not acceptance of this intent; establish the implementation
environment and classify fresh failures before comparing results.

Use independent expected dates and intervals to verify:

- All ten frequency steps, positive/negative/zero offsets, leap years, supported
  date-range boundaries and unchanged rejection of datetime coordinates.
- PRESERVE_END versus CLAMP, original-anchor behaviour across February and the
  April-to-May distinction; zero offsets and sequence starts remain unchanged.
- Count-bounded and endpoint-bounded sequences, adjacency, partial final periods,
  and eager invalid-configuration rejection even for empty requests.
- Calendar and July–June years, their quarters and half-years, and Monday weeks.
- Opposite Monday fortnight origins, dates before/after each origin, and continuous
  14-day grids across year boundaries; missing or conflicting origins must fail.
- Multi-year blocks for calendar and fiscal origins, including dates exactly on
  an exclusive boundary, which belong to the next Period.
- Alignment followed by FIRST/LAST/END selection under RF-017, including an explicit first
  month-end date for a mid-month request. Do not test only already-aligned dates.
- Complete-step counts, partial remainders, equal dates, sign symmetry and the
  documented non-invertibility of clamped calendar offsets. Include expected
  counts independent of the shared offset helper.
- Migrated callers that previously relied on default clamping or forced
  `month_end=True`, and extension that retains its original anchor and rules.
- Unchanged financial day-count outputs, immutable records, public enum identity,
  typing contracts and absence of eager pandas or financial backend imports.

Run affected cases in `tests/test_calculations.py`, `tests/test_modules.py`,
`tests/test_flow_dates.py` and `tests/test_financial_library.py`, plus new focused
measurement/alignment cases and applicable installed-package, typing and combined
checks from [Verification](VERIFICATION.md).

Completion requires shared frequency metadata and boundary preparation, all agreed
capabilities, explicit alignment origins, the documented month-end default change,
signed whole-period measurement, migrated callers and guides, passing applicable
checks and recorded code-size evidence. No major domain decision remains open;
record the final API and module placement before implementation, with reasons for
any further public rename or abstraction.

### Implementation record

Implemented in the coordinated working-tree pass. `duration` exposes Frequency, MonthRoll, PeriodTiming and DayCount, with offset, measure, align, cover and period constructors. Month offsets default to preserving month ends.

Old flags and aliases are removed. Native-date, leap-year, anchored-grid, elapsed-step, all ten signed frequency offsets, representable date limits and original-anchor extension cases pass; calendar behavior is tested separately from wire migration. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-017 Clarify Period boundary fields and timing names

### Problem and agreed API

Period currently stores `start` and `end` for the half-open interval `[start, end)`.
Its timing options are `start`, `last_day` and `end`. The distinction is correct,
but the names require callers to remember that `end` is outside the covered dates.

Store explicitly named boundaries and provide concise derived properties. Rename
the schema fields for Period, inherited by Span:

| Current stored field | Planned stored field | Meaning |
| --- | --- | --- |
| `start` | `start_inclusive` | First included calendar date |
| `end` | `end_exclusive` | Boundary immediately after the included dates |

Expose read-only properties through the existing `PeriodBehavior` mixin:

| Property | Derivation |
| --- | --- |
| `first` | `start_inclusive` |
| `last` | `end_exclusive - timedelta(days=1)` |
| `end` | `end_exclusive` |

Only the two boundary fields are stored and serialized. The three properties
are calculated on access, with no cache or duplicate state. They are the agreed
convenience API, not schema fields. `end` retains its exclusive meaning as a
read-only property, but `end=` is no longer a constructor or replacement field.
Do not add a `start` compatibility property or retain old constructor keywords.

Use the canonical RF-002 enum, exposed through `rangekeeper.duration`:

```python
class PeriodTiming(Enum):
    FIRST = "first"
    LAST = "last"
    END = "end"
```

Example of the planned interface:

```python
january = Period(
    start_inclusive=date(2026, 1, 1),
    end_exclusive=date(2026, 2, 1),
)

january.first  # 2026-01-01
january.last   # 2026-01-31
january.end    # 2026-02-01

assert january.resolve(timing=PeriodTiming.LAST) == january.last
assert january.resolve(timing=PeriodTiming.END) == january.end_exclusive
```

This supersedes the interim suggestions `START`, `LAST_DAY`, `END_EXCLUSIVE`,
`first_day` and `last_day`. Do not introduce `NEXT`: the exclusive boundary exists
whether or not a following Period is declared. Retain one timing enum identity
and RF-002's enum-only Python argument boundary, with explicit text conversion
where an external configuration supplies strings.

### Ownership and behavior to preserve

`schema/duration.yaml` owns the two fields and their descriptions. Generate Python
constructors, properties and typed replacement signatures, JSON Schema and slot
metadata, and the C# bindings from that source. Do not edit generated files by
hand. In C#, the stored properties become `StartInclusive` and `EndExclusive`.
Do not expand this intent into a new C# behavior framework.

`_behaviors/period.py` owns the derived Python properties, positive-interval check
and `resolve()` dispatch. Reuse those date derivations rather than repeat the
last-day subtraction in callers. Span inherits the same Python behavior. Keep
the existing canonical record classes and nested-decoding registry; do not add a
second Period wrapper or move field declarations into the behavior mixin.

Preserve these contracts:

- Intervals remain half-open, positive and date-only. Equal or reversed endpoints
  remain invalid under semantic checks. Datetime inputs are not silently truncated.
- Duration remains `end_exclusive - start_inclusive`; there is no added day.
  Adjacent intervals share an exclusive/inclusive boundary without overlap.
- FIRST is included, LAST is included, and END is excluded. A one-day interval has
  `first == last`; its `end` is the following date. Leap days and year boundaries
  require no special alternative representation.
- `resolve()` retains validation and returns the date selected by the enum.
  `Movement.resolve()` still prefers an explicitly recorded date, including one
  outside its coverage Period. An undated period Movement still requires explicit
  timing, and an invalid supplied timing still fails even if a date is recorded.
- Flow ordering, overlap checks, matching coordinates, trimming, extent,
  integration and resampling use the same boundary dates as before. Do not change
  coordinate tuple contents or convert an exclusive endpoint to LAST accidentally.
  Coordinate-index reuse under RF-014/RF-015 must preserve these dates and leave
  order and join decisions with each operation. Keep serialized dataframe keys
  at the numerical adapter boundary rather than making them domain coordinates.
- Policy observation availability and resale dates previously using `last_day`
  use LAST and keep the same dates. Financial/payment callers previously using
  `end` use END and keep the same dates. No payment convention is inferred.
- Properties do not mutate records, mint revisions or alter field presence. A
  property named `end` does not make `has_field("end")` true or export an `end` key.

### Migration, dependencies and deletion targets

Apply the following mappings explicitly:

| Current interface | Replacement |
| --- | --- |
| Period/Span constructor and `replace(start=..., end=...)` | `start_inclusive=..., end_exclusive=...` |
| Period/Span JSON or YAML `start` and `end` | `start_inclusive` and `end_exclusive`, with dates unchanged |
| `timing="start"` / proposed `PeriodTiming.START` | `PeriodTiming.FIRST` |
| `timing="last_day"` / proposed `PeriodTiming.LAST_DAY` | `PeriodTiming.LAST` |
| `timing="end"` | `PeriodTiming.END` |

For interval arithmetic, prefer the explicit stored boundary names. For a selected
calendar date, use `first`, `last`, `end` or `resolve(timing=...)`. Audit duration
factory arguments with RF-016: a function explicitly accepting a pair of Period
boundaries should expose their inclusive/exclusive meaning. Do not mechanically
rename every unrelated `start` or `end` argument, sequence anchor, date range or
opaque content key in the repository.

This is a wire-format and constructor change, not only an enum rename. Inventory
persisted examples and supported input versions. Apply existing versioning and
migration rules and the integrated version/support table before implementation.
Reject old wire names at the new strict boundary; support their conversion only
through the explicit source-version migration. Do not accept two competing field
layouts in canonical records or automatically upgrade store reads. Reject
ambiguous mixed layouts in migration.
An old exclusive `end` date maps directly, without adding or subtracting a day.

Update active fixtures as a coherent set. Serialized bytes and computation/schema
fingerprints will change even though dates do not. Audit content hashes, revision
pins and referenced artifacts; follow existing migration/provenance rules rather
than silently rewriting stored history or claiming old content hashes still match.
Historical snapshots remain evidence of their original version.

Affected code includes schema sources and generated bundles, `PeriodBehavior`,
`MovementBehavior`, `FlowBehavior`, `model.duration`, duration factories and RF-016
calendar operations, calculations, policy availability/resale, scenario generation,
examples, adapters and active migration code. Update relevant Grasshopper
constructors/consumers and cross-language fixtures. Inspect wire dictionaries as
well as attribute access: a search only for `.start` and `.end` is insufficient.

Update record-boundary, domain, calculation, scenario/policy and upgrade guides,
maintained notebooks, schema examples, tests and typing/install fixtures. RF-002
owns enum generation/encoding conventions; RF-016 owns calendar arithmetic;
RF-006 owns reuse of local semantic checks; RF-001 owns policy availability.
This intent renames boundaries and selectors without changing those domain rules.

Delete the old PeriodTiming Literal, old option names, obsolete wire field
definitions and superseded dispatch. Reuse the existing behavior mixin rather
than add a module, adapter or compatibility layer. Three short properties can
add a small amount of handwritten code; they provide the agreed date-selection
API without duplicate storage. Record this expected growth separately from
generated field renames and any removed caller-side date derivation.

### Verification and completion criteria

Establish representative pre-change boundary and resolution fixtures. Verify:

- January resolves to 1 January, 31 January and 1 February for FIRST, LAST and END.
  Cover one-day periods, leap February, year boundaries, adjacency and membership
  exactly at the exclusive endpoint, plus invalid and out-of-range dates.
- Direct, JSON and nested construction return the canonical Period/Span types
  with the new properties. Span retains its inherited methods and schema fields.
- Exports contain only the new stored boundary names; derived properties are not
  fields. Typed replacement uses only new keywords and preserves the input.
- New strict constructors/codecs reject obsolete or mixed field layouts. Test any
  explicit version migration separately, including unchanged exclusive-end dates.
- Recorded Movement dates retain precedence, undated Periods need a timing choice,
  and policy/payment dates do not shift by one day during migration.
- Flow matching coordinates, coverage, overlap checks, trim, extent, integration
  and financial calculations retain their results. Isolate RF-016's intentional
  calendar changes from this naming-only date migration.
- Python typing accepts the new enum and fields and rejects old keywords/options;
  C# generated records and cross-language round trips agree on the new wire keys.
  Regeneration checks pass and no optional numerical dependency loads merely from
  importing Period or PeriodTiming.

Run affected record, record-behavior, Flow-date, calendar, policy and calculation
tests, schema examples, generator checks, cross-language checks and applicable
typing/installed-package checks from [Verification](VERIFICATION.md). Search live
callers and guides for old field/option names, allowing only documented historical
or explicit migration uses. Record any platform checks that could not be run.

Completion requires explicit stored boundaries, consistent FIRST/LAST/END enum
and properties, migrated schema/bindings/consumers, preserved date results, a
documented wire-version strategy, passing applicable checks and size evidence.

### Implementation record

Implemented in the coordinated working-tree pass. Period/Span use start_inclusive and end_exclusive. FIRST/LAST/END timing choices are migrated across calculations, policy, scenarios, examples, fixtures and notebooks.

Source-layout migration handles old fields before target construction. Python/C# generation and a bidirectional record round trip pass. Historical archived documents retain their old fields and pins. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-018 Simplify policy ownership, evaluation and decision terminology

### Problem and decision

The review covered all five modules in `src/rangekeeper/policies/`, their
Specification/Run validation callers, execution preparation and investment-model
construction. Retain the package's generic purpose: evaluate finite declarative
policies over explicitly available observations and produce recorded evidence.
It must not own a catalogue of investment strategies or make numerical
feasibility claims.

Current smells include a resale strategy exported as generic library behaviour,
independently stored derived assignments, unvalidated sequence fields in frozen
dataclasses, repeated observation/history preparation, and a public `decide()`
entry point that relies on semantic checks performed only by `evaluate()`.
Availability and scalar-access duplication and private cross-package imports
overlap with RF-001, RF-006, RF-008, RF-009 and RF-014; integrate those changes
rather than adding competing helpers.

### Declaration and outcome terminology

Rename `DecisionPoint` to `Decision` as requested. The existing `Decision` already
means recorded evaluation evidence, so move that meaning to `DecisionOutcome`.
The two remain separate records: a declaration contains rules and fallback;
an outcome records observations, the chosen rule, assignments and termination.

Use matching field terminology in the same migration:

| Current API | Intended API | Meaning |
| --- | --- | --- |
| `DecisionPoint` | `Decision` | One dated declaration with observations, ordered rules and fallback |
| `Policy.points` | `Policy.decisions` | Ordered declarations |
| Current `Decision` | `DecisionOutcome` | Evidence from evaluating one declaration |
| Current `Decision.point` | `DecisionOutcome.decision` | UUID of the originating Decision declaration |
| `PolicyResult.decisions` | `PolicyResult.outcomes` | Ordered evaluated outcomes |
| `Report.decisions` | `Report.outcomes` | Persisted policy outcomes in Run evidence |

Migrate internal preparation fields, arguments and diagnostics to the same
distinction, including execution's `Prepared.decisions`. Do not overload a single
record with both unevaluated rules and evaluated results, or use `Decision` as an
alias for two meanings. Keep outcome-to-declaration UUID references, rule IDs,
date values, order and optional-field presence unchanged.

Change `schema/policy.yaml` and `schema/run.yaml` as the source of truth. Regenerate
Python and C# records, native/JSON schemas, metadata, registries and manifests
through the existing generators. Update public record exports, typed fixtures,
validators, codecs and Run consumers together. Generated output must not be edited
by hand. Removing old names without compatibility aliases is deliberate.

Field renames change JSON/YAML keys, not just Python class names. Apply the
integrated version/support table and explicit migration contract with RF-017 and
RF-021. Preserve historical snapshots and Runs; do not rewrite stored history
in place or silently interpret an old outcome as a new declaration. Test that
unsupported old shapes are rejected clearly, and any explicit converter preserves
record presence, identity, references and order.

### Model-specific policy authoring

Move `build_stop_gain_resale_policy()` from `policies/resale.py` into the investment
example's construction code, consolidating its existing wrapper in
`examples/investment.py`. A named, tested model-local factory is appropriate;
callers need not duplicate a large Policy declaration inline. It returns the same
generic declaration records consumed by the policy runtime.

These choices belong to the investment model: strict gain threshold, minimum
holding period, sale-period operating income, forced final-horizon sale, and zero
holding/sale controls after disposal. Remove `policies/resale.py` and its generic
package export. Do not replace them with a strategy registry, runtime callback
system or a library-wide collection of resale presets.

Reuse RF-014's declaration identity and Flow-shape helpers from the model-local
factory. Preserve deterministic child IDs for a supplied policy ID and the
market-to-investment mapping contract. Keep authoring passive: it may inspect
declared shape but must not evaluate the price path to choose a sale, mutate
quantities, invoke a solver or load history. Keep strategy-specific tests with
the example and test generic runtime behaviour with direct policy declarations.

### Result composition and public boundaries

Retain `Observation` as a useful information boundary: only declared observed
quantities and the evaluation date reach rule evaluation, with no Model/store
handle. Normalize retained sequences to tuples and validate their element types
and date fields at the public construction boundary. A frozen dataclass alone
does not prevent a supplied list from being changed later.

Store only the ordered `DecisionOutcome` tuple in `PolicyResult`; derive its
`assignments` property by flattening outcome assignments in order. Remove the
independent assignment constructor argument so contradictory summaries cannot be
constructed. Do not recompute rules or read a Model to derive that property.

Remove `DecisionHistory`, which currently wraps a tuple without adding behaviour
or validation. Internal decision evaluation can consume the required prior-state
index and last-outcome information directly. Do not replace it with another
public wrapper unless an identified contract requires it. Keep runtime results
separate from authoritative schema records and numerical solve status.

Make the current standalone `decide()` operation internal to the validated
`evaluate()` path. Its existing public export accepts declarations that bypass
policy semantic validation: a direct call currently permits duplicate assignments
within one fallback, although `evaluate()` rejects that declaration. It also
uses assertions for required action fields. A public step-by-step evaluation API
is outside this intent; adding one later requires an explicit validation and
observation-provenance contract.

Retain a small pure decision kernel that selects the first true rule or fallback,
converts selected actions and returns one outcome. Validate externally supplied
declarations at the public boundary; use explicit failures for user-controlled
invalid data rather than relying on assertions. Compute selected termination once
instead of scanning the actions twice. Do not use internalization to excuse
invalid outcomes from the public evaluator.

### Evaluation preparation and composition

Compose the evaluator from a few focused operations, keeping chronological
orchestration visible:

1. Prepare the pinned Model scope, validate the policy declaration and build the
   scenario-availability evidence index once for this evaluation.
2. Resolve each declaration's observations from earlier control assignments or
   exogenous recorded quantities. Preserve declared order and each binding's
   availability checks.
3. Evaluate first-match rules against that Observation, construct an outcome,
   and append it atomically. Update prior assignment/date state only after the
   outcome passes the required local checks.
4. Stop on termination, validate the completed trace under its evidence contract,
   and return an immutable PolicyResult with derived assignments.

Maintain prior assignments and their decision dates incrementally. Remove the
per-declaration history-map reconstruction, repeated history scans in the decision
kernel, and reconstruction of a history wrapper on each iteration. Do not scan
all scenario provenance separately for each observed binding. The public
`observe()` operation may prepare its own context for standalone calls, while
`evaluate()` reuses one operation-local context through a small internal path.

Use RF-001's single availability rule and RF-009's shared scoped scalar access.
Retain the distinction between a prior assignment and an observed recorded Value:
a controlled target without an earlier outcome must not fall back to a recorded
control quantity. Declared availability may delay access, never advance it.
Preparation must not evaluate rules early or bypass time checks for later points.

Coordinate RF-006's reuse of validation scope with the pinned revision, units,
history and settings. Keep the standalone public `evaluate()` boundary validated;
do not add a public `trusted=True` flag, global cache or prepared context reusable
across different Model revisions. A few local mappings are sufficient; no
persistent policy engine or general pipeline is required.

**Confirmed correctness fix (G1).** The review constructed a control with a
recorded quantity and no earlier decision. Runtime evaluation rejected an
observation of it, but `specification/_policy_validation.validate_decisions()`
accepted corresponding stored evidence by falling back to the recorded quantity.
Enforce the controlled-target rule in both producer and evidence checks. Share
the pure ownership/timing rule, but do not validate evidence by rerunning public
evaluation. Add solver-free forged-outcome cases and cover both Run branches,
with and without published outputs. Moving the existing checker unchanged is not
acceptance of RF-001/RF-018/RF-019.

### Policy validation ownership and imports

Move shared declaration and recorded-outcome checks from
`specification/_policy_validation.py` to a lightweight policy-owned validation
module. Coordinate this move and removal of the `specification/policy.py` export
shim with RF-022's package consolidation; do not create another policy-check path.
Specification and Run remain their public validation coordinators and
supply the resolved scope and provenance needed by those checks. Policy evaluation
uses the same domain contracts without importing private Specification orchestration.
Remove the retired module after all callers migrate; do not retain a forwarding
layer. RF-003/RF-004 supply traversal and scope operations where needed.

Retain verification of stored outcomes against the pinned input, available
quantities, first matching rule, declared actions, dates, termination and exact
target coverage. This is a deliberate evidence boundary, not redundant checking
to delete merely because the producer performed similar work. Do not invoke the
public policy evaluator or a numerical solver to validate stored evidence.

RF-008 supplies policy-owned Boolean evaluation with exact truth and short-circuit
semantics, sharing only matching pure numerical arithmetic. Numerical residuals,
tolerances and solve acceptance remain independent. Any shared rule/action helper
must leave evidence/provenance verification intact; tests must use independent
expected results rather than asking the producer to validate itself.

Make `policies/__init__.py` lightweight under RF-001. Loading result types,
availability, predicates or pure checks must not load strategy authoring,
Specification orchestration, execution, solvers or optional numerical packages.
Keep policy capability errors available through a lightweight owner if sharing
them would otherwise pull in observation orchestration; do not add an error
hierarchy without a need.

Correct the `observe()` docstring: current period-only observations can derive
availability from the final included day, rather than always needing an explicit
date. Use RF-017's final Period field/timing names while preserving the actual
availability date. Scalars still require an availability source; unresolved
quantities remain errors, not zeros.

### Dependencies, deletion targets and implementation sequence

1. Establish independent declaration/outcome fixtures and import baselines.
   Inventory schema references, public consumers, private imports, resale factory
   callers, result construction and stored evidence.
2. Apply the paired record and field renames through generators and codecs;
   reconcile wire-version changes with RF-017 and enum generation with RF-002.
3. Move resale construction to the investment example with RF-014. Remove its
   generic export and module, preserving strategy semantics and identity fixtures.
4. Consolidate policy validation ownership and imports with RF-001/RF-008/RF-009.
   Keep Specification, Run and execution errors translated at their own boundaries.
5. Remove independent PolicyResult assignments and DecisionHistory, normalize
   retained sequences and internalize standalone decision evaluation. Compose the
   public evaluator around operation-local preparation and incremental prior state.
6. Migrate consumers, tests and documentation, then run focused and combined checks.

Affected code includes the policy package, `specification/policy.py`, Specification
validation, Run validation/publication/tree checks, execution preparation/results,
the investment example and its test facades, schema generators and generated
bindings, typing/install fixtures, active examples and
`docs/SCENARIOS_AND_POLICIES.md`. Audit all users of old `Decision` by meaning before
renaming; a textual replacement can silently confuse declaration and evidence.

Expect a net reduction in generic handwritten policy runtime through removing the
strategy, wrapper state, redundant result field and repeated preparation. Moving
resale to examples is not a repository-wide deletion: include the destination and
all consumers in size counts. Report necessary validation and migration growth
separately. Do not count generated renames or shorter identifiers as deleted logic.

### Verification and completion criteria

The earlier 2026-10-07 policy integration failure reported missing Pyomo and
did not reach its forged-evidence assertions. After the declared Pyomo/HiGHS
packages were installed, all 16 tests in the combined scenario/policy and market
selection passed. G1 was exposed by a separate solver-free probe and is not
covered by that pass. Re-establish both tests and probes at implementation.

Direct review probes also confirmed that standalone `decide()` accepted duplicate
targets within one fallback, PolicyResult accepted an assignment summary that
contradicted its decisions, and a list supplied to DecisionHistory remained
externally mutable. Normal validated evaluation rejects the malformed declaration;
do not present these probes as evidence that its normal producer emits such data.

Required checks include:

- Declaration/outcome record imports, generated language bindings, JSON/YAML keys,
  identity references, optional fields, order and explicit old-format migration
  or rejection. No old-name aliases or ambiguous Decision exports remain.
- First-true-rule selection, ordered fallback, atomic assignments, terminal action
  ordering, exact target coverage and rejection of duplicate control assignments
  both within one outcome and across outcomes.
- Availability from dates, periods, scenario evidence and explicit delays; future
  changes cannot alter earlier outcomes. Prior controlled assignments can become
  observations, but recorded controls cannot impersonate earlier decisions.
- Missing/unresolved quantities, scalar and Movement ownership, unit compatibility,
  invalid action/condition types, short-circuit behaviour and public error contracts.
- Tuple normalization and element validation, attempted mutation through input
  lists, immutable outcomes and assignment flattening in exact trace order.
- Fresh operation-local preparation for different revisions; evidence indexing
  once per evaluation without changing observation order or delaying failures
  past their correct boundary.
- Stored outcomes with forged availability, quantities, declaration/rule IDs,
  assignments, dates or termination. Retain independent expected evidence checks
  after the preparation optimization.
- Model-local resale thresholds, minimum holding, final-horizon fallback,
  sale-period income, later zero controls, explicit mapping and deterministic
  declaration IDs. Generic policy tests must also work without importing resale.
- Fresh-process import ordering for policy types/checks, Specification and Run
  validation, with no eager example, formulation or solver dependency.

Run `tests/test_scenarios_policies.py`, affected example/model, Specification, Run,
execution, retirement and typing tests, installed-package checks and applicable
combined checks from [Verification](VERIFICATION.md). Record unavailable platform
checks and pre-existing failures separately.

Completion requires distinct Decision declarations and DecisionOutcome evidence,
model-local resale construction, one source for result assignments, no history
wrapper or unvalidated public decision step, prepared observation evidence,
incremental prior state, policy-owned shared validation, preserved evidence and
numerical boundaries, migrated schema/consumers/guides and recorded verification
and size evidence. Implementation follows the explicit execution instruction.

### Implementation record

Implemented in the coordinated working-tree pass. `policies` is the policy facade. Decision is a declaration, DecisionOutcome is evidence, Policy.decisions and Report.outcomes use those meanings. PolicyResult stores an immutable outcome tuple with derived assignments.

Specification policy modules, public decide/DecisionHistory and the package resale recipe are removed. The resale recipe now belongs to examples.investment. G1 and the full policy trace checks remain independent. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-019 Simplify Run validation around prepared documents and explicit checks

### Architecture and agreed decision

The review covered all seven modules in `src/rangekeeper/run/` (893 lines at the
review baseline), plus Specification validation, execution, IO and conformance
callers. A Run records one finalized attempt: its Metadata, exact Specification
reference, direct spawned Runs, accepted output Model references and Report.
The Report contains status, runtime, diagnostics, policy outcome evidence and trace.

Keep the immutable Run facade and three checking responsibilities:

| Responsibility | Fact established |
| --- | --- |
| Local evidence | Status, outputs, runtime, diagnostics and trace agree within one Run |
| Resolved execution tree | Exact revisions, spawn ownership, batch case accounting, lineage and scoped references are consistent |
| Output conformance | Accepted output Models preserve permitted definitions, assignments, lineage and historical Claims |

Execution remains in `execution`; persistence remains in `io`. Run validation
does not schedule work, solve equations, select an optimum or prove that recorded
computation occurred. Keep `Run.from_data()` local and resolver-free, the absence
of `Run.revise()`, and the distinction between another execution and revision
lineage. This redesign changes validation composition, not the Run wire model.
RF-018's separate decision-evidence schema changes still apply.

### Observed duplication and review baseline

- `_resolve.collect_documents()` loads immutable domain objects, then exports
  dictionaries. `validation.validate_records()` passes those through `checked()`,
  which structurally validates, reconstructs a generated record that validates
  again, and exports it. The root is also in the Run catalogue and is prepared
  twice. Retain checks of newly supplied raw data; remove redundant reconstruction
  of the same prepared content within one validation operation.
- `Tree.visit()` composes a Specification before calling `validate_specification()`,
  which composes it again. Batch input-Model assertions walk descendants and
  compose the leaf Specifications again rather than consuming prepared results.
- `Tree.visit()` combines traversal, Specification checking, permitted failure
  handling, batch accounting, policy evidence, output checks and report references.
  The traversal is difficult to distinguish from the rules it coordinates.
- `Publication` owns input IDs, output IDs and producer ownership, although those
  are tree-wide facts. `Tree` directly modifies its `input_ids`. It does not publish
  anything, and its name overlaps with execution's candidate-publication module.
- Each output comparison deep-copies and normalizes the unchanged input Model
  again and rebuilds its historical-Claims mapping. Prepare those once per Run.
- `validate_report(batch=..., effective=None)` mixes intrinsic evidence rules with
  checks against effective settings, objectives and policy. Separate the additional
  resolved checks without creating a second implementation of local report rules.
- The executor imports `_report.completion_for()` and exports entire child Runs
  to read their completion states. `schema/checks/runs.py` imports `_tree.Tree`
  directly. These consumers need intentional shared interfaces.

Read-only instrumentation on 2026-10-07 measured these calls during one public
validation operation, after fixture construction/storage had finished:

| Fixture | Top-level Run/Model/Specification schema validations | Specification compositions |
| --- | --- | --- |
| Forward Run | 12 | 2 |
| Batch with two leaf Runs | 22 | 6 |

`tests/test_domain_run.py` passed 23 tests during that review. These are measured
baseline observations, not acceptance of the redesign or a claim that all Run/IO
conformance checks were run. Recheck the implementation checkout before changes.

### Intended package and ownership

```text
run/
  __init__.py       public exports
  run.py            immutable facade and local construction boundary
  report.py         local evidence rules, resolved report checks, batch completion
  validation.py     preparation, exact dependency resolution and Run traversal
  outputs.py        output-conformance operations; no publication or tree state
```

Retain the small facade. Move `_report` to `report`, fold `_resolve` and `_tree`
orchestration into `validation`, and replace `_publication` with `outputs`.
No old-module forwarding aliases are planned. File count falls from seven to five;
the principal simplification must also be visible in state ownership and call flow.
Removing underscores or concatenating the existing code is insufficient.

Use one small internal owner for the state of a validation call: resolved exact
documents, reusable Model/Specification results, active and completed Runs,
parent ownership, used Model revisions and output producers. This replaces the
state divided between Tree and Publication. Do not add a general validator class
hierarchy, plugin registry, global cache or persistent validation service.

Reuse RF-006's prepared representation and RF-003–RF-005's scope/index results.
Retain canonical typed records where available. If lower-level checks still need
a mapping projection, prepare it once and share it without mutation; do not
alternate between dictionaries and reconstructed records at each stage. Reuse is
scoped to exact content, kind, revision, scope, UnitSystem and applicable settings.
Reject conflicting content before using revision IDs as cache keys.

### Preparation and explicit traversal

Keep both existing entry points:

- `validate(run, resolver=..., units=...)` collects exact immutable dependencies.
- `validate_records(run, runs=..., specifications=..., models=..., units=...)`
  prepares raw conformance catalogues and generated records.

Both converge on one semantic pipeline after preparation:

```text
Prepare supplied records
  -> resolve/check exact dependency revisions
  -> prepare or reuse Model and Specification results
  -> check spawned Runs before their parents
  -> check reports, outputs and scoped evidence
  -> finish tree-wide lineage and identity checks
  -> return ValidationReport
```

Dependency collection and Run traversal are intentionally different operations.
The dependency graph includes Specification includes/cases, pinned Models, outputs
and scoped report documents, including documents outside the spawn tree. Preserve
that closure and the existing treatment of raw catalogue extras; do not validate
only successful leaves or silently ignore structurally malformed supplied entries.
Previous revisions need not be loaded solely because a predecessor is named.

Insert the in-memory root once after checking any supplied duplicate has identical
kind/content. Continue checking resolver-returned kind and identity. Preserve
missing/wrong-kind/wrong-identity diagnostics, absent optional fields, source paths
and structural-error gating. A failed attempt still requires referenced documents
to resolve. A structurally valid generated RunRecord is not automatically a
locally valid Run facade; perform its required local semantic checks.

Composition and Specification validation must share the existing Composition
instead of rebuilding it. RF-022 owns that result and the shared Specification
catalogue; consume its preparation rather than adding a Run-specific replacement.
Retain both Model-only and composed mathematical scopes:
report participant references restricted to the input Model must not gain access
to Specification-local declarations. Reuse RF-004's declaration index for scoped
target membership, excluding opaque content, and RF-009's scalar access.

Make child checking return or retain the small result needed by its parent:
completion, accepted outputs and composed input-Model pins. Batch assertions then
consume those results without a second descendant walk or composition. Preserve
the distinction between composition failure and later semantic failure: a composed
input-Model pin still participates in a batch assertion when later Specification
validation fails. Do not discard it merely because the leaf is not assessed.

Use cohesive operations for a leaf attempt, batch accounting, report context and
scoped references. Keep prerequisite order visible. Do not replace the large
`visit()` with a collection of trivial forwarding methods or unconditional stages
that run without their required scope. Catch expected contract failures only where
the Run contract permits recording them; programming and unexpected resolver
failures must not be reclassified as a valid failed attempt.

### Report and output checks

In `report.py`, share one implementation of intrinsic report/status rules between
construction and explicit validation. Resolved checks add agreement with effective
settings, policy presence, objective-selection evidence and actual batch kind.
Local construction may infer aggregate intent from `not_applicable`; resolved
validation must still confirm the Specification is a batch. Retain required runtime,
timezone-qualified trace ordering, diagnostics, residual/tolerance and skipped-Run
rules. Avoid repeating local checks once their equivalent result has been prepared
within the same operation; no persistent trusted/validated flag is introduced.

Change the shared batch-completion operation to consume completion statuses, not
serialized Runs. For example, the executor supplies
`child.report.status.completion` for each child. Preserve the existing precedence
for completed, partial, failed, limited, cancelled and skipped outcomes; do not
replace it with a guessed severity ordering. Use RF-002's canonical enums and
define iterable/empty-input behavior explicitly without allowing an empty child
set to bypass actual batch case-accounting rules.

In `outputs.py`, use checking functions with explicit input, output, prepared
requirements and scopes. Prepare allowed change targets, the invariant input
definition, assignments including checked policy outcomes, and historical Claims
once per producing Run. Reuse each selected output's own prepared Model scope.
Check every output against that input preparation. Reuse target reads where their
revision and unit context are identical. Keep producer uniqueness and used-model
sets in the traversal owner; output functions do not mutate external tree state.

The existing definition comparison is allowed to ignore Metadata/provenance and
only the specifically permitted numerical/evidence fields. Preserve its exact
allowlist, unrelated recorded content, Flow shape, IDs and opaque content. Do not
replace it with a broad equality rule that ignores all quantities or evidence.
Preserve historical Claim contents and required finite, resolved output quantities.

**Confirmed correctness fix (G2).** The current historical-Claim check compares
plain dictionaries. A review probe changed an input Claim's content from `0` to
`False` in the output, retaining its UUID, and public Run validation accepted it.
Use RF-020's type-sensitive, order-preserving equality for immutable historical
Claims. Cover numeric types, signed zero, field presence and ordered opaque
content. Keep this separate from the permitted-output-field mask and from schema
equivalence; neither authorizes changing historical evidence.

Raw conformance defaults compare assignments strictly. Public validation supplies
an explicit UnitSystem for conversion to output units; conversion does not imply
numerical tolerance. Keep both contracts intentional and retain invalid-unit
handling that allows properly evidenced failed/not-assessed attempts.

Validate recorded policy outcomes through RF-018's shared policy checks and
RF-008's predicate implementation. Retain the branch rules for outputs, no outputs,
recorded decisions and not-assessed outcomes. Preserve independent checks of
observations, availability, first matching rule, actions and termination; do not
trust executor-produced evidence or run a new policy investigation. Coordinate
Decision/DecisionOutcome names and report fields with RF-018 instead of inventing
a Run-specific outcome representation.

### Preserved boundaries, diagnostics and exclusions

- Spawn edges, revision lineage and Specification inclusion/case edges remain
  distinct. Reject spawn cycles, repeated spawning parents and lineage misuse.
  Each direct batch case has exactly one child Run; a repeated case along different
  paths still requires distinct Run identities. Batch outputs equal the child union.
- Outputs have one producer within the tree, cannot be the input revision, and
  must name the input as predecessor. Preserve document/declaration identity
  collision checks. An output can be a later Run's input where the existing
  contract permits it; producer ownership is not a ban on downstream use.
- A failed, cancelled or skipped not-assessed Run can record an invalid investigation
  with the required diagnostic. Do not force all recorded attempts through the
  requirements for a successful numerical conclusion.
- Scoped diagnostics/trace targets belong to the named revision. Participant
  references require the valid input-Model scope under the existing rule. Cache
  membership only for the matching immutable revision and applicable scope.
- Preserve the IO snapshot boundary, fresh resolver context per independent call,
  store validation before publication and rechecking of idempotent Run puts.
  Independent numerical acceptance must continue to check original requirements
  against reconstructed candidates. These are not redundant preparation stages.
- Do not add scheduling, live progress, solver execution, feasibility certification,
  new publication capabilities, storage transactions or implicit history loading.

Where semantic checks currently produce only a root-level generic contract error,
carry the offending Run/document and field path through the existing Issue and
ContractError mechanism. Preserve referenced-document scope separately from the
location of the malformed evidence. Improve child/field attribution without
adding a parallel diagnostic framework or broadly catching programming errors.

### Dependencies, deletion targets and implementation sequence

1. Record semantic, representation and size baselines. Cover all seven modules,
   constructor/resolver/raw paths, executor consumers and schema conformance imports.
2. Establish shared prepared Model and Specification interfaces with RF-003–RF-006,
   and scoped identity/scalar access with RF-004 and RF-009. Do not create a second
   Run-only scope or record preparation abstraction.
3. Consolidate dependency collection and preparation in `validation.py`. Route both
   entry points into the same semantic checks and remove root double preparation.
4. Establish one traversal state owner and consume prepared child results for batch
   checks. Remove repeated Specification composition and unnecessary Model analysis
   while keeping base/composed scopes separate.
5. Separate local/resolved report stages, migrate the completion-status helper and
   replace Publication with explicit output functions. Hoist invariant input work
   out of output loops. Integrate RF-018's policy evidence interface.
6. Migrate `execution/executor.py`, schema conformance scripts and affected tests,
   imports, package exports, typing/install fixtures and guides. Schema checks
   should use the supported raw-catalogue boundary, sharing the semantic core;
   replace direct Tree access and preserve coverage of expected failures. The
   package facade need not expose every internal helper merely because its module
   has a clear non-underscore name.
7. Run focused and combined checks, record call-count/size evidence and update
   `docs/RUN_AND_STORAGE.md`, `docs/LIBRARY_ARCHITECTURE.md` and verification guidance.

Delete `_resolve.py`, `_tree.py`, `_report.py` and `_publication.py` after migrating
their callers; retain their necessary rules in the agreed owners. Remove the old
Tree and Publication orchestration, child serialization for completion, repeated
composition, repeated input definition/Claim preparation and duplicate structural
round trips. Do not add compatibility files under the old paths.

Expect a net reduction in handwritten implementation and two fewer package files.
Count the replacement state owner, functions and all external caller changes;
moving logic into Specification or policy helpers does not count as deletion.
Justify any net growth needed for improved diagnostics or an explicit preparation
contract and assess it against the combined plan's reduction requirement.

### Verification and completion criteria

Use independent expected outcomes and meaningful call-count checks to verify:

- Local construction, generated-record/raw input and resolver-backed validation
  retain their distinct prerequisite and error contracts; inputs remain unchanged.
- Supplied roots and dependencies prepare once for the applicable context; conflicting
  content/kind cannot enter a cache. A later validation call resolves afresh.
- Each applicable Specification composition is reused through leaf validation and
  parent assertions. Failed composition is distinguished from later invalid roles.
- Base Model scope and combined Specification scope stay distinct. Many repeated
  report references do not trigger repeated scope preparation or cross-revision
  target leakage.
- Status/runtime/diagnostic/trace rules, nested batches, every completion state,
  missing/duplicate cases, shared children, cycles and predecessor rules remain
  enforced. Raw catalogue extras retain the intended validation contract.
- Missing references, wrong kinds, wrong returned UUIDs, report documents outside
  the input tree, identity collisions and malformed child evidence give appropriate
  diagnostics and do not become successful not-assessed fallbacks.
- Multiple outputs share input preparation but are independently checked for
  producer uniqueness, lineage, permitted changes, finite quantities, assignments,
  unit conversion and retained Claims. A later Run can consume a valid prior output.
- Recorded policy outcomes are independently checked with and without outputs;
  tampered observations, chosen rules, actions and termination remain rejected.
- Failed publication leaves stores unchanged; idempotent puts still validate;
  loading/constructing a Run does not execute it. Solver acceptance remains
  independent of report and output-conformance checks.

Run `tests/test_domain_run.py`, affected `tests/test_domain_io.py`, execution,
temporal and scenario/policy tests, and `schema/checks/runs.py` in its supported
environment. Run applicable typing, import, installed-package and combined checks
from [Verification](VERIFICATION.md). Report environment limitations rather than
presenting the 23-test review baseline as complete acceptance. Compare preparation
and composition counts under equivalent fixtures; do not remove required boundary
checks merely to reach a lower count.

Completion requires one prepared semantic pipeline, one traversal-state owner,
explicit report/output operations, preserved failure/provenance/scope contracts,
migrated executor and conformance callers, removed obsolete modules/classes,
passing applicable checks and recorded reduction evidence.

### Implementation record

Implemented in the coordinated working-tree pass. `run.report`, `run.outputs` and one prepared resolver-backed validator replace the old tree/resolve/publication/report modules. Outcome validation reads the input scope with the caller unit context.

Historical Claims use exact type-sensitive, order-preserving content comparison. G2 covers integer/Boolean/float differences, nested values, list order and field presence. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-020 Integrate record equivalence and simplify revision comparison

### Problem and ownership

`_comparison.py` combines two responsibilities.
`canonical()` builds a schema-directed comparison key for revisions, Model diffs
and storage conflict checks. `check_revision()` enforces document kind, lineage,
schema-version and meaningful-change rules for Model and Specification revisions.
Both behaviours are required; their current placement is not a reason to retain
the repeated copying and conversion around them.

The current comparison copies an exported subtree at each recursive record and
copies slot metadata through `slots_for()`. Model diffing then parses the returned
JSON back into data. It also exports and reconstructs each Model to build indexes
that the validated Model already holds. These are observed source paths, not
measured performance results.

Put schema-aware equivalence in the existing record layer. Keep revision policy
at the document boundary, shared by both `revise()` methods. Comparison performs
no unit conversion, numerical evaluation, reference resolution, IO or history
lookup. A normalized comparison structure is derived data, not a new wire format
or persistent content hash.

### Intended implementation

Expose `Record.equivalent(other)` through
[`_records.py`](../src/rangekeeper/_records.py). The record supplies its own schema
kind and immutable content. Require the same concrete record type and compare all
recorded content, including identities. Keep existing `Record.__eq__` behaviour
unchanged: it preserves collection order. Do not silently replace equality in
unrelated callers with schema-aware equivalence.

Use one internal normalization implementation for equivalence, revision checks
and diffing. Build its comparison structure in one pass without mutating `_data`
or repeatedly copying whole subtrees. Reuse immutable generated slot metadata.
Share existing record traversal mechanics only where that reduces the complete
implementation; do not add a visitor hierarchy or general comparison framework.

Give [`model/diff.py`](../src/rangekeeper/model/diff.py) direct access to the
normalized structure, removing the whole-document JSON encode/decode round trip.
Use the Model's existing validated index through the internal access boundary
agreed with RF-004 and RF-006. Preserve added/removed/modified UUID reporting,
Metadata exclusion from declaration changes, JSON-pointer escaping and the
existing canonical ordering used for change paths. Reordering comparison output
could change those paths even when equivalence remains correct.

Let [`io/_document.py`](../src/rangekeeper/io/_document.py) delegate equivalent
record comparison to this implementation, retaining document-kind checks and
`RevisionConflictError`. Preserve snapshot reconstruction, validation, exact
revision resolution and conflict-safe publication. Those IO checks establish a
separate boundary; this item only removes redundant comparison work.

Retain one shared revision guard called by Model and Specification. It checks:

- The document type is unchanged.
- The new UUID differs from the current UUID and its known immediate predecessor.
- The new `previous` equals the current revision UUID.
- The schema version is unchanged; `revise()` is not a migration operation.
- Content differs after excluding only the root Metadata `id` and `previous`.

Descriptive changes, such as a Metadata name, remain valid revisions. Identity-only
changes and schema-unordered reordering remain invalid. Do not remove nested
identities from comparison. The guard checks the supplied pair and does not claim
global historical UUID uniqueness. Complete candidate validation remains the
owning document's responsibility; Run gains no revision method.

Classify each comparison caller before migration. Stored-revision conflict checks
use schema equivalence; historical Claim preservation under RF-019 uses exact,
type-sensitive ordered equality; output-definition checks retain their explicit
allowlist. The review reproduced `0` to `False` Claim changes passing Run
validation under plain dictionary equality. Fix that caller rather than merely
moving the comparison implementation.

Include `model.flow.Stream.merge()` in the audit: its current `to_data()` dictionary
comparison copies both Models and loses scalar-type distinctions. Retain its
order-sensitive same-revision/content contract using strict record equality,
with a safe same-object shortcut. Do not substitute schema equivalence in graph
callback or pinned-view checks without establishing their intended contract.

### Behaviour to preserve

| Difference | Required comparison result |
| --- | --- |
| Mapping key order or schema-declared unordered collection order | Equivalent; retain original encounter order in exported and stored documents |
| Ordered expression operands, Movements, objectives or trace steps | Order remains significant |
| Lists inside opaque Claim content | Order and repeated elements remain significant; do not interpret content as schema records |
| Duplicate collection elements | Preserve multiplicity; do not normalize through a set |
| Absent field, explicit null or empty collection | Remain distinct |
| `0`, `0.0` and `False` | Remain distinct; ordinary Python container equality is insufficient |
| Other numerical representations, including signed floating zero | Preserve the distinctions made by the existing serialized comparison |
| Different record types, identities, units or recorded magnitudes | Remain different; mathematical or unit equivalence is outside this operation |

Preserve Unicode strings and existing sort-key ordering. A comparison structure
must retain the current type-sensitive semantics; replacing serialized comparison
with plain dictionary equality would weaken them. Choose the smallest mechanism
that preserves these rules. JSON encoding of individual sort keys or scalar
comparison tokens can remain where needed; eliminating the whole-document round
trip does not require a new general-purpose encoding system.

### Dependencies, deletion targets and W1 representation choices

Coordinate record access with RF-002: enum fields still compare through their
stored wire values, and omitted/null/empty distinctions remain intact. Reuse
RF-004's record index and RF-006's revision-local access rules. Coordinate with
RF-019 without removing independent storage validation. Graph callback checks in
RF-012/RF-013 must retain their own exact revision and ownership contracts; do not
substitute `equivalent()` solely because it is available.

Finalize the internal normalization shape and shared record/index access in
W1. Keep the document revision guard in one small `_revision.py` module shared
by Model and Specification. It needs complete documents and does not belong on
every nested Record or Metadata. Keep normalization in the record layer and
remove `_comparison.py` after all callers migrate. No document base class or
parallel revision guards are needed.

Delete the old canonicalization path, recursive deep copies, copied slot metadata,
diff JSON round trips, reconstructed diff indexes and repeated caller comparison
plumbing. Retire `_comparison.py` after both responsibilities have clear owners
and all callers have migrated. The retained `_revision.py` helper has the
explicit document-pair contract above; file-count reduction alone is not success.
Keep no forwarding alias or parallel comparison implementation.

Update current domain, record and storage guides, typing/install checks and
[`workflow/implementation.py`](../src/rangekeeper/workflow/implementation.py)'s
module fingerprint inventory when paths change. Preserve data fingerprints and
wire contracts; source implementation fingerprints may change. Keep schema
version changes required by other intents separate from this behaviour-preserving
refactor. Measure net handwritten changes across the record layer and every caller.

### Verification and completion criteria

Establish focused baselines in `test_records.py`, `test_record_behavior.py`,
`test_domain_model.py`, `test_domain_specification.py` and `test_domain_io.py`.
Add missing cases from the comparison table. Verify both directions of equivalence,
unchanged strict `==`, descriptive versus identity-only revisions, lineage/version
rejection and unchanged inputs after successful or failed comparisons.

Compare diff outputs, including paths, against representative existing results.
Exercise nested unordered collections, ordered mathematics, opaque content,
duplicate elements, type-sensitive values and non-ASCII sort keys. Confirm that
diffing an existing Model does not rebuild its validated index or reconstruct the
root document. Preserve the first stored representation on an equivalent write
and reject changed content under the same UUID in both stores.

Run applicable typing, installed-package, import and regression checks from
[Verification](VERIFICATION.md). Check that normalized data cannot mutate the
source record and that comparison imports no solver or optional numerical package.
Use focused call counts or profiles to substantiate reduced work; do not infer a
speedup from file consolidation or promise one without measurement.

Completion requires one shared record-equivalence implementation, direct diff
consumption of normalized data, reuse of validated indexes, one shared revision
guard, migrated callers, preserved comparison/storage contracts, passing checks
and the reduction evidence required by the overall strategy.

### Implementation record

Implemented in the coordinated working-tree pass. `_records.py` owns exact ordered comparison and schema equivalence. Model and Specification use `_revision.py` for lineage and meaningful-change checks; stores use schema equivalence for repeated writes. Stream.merge checks its Model pin and strict ordered record equality. Graph callback/revision checks also retain strict comparison; they do not use the document revision guard.

`_comparison.py` is removed. Exact evidence preservation is not replaced by unordered equivalence; tests retain both contracts. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-021 Consolidate scenario mechanics and market contracts with explicit replay provenance

### Problem and decision

The review covered all eight modules in `src/rangekeeper/scenarios/`, associated
Model conformance, market-naming migration and active consumers. Sampling,
recording supplied inputs, deterministic realization and replay are useful
separate operations. Retain those boundaries while consolidating their shared
preparation and record construction.

The package's general-looking surface currently implements three market methods.
Even the independent method samples space factors and capitalization rates.
Parameter defaults, inventories, input shapes, output lengths and observation
delays are repeated across `plan.py`, `components.py`, `market.py`, `_paths.py`
and `model/_scenario.py`. Make the market ownership explicit without introducing
a generic scenario framework to justify the package name.

Use stable method identifiers, separate calculation implementation provenance,
and content-sensitive realized revision identity. This supersedes the earlier
RF-002 example of retaining `market.v2` as the active method name; method identifiers
remain strings rather than enums.

### Stable method names and provenance responsibilities

| Current recorded method | Replacement | Meaning |
| --- | --- | --- |
| `market.v2` | `market` | Market calculation with direct cycle parameters |
| `market.estimates.v2` | `market.estimates` | Market calculation with linked cycle estimates |
| `independent.v2` | `market.independent` | Independent space-factor and capitalization-rate sampling |

Separate these recorded concerns:

- Method selects the calculation and its parameter/input/output contract.
- Document schema version describes the stored representation and its migration.
- Sampling provenance records generator, seed, stable component streams and
  relevant dependency versions.
- Calculation provenance identifies the implementation that realized outputs.
- Captured inputs and outputs remain the inspectable numerical evidence.

Keep the existing generator information about sampling; it must not stand in for
calculation identity. Use one reliable implementation identifier tied to released
or built code, with relevant calculation dependency evidence. Do not scatter
manually maintained method-version constants through modules or label modified
source as the same implementation merely because its package version is unchanged.

Add an optional `ScenarioRealization.calculation` record in the scenario
schema. Its compact CalculationProvenance contains `name` (implementation
identifier), `fingerprint` (versioned digest) and `versions` (existing LibraryVersion
records for relevant calculation dependencies). New realized outputs require it
at their producer boundary. Captures before calculation and explicitly migrated
legacy results may lack it; absence is an inspectable provenance limit and makes
exact replay unavailable. Do not invent a historical fingerprint. This is not
a solver Implementation record. Generate all affected Python/C# bindings.

Use a deterministic fingerprint of the declared calculation source/dependency
manifest, including relevant schema and numerical dependency versions. Share
only pure source-digest/manifest-encoding mechanics with workflow and execution
where their contracts match. The owning subsystem retains its inclusion policy
and provenance record. Test source changes under an unchanged package version,
and verify that the same installed code/dependencies produce the same identity.

For the three supported market methods, set CalculationProvenance.name to
`rangekeeper.scenarios.market`. Set its fingerprint to
`scenario-calculation/v1:<digest>`, where `<digest>` is the lowercase SHA-256 hex
digest of the following manifest encoded as UTF-8 compact, sorted-key JSON with
`ensure_ascii=True` and nonfinite numbers rejected:

- `format`: `scenario-calculation/v1`.
- `name`: `rangekeeper.scenarios.market`.
- `sources`: mapping of package-relative POSIX paths to semantic source digests,
  using the existing executable-AST digest contract without comments/docstrings.
- `resources`: mapping of package-relative POSIX paths to SHA-256 file-byte digests.
- `versions`: LibraryVersion-shaped objects with `name` and `version`, sorted by
  unique name; include Python and relevant calculation dependencies. Store this
  same ordered list in CalculationProvenance.versions.
- `currencies`: the sorted currency-code list from the immutable unit catalogue;
  fingerprint the actual supported codes as well as the supplying dependency version.

The [fingerprint inclusion rules](#fingerprint-inclusion-rules) define the scope.
W1 records the exact final path/dependency list after module placement is fixed;
missing listed inputs fail fingerprint construction. Do not include timestamps,
absolute install paths, sampling state or presentation assets. Python's recorded
version makes changes in the AST encoding environment explicit. Freeze a manifest
and digest fixture so source and installed-wheel calculations use the same rule.

Stable method names do not authorize silent changes to their mathematical meaning.
Different supported mathematical definitions must remain distinguishable. The
refactor preserves the three existing calculations; support for historical
implementation execution is a separate capability, not a promise made by a suffix.

### Shared method contracts and market authoring

Define each supported method once through lightweight immutable metadata:

- Parameter names, defaults and applicable constraints.
- Scalar versus per-period captured inputs.
- Output names and lengths relative to the declared horizon.
- Forward-dependency offsets used for observation availability.

Use these definitions from market authoring, input capture and Model conformance.
Keep numerical functions separate from metadata. Do not introduce a dynamic
plugin registry, callback catalogue, arbitrary implementation loader or method
subclass hierarchy. Preserve exact method selection; replace scattered prefix
tests and inventory copies with the shared definitions where contracts match.

Model validation must remain able to check recorded provenance without importing
generators or numerical execution. Choose a lightweight contract owner and package
initialization that enforce this dependency. Share structural facts and matching
checks, not an invocation of scenario generation from a validator. RF-006 retains
Model/provenance validation orchestration; RF-009 supplies scoped target access.

Consolidate `plan.py` and `components.py` around one conversion from numbers,
Quantities and Distributions into ScenarioParameter records and one source of
defaults. Keep named component helpers only where they clarify construction;
describe them as parameter groups, not independently composed simulation stages.
Reject duplicate explicit declarations and retain deterministic parameter order.

Expose market-specific plan authoring through `scenarios.market`. Keep defaults,
parameter groups, path composition and the Market view under clear market
ownership. Project-specific calibration remains in model construction. Inventory
and remove misleading or redundant package-level authoring exports without adding
forwarding compatibility functions. Finalize exact module placement after tracing
imports; moving every helper to a separate file is not the goal.

Validate invalid fixed parameters during plan preparation. The review confirmed
that public plan validation accepts negative fixed volatility and zero fixed cap
rate, although the calculation cannot accept those inputs. Share the applicable
constraints with captured-input checks. Recheck sampled values and combinations
once their actual values are known; valid distribution support alone does not
prove that every resulting market path is valid.

### Shared capture, realization and dispatch

Retain these distinct operations:

| Operation | Responsibility |
| --- | --- |
| `sample()` | Draw inputs from deterministic component streams and record them |
| `capture()` | Record supplied inputs without drawing randomness |
| `realize()` | Calculate outputs from captured inputs |
| `replay()` | Verify stored outputs against captured inputs without redrawing |

Make sampling and supplied-input capture converge on one recording path. Share
input normalization, Value/Movement construction, shape validation, provenance
assembly and revision construction where their contracts match. Preserve the
difference between generated and supplied evidence and the order of streams,
bindings, parameters and movements. Avoid a new public intermediate wrapper
unless it replaces identified state or establishes a required boundary.

Keep pure known-input path composition separate from sampling and publication.
Retain existing characterized calculation kernels. Periodic path generation must
not draw additional randomness, mutate Models, choose policy actions, invoke a
solver or write a store. Construct publication records from complete validated
outputs and their availability information.

Use one in-process generation operation. The sequential branch of `generate()`
calls it directly on immutable records. Only the multiprocessing adapter exports
and reconstructs records at the process boundary. Prepare base Model and plan
payloads once where possible, rather than serializing them independently for every
key. Preserve detached process payloads, spawn behaviour, supplied key order and
identical results regardless of worker count or dispatch order.

Reuse plan preparation within the matching operation under RF-006. Do not remove
validation of independently supplied capture documents or process-boundary data,
add a public trusted-input switch, or retain cross-revision caches merely to reduce
calls. Consolidate scenario-key argument checks so sample/capture/generate reject
invalid inputs consistently.

### Realized revision identity and replay

The current realized Model revision UUID depends on captured draws, not the
realized output content. A controlled review probe changed path calculation while
keeping the captured document fixed and obtained different Model contents with
the same revision UUID. This demonstrates exposure to implementation changes,
not disagreement between ordinary calls to an unchanged deterministic function.

Construct the complete candidate wire document first, including final root
metadata, predecessor, captured inputs, realized outputs and calculation
provenance. Exclude only `/metadata/id` from the identity payload. Retain all other
fields, nested identities, field presence and collection order. Encode it as
UTF-8 JSON with `ensure_ascii=True`, `sort_keys=True`, separators `(',', ':')`
and `allow_nan=False`. Take the lowercase SHA-256 hex digest of those bytes.
The root identity is `uuid5(realization.id, 'realized-model/v1:' + digest)`, with
the stable realization record UUID as the namespace. Freeze
encoding/identity fixtures before migrating callers. Do not use schema equivalence
as the hash projection or strip all metadata/provenance.

Nested declaration and Movement IDs remain derived from stable input/realization
identities, not the newly hashed root UUID. Do not introduce a self-reference
cycle or silently remove additional fields to break one. Preserve predecessor
links and immutable storage semantics. Validate the final candidate and retain
RF-020's revision guard after assigning the derived root identity.

Replay must:

1. Resolve the selected recorded realization and its captured inputs.
2. Establish whether its recorded calculation implementation is supported.
3. Recompute from those inputs without sampling.
4. Compare recomputed mathematical paths with recorded paths and return the same
   immutable Model on success.

Distinguish unavailable/unsupported calculation implementations from numerical
mismatches and invalid captured data. Current-format stored results must remain
readable when their replay implementation is unavailable. Old-format documents
follow the agreed explicit-migration policy; old Runs retain their original pins
and require matching older tooling, not a new multi-version canonical reader.
Separate record conformance from runtime capability; do not weaken structural
validation or execute arbitrary code
named by provenance to make replay succeed.

Retain replay's explicit mathematical comparison scope: Movement IDs and Claims
are excluded from that comparison to support deliberate historical upgrades.
Their identity and provenance constraints remain subject to normal Model
validation. Do not replace exact numerical replay with a content-ID check, or
mistake mathematical agreement for proof that the recorded provenance is correct.

### Explicit migration and behaviour to preserve

Removing `.v2` changes recorded data and identity inputs. Supply an explicit
migration for the old method identifiers and parameter/output naming lineage;
do not treat this as a cosmetic Python rename. Integrate with the existing
`migration/scenarios.py` path where appropriate and coordinate schema/version
changes with RF-017 and RF-018.

Preserve historical documents and Runs unchanged. A migrated document is a new
revision with explicit lineage. Preserve captured draws, declared identities,
references, values, order, field presence and availability dates. Do not regenerate
scenarios or recompute historical paths as a substitute for migration.

Retain random-stream labels and the seed derivation algorithm exactly. In
particular, the internal legacy `volatility` stream label must not become
`volatility_per_period` merely because that is the public parameter name. Such a
rename changes seeded draws. Test stream identities independently of public
method labels and parameter naming.

Do not invent exact calculation fingerprints for old records that lack them.
Record the known legacy method contract and provenance limitations explicitly.
Any supported legacy replay path must be deliberate and verified; otherwise
report that replay is unavailable while retaining usable stored results.

Retain the revision-pinned Market view and its explicit named accessors over
canonical Values. They provide discoverability and do not duplicate path data.
Avoid dynamic attribute lookup or copied arrays as a replacement. Keep incomplete
captures distinct from realized results, non-finite/unresolved input rejection,
dimensionless market contracts and future-dependent observation delays.

### Dependencies, deletion targets and implementation sequence

1. Freeze independent method, seeded-draw, stream, identity, availability and
   replay fixtures. Inventory active callers and recorded migration cases.
2. Define lightweight contracts and consolidate market authoring. Remove duplicate
   parameter/default conversion and input/output inventory declarations.
3. Define calculation provenance and result-content identity, update schema and
   generated bindings, and prepare the explicit method-name migration.
4. Consolidate input recording and deterministic realization. Replace sequential
   process-style serialization with the direct in-process path; retain the narrow
   process adapter for parallel dispatch.
5. Apply replay capability checks and migrate Model conformance to shared contract
   metadata without numerical imports. Preserve RF-001/RF-018 policy availability
   and RF-016/RF-017 date semantics through independent fixtures.
6. Migrate active imports, names, examples, typing/install fixtures and guides;
   run focused and combined verification and record size changes.

Affected code includes the scenario package, `model/_scenario.py`,
`model/scenario.py`, `schema/scenario.yaml`, generated artifacts, scenario migration,
investment/probabilistic examples and test facades, `docs/SCENARIOS_AND_POLICIES.md`
and the upgrade guide. Keep replay comparison separate from RF-020's general
record equivalence where their field-presence or identity requirements differ.

Deletion targets are repeated conversion/default definitions, scattered method
inventories and dispatch facts, duplicated capture preparation, repeated payload
exports, and sequential serialization/reconstruction. Retire superseded modules
and active `.v2` branches after migration; retain historical evidence and explicit
migration recognition. Do not count moved market code as deletion.

Target lower handwritten duplication and execution overhead across all callers.
Calculation provenance, identity protection and explicit migration can require
additional code; account for that separately and justify necessary net growth
under the overall strategy. No general scenario plugin framework is in scope.

### Verification and completion criteria

The final 2026-10-07 review baseline ran `tests/test_market_naming.py` and
`tests/test_scenarios_policies.py` with the declared Pyomo/HiGHS packages: all 16
tests passed, with no excluded policy integration case. This supersedes the
earlier 15-pass/one-deselected baseline caused by missing Pyomo. It is not
acceptance of this refactor; rerun affected checks in the implementation checkout.

Verify with expected results independent of the shared method definitions:

- All three methods preserve characterized outputs, direct/estimated cycle
  semantics, independent market sampling and output lengths.
- Parameter groups equal explicit declarations, defaults have one source,
  duplicates/unknown inputs fail, and invalid fixed parameters fail early.
- Seeded draws and stream labels remain unchanged; worker count, dispatch order
  and unrelated component streams cannot perturb existing draws. Sequential and
  parallel results must be identical.
- Supplied-input capture, realize and replay make no random calls. Missing, extra,
  reordered, non-finite, out-of-support and wrongly sized captured inputs fail.
- Same inputs and implementation produce the same result revision. A changed
  output or relevant implementation provenance cannot reuse that revision ID.
  Check both mathematical content and immutable-store conflict handling.
- Replay detects altered numerical paths and distinguishes unsupported
  implementations. Missing replay capability does not prevent reading valid
  stored results. Claims/ID exclusions do not weaken normal provenance checks.
- Explicit old-name migration preserves draws, identities, availability, field
  presence and historical source documents without resampling. New provenance
  must not pretend to establish an unavailable historical implementation identity.
- Forward ratios remain unavailable until their later inputs; boundary renames
  and month-end changes must not silently shift recorded availability.
- Market access stays revision-pinned and returns canonical Values. Contract and
  conformance imports do not load numerical generation or optional backends.
- Sequential dispatch avoids detached process round trips while parallel dispatch
  continues to use only supported detached payloads.

Run affected scenario, market-naming, Model/provenance, migration, example,
policy-availability, typing and installed-package tests, then applicable combined
checks from [Verification](VERIFICATION.md). Record independent numerical and
seed fixtures, required environment limitations and code-size evidence.

Completion requires stable method names, distinct calculation provenance, one
source for method contracts/defaults, shared capture construction, a direct
sequential path, content-sensitive result identity, explicit migration and replay
capability handling, preserved recorded mathematics and seeded draws, migrated
consumers/guides and passing checks. No implementation is authorized by this entry.

### Implementation record

Implemented in the coordinated working-tree pass. `scenarios.contracts` owns immutable inventories; `market` owns plan authoring and capture/realization. Sequential generation calls the calculation directly. CalculationProvenance and the complete-content revision encoding separate computation from sampling evidence.

The old plan module and package forwarding functions are removed. Replay rejects unavailable calculation identity while current-format stored values remain readable. Explicit migration preserves draws and values; parallel/serial, identity and fingerprint regressions pass. Captured noise, events and zero-volatility innovations share explicit support checks. A portable revision fixture fixes calculation and environment evidence; generated-source and currency-catalogue changes alter the live fingerprint. Required provenance adds code. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-022 Consolidate Specification composition and validation

### Problem and review evidence

The Specification package has nine files and 1,150 physical lines at the
2026-10-07 review. It contains two Composition classes, repeated dictionary/record
conversion, repeated graph preparation and mathematical collection, and policy
checks that serve other packages. Reduce these layers while retaining the distinction
between a saved Specification revision and a derived composition.

The review traced the composed-forward fixture after constructing its Composition:

| Operation | Additional composition calls | Model resolver calls |
| --- | --- | --- |
| Validate the existing Composition | 2 | 1 |
| Prepare that Composition for execution | 2 | 2 |

Both paths also called `model_documents()` three times and
`validate_formulations()` twice. These are call counts, not timing measurements;
Model-only and combined scopes differ and must not be merged merely to reduce counts.
The focused `test_domain_specification.py`, `test_validation_composition.py` and
`test_records.py` selection passed 87 tests, run without the global conftest.
Re-establish these baselines before implementation; this is not solver acceptance.

### Intended ownership and public operations

Consolidate the package around these responsibilities:

```text
specification/
  __init__.py         small public export surface
  specification.py  immutable saved contribution, construction and revision
  composition.py    one immutable Composition and additive graph composition
  validation.py     local, complete and batch validation orchestration
  targets.py        useful explicit assignment/unknown authoring helpers only
policies/
  validation.py     shared policy declaration and outcome checks under RF-018
```

Absorb `_composition.py` into `composition.py` and `_validation.py` into
`validation.py`, removing superseded conversion and collection code rather than
concatenating the old modules. Move `_policy_validation.py` and the policy type
exports in `specification/policy.py` to their policy owners under RF-018, then
remove the old modules. Retain the small `__init__.py` export boundary.

Prefer `Specification.compose(resolver=...)` and
`Composition.validate(resolver=..., units=...)` as public instance operations.
Finalize signatures with RF-006, migrate callers and remove equivalent public
module wrappers rather than retaining both APIs. Complete validation still returns
`ValidationReport`; raw-catalogue validation remains an explicit entry point.
Internal pure operations serve these boundaries without duplicated rules.

Composition is not a saved revision, does not mint an identity and must not be
persisted as replacement root content. Do not add inheritance, a builder, a
validator hierarchy or a document base class to remove a few accessors. Preserve
lightweight imports; use type-only imports or deferred boundary imports where
needed to avoid constructor/composition cycles.

### One composition and reusable preparation

Replace the private dictionary Composition and public typed Composition with one
immutable result. Retain effective requirements, exact contributor snapshots and
source attribution, including original contributor UUID and JSON pointer for
each requirement/declaration. The current contributor-only `sources` mapping
is insufficient for original diagnostics; extend it without rewriting source
locations as effective-array positions. Derive `root_id` and `model_id` from the
requirements; derive contributor IDs from the snapshots instead of storing a
parallel tuple.
Use `contributors` for the documents and, only if needed, an explicit
`contributor_ids` accessor. Migrate the current `contributors`/`contributions`
callers together. Keep attribution read-only and construct results only after
composition checks succeed; do not introduce an unchecked public constructor.

An existing Composition must pass directly to semantic validation. Remove the
export/reconstruct/recompose path in `specification/validation.py`. Raw mappings
and generated records still need their applicable structural, local and catalogue
checks before joining the same semantic stages. Preserve structural findings for
malformed supplied catalogue entries, including extras outside the reachable graph.

Use RF-006's internal result to retain the exact resolved Model, declaration scope
and analysis for execution preparation. Resolve and check the pinned Model once
within that operation. Execution adds capability checks, normalized assignments,
policy execution where supported, and imposed assertions; validation itself does
not execute an investigation. Preserve checkpoints and independent acceptance.

Prepare the reachable Specification catalogue and check include/case cycles once
within an operation. Reuse it for leaf composition, batch pin checks and execution
planning. `Plan.resolve()` must not load included documents again through public
composition after it has resolved them. Batch validation must not rebuild the
catalogue or compose a leaf again solely to pass it to the next check. Reuse
unchanged leaf results across case paths while retaining each occurrence.
Scheduling, persistence and recording failed attempts remain execution concerns.

Keep reuse confined to exact immutable content, revision, scope, units, history
and applicable settings under RF-006. Reject conflicting content before caching
by identity. A new independent operation establishes its own resolver context;
there is no global validation flag or cross-operation cache.

Include the pinned Models in that per-operation catalogue: `Plan.resolve()`
currently loads/checks them and then discards them. Retain the exact snapshots
for validation and execution preparation. Carry UnitSystem and original source
locations with their applicable results; policy evaluation must consume that
same unit context. Preserve failed-leaf evidence and Model-only versus composed
scope distinctions under the shared preparation contract.

### Direct local rules, mathematical reuse and settings correction

Remove `_validate_local()`'s temporary document with `includes` and `cases` stripped
out and its discarded call to the full composer. Apply contribution rules directly:
header/version, local identities and known-reference kinds, local duplicate roles,
role overlap, settings and Formulation naming. Share matching rules with real
composition and raw validation. Missing external targets remain valid locally;
construction performs no resolution or completeness check.

Use RF-004's schema-directed traversal and index for identities and references.
Retire the generic `records()` walker after migrating its policy, Run and conformance
callers. Opaque content must remain opaque. Consume RF-003/RF-005's located
Formulations, expression domains and dependencies; remove the second Formulation
collector and rebuilt expression lookup from `_validate_concrete()`.
Specification retains role eligibility, units, estimate eligibility, objective
eligibility and completeness rules over the prepared combined scope. Preserve
source-document identities and original diagnostic locations.

Use one intrinsic settings check at local construction and raw-validation
boundaries. The review reproduced `relative_tolerance=1` passing local construction
but failing complete validation. **Deliberate behaviour change:** reject it locally
as well, because the strict upper bound does not depend on Model resolution.
Preserve positive finite limits and optional/absent/null settings, and check
`0 < relative_tolerance < 1` when supplied. Backend support and effective-setting
interpretation remain execution concerns. Reuse this rule elsewhere only when
the settings contract matches; do not broaden the correction into new defaults.

### Target authoring and preserved contracts

Delete `targets.scalar()` and `targets.movement()`: both only construct
`Reference(target=id)` and neither validates the claimed target kind. Migrate
examples, formulation callers and tests to direct Reference construction with
RF-009/RF-014. Do not replace the two wrappers with another trivial helper.

Retain `assign_flow()` and `unknown_flow()` while they provide useful selection
validation and explicit role authoring. Absorb reusable Movement selection into
Flow only if actual callers share that operation; do not move Specification
assignment construction into Model or Flow. Preserve selection order, duplicate
and unknown-ID rejection, unresolved-magnitude rejection for assignments, recorded
zero, Flow units and unchanged inputs. Recorded amounts must never become fixed
assignments automatically.

Preserve additive composition without overrides. A diamond contributes an included
revision once, while independent duplicate requirements remain errors even when
equal. Objectives retain their order and single-contributor rule; empty content
is neutral. Keep exact Model pins, source attribution, declaration ownership,
local versus combined name scopes and predecessor checks. Lineage is separate from
includes/cases and does not cause implicit history loading.

Batch leaves keep separate mathematical scopes and occurrences. A batch Model pin
asserts each leaf's independently supplied pin and cannot supply a missing one.
Preserve composition failures, later semantic failures and execution capability
failures as distinct outcomes under RF-019. A valid partial document need not be
a complete investigation, and a valid investigation need not be solver-supported.

### Dependencies, deletion targets and verification

RF-006 owns shared preparation and diagnostic boundaries; this item owns the
Specification result, graph preparation and package consolidation. RF-003–RF-005
own mathematical analysis and traversal; RF-018 owns policy checks and their import
boundary; RF-019 consumes prepared results without weakening evidence validation.
RF-020 continues to own the shared revision guard. Implement overlapping changes
once, without parallel preparation objects or replacement wrappers.

Delete the second Composition class, stored derived identities, temporary local
composition, repeated catalogue/composition calls, second Model load, redundant
mathematical collectors and trivial target wrappers. Include all migrated callers
and destination modules in before/after counts. Policy relocation is not deletion.
Expect a net reduction in handwritten implementation; record any required growth
separately under the overall strategy.

| Area | Required acceptance evidence |
| --- | --- |
| Existing typed Composition | No recomposition or record round trip during validation; execution preparation resolves the Model once in its context |
| Raw input | Applicable structure, catalogue key/identity and semantic checks remain; malformed extras still report findings |
| Local construction | Partial references remain unresolved and permitted; duplicates and known wrong kinds fail without temporary graph composition |
| Settings | One shared rule rejects tolerance 1 locally and completely; exercise zero, negative, nonfinite, valid and absent/null values within schema constraints |
| Composition and batches | Preserve diamond deduplication, independent conflicts, cycles, exact pins, attribution, ordered objectives and distinct repeated case occurrences |
| Mathematics and diagnostics | Preserve separate Model/combined scopes, role completeness, unit checks, source locations and opaque-content boundaries |
| Authoring helpers | Direct References retain UUIDs; Flow helpers preserve selection, explicit roles, zero and unresolved-value handling |
| Public and package boundaries | New methods and migrated imports work; retired exports are absent; pure checks do not import execution or solvers |

Run the three focused suites above, affected execution, temporal, policy and Run/IO
tests, and `schema/checks/specifications.py` including its composition cases.
Keep independent expected results for policy evidence and numerical acceptance.
Run affected typing and installed-package checks; update current architecture,
authoring and naming guides, examples, docstrings and implementation fingerprint
inventories for changed paths and APIs. Do not describe planned behaviour as current.

Completion requires one Composition representation, direct local checks, shared
graph preparation, reusable semantic results, the explicit settings correction,
all caller migrations and measured reduction. Retain required validation and
provenance checks rather than satisfying call counts by omitting their work.

### Implementation record

Implemented in the coordinated working-tree pass. Specification.compose creates the sole immutable Composition; Composition.validate and internal preparation reuse its exact contributors and source locations. The package-level compose/validate wrappers and target scalar/movement wrappers are removed.

Local and complete settings checks enforce the same relative-tolerance bound. Planning caches exact Models for preparation; includes/cases, failure evidence and one-shot iterable cases retain their contracts. See the [combined acceptance record](#combined-implementation-record) for
verification, reduction accounting and remaining platform limits.

## RF-023 Consolidate workflow around existing evidence, graph and IO owners

### Purpose, current architecture and review evidence

The workflow package turns source observations and reviewed interpretation
declarations into a canonical Model, supporting provenance and reconciliation
results. It also contains reusable ingestion, HTML reporting, filesystem workbench
and saved-layout orchestration. At the 2026-10-07 review it contained 38 Python
files and approximately 5,700 physical lines, including its ingestion subpackage.
Re-establish exact counts across all affected owners before implementation.

The current execution flow is:

```text
sources.yaml + model.yaml + decisions.yaml + checks.yaml
  -> load, expand shared declarations and validate WorkflowSpec
  -> record configuration and implementation identity
  -> execute declared steps in order, retaining native intermediates
  -> extract and transform supported Evidence tables
  -> compose definitions, objects, relationships and Assembly memberships
  -> publish a validated Model with provenance
  -> compare source/Model values, Model invariants and source quality
  -> return WorkflowResult
  -> optionally render and publish a review bundle
  -> optionally prepare a saved layout
```

`WorkflowSpec` is a source-interpretation declaration. It is not the domain
`Specification`; `WorkflowResult`, `Operation` and a workbench attempt are not a
mathematical `Run`. Preserve these distinctions. `workflow.run()` reads inputs and
returns an Outcome without writing an output bundle. A successful build can contain
differences, unavailable comparisons and findings; completion does not establish
that all checks passed or that source coverage is complete.

The main problems are repeated preparation, data copied between parallel result
fields, unclear ownership of generic Evidence operations, and mixed report and
publication responsibilities. The private filename prefix is not itself a defect.
Retain cohesive private implementation boundaries where they reduce coupling.

Observed duplication includes:

- Table operations validate an Evidence input and then fingerprint it through a
  second validation. Output validation is a separate, necessary check.
- `tabular.claim()` resolves a row through `Table.row()`, which scans the table.
  Evidence validation also resolves rows for cell addresses, and Issue lookup scans
  scopes repeatedly. Whole-table processing can therefore perform quadratic row
  lookup work. This is a structural finding, not a measured timing result.
- `numbers()` and `transform()` repeat settings lineage, derived Claim creation,
  Issue propagation and output construction.
- `ProvenanceBuilder.add()` revisits support chains and recreates records before
  retaining them in dictionaries; retained uniqueness does not prevent repeated work.
- `CheckResult` duplicates left-side completeness in legacy and explicit fields.
  `model_operand()` creates a new View and prepares selections repeatedly.
- Workbench and layout publication repeat hashing, pointer verification and
  publication mechanics, while report modules mix data preparation and rendering.

### Ownership decision and package boundaries

Use existing Rangekeeper capabilities before introducing a new top-level package.
The agreed refinement supersedes the initial suggestion of a separate
`rangekeeper.ingestion` package: expand the existing `rangekeeper.evidence` capability.

| Responsibility | Intended owner and integration |
| --- | --- |
| Source observations, Claims, Locations and support indexing | Existing `evidence` capability |
| Evidence container, addressed Issues, validation, fingerprints and evidence-preserving transformations | Move from `workflow.ingestion` into a small `evidence` package |
| Ordered rows, columns, row identity and efficient row lookup | `table.py`; keep it independent of Claims and workflow |
| Canonical Model lookup, recorded Value access and unit conversion | Existing Model/graph/units operations and RF-004/RF-006/RF-009/RF-012 |
| Shared contributor selection, quantities and coverage | `graph`, coordinated with RF-013; retain distinct flat and hierarchy callers |
| Invocation identity, Outcome and expected operation failure | Existing `operation.py`; no new workflow-specific equivalents |
| Atomic file creation/replacement | Existing `io/_atomic.py`, with separate explicit contracts |
| Source reading, extraction, native checks and address formatting | Owning adapter; workflow integration registers its capabilities |
| Saved-layout preparation and review | Existing `adapters/cytoscape/layout` integration |
| Declarations, step order, source-to-Model composition and reconciliation | `workflow` |
| Workflow report preparation, rendering and workbench coordination | Focused workflow consumers of the execution result |

Convert `evidence.py` into a cohesive package if required to keep these operations
navigable. Preserve its logical public imports for Claim, Source, Location and
Method through normal package exports. Do not concatenate all ingestion code into
one large file or retain the old ingestion package as a forwarding layer. Choose
the internal file split from the resulting responsibilities and deletion evidence.

Keep Table, Claim, Evidence and Model distinct. Table accepts general cells and
optional row identity; Evidence imposes supported immutable payloads, addressed
Claim coverage and explanations. Evidence validation currently supports only Table
content. This refactor does not add other Evidence representations or require
native adapter snapshots to inherit a common type or masquerade as tables.

Keep core evidence types lightweight. `operation.py` imports evidence types, while
Evidence operations use Outcome and severity; plan imports so these dependencies
do not form a cycle or load Excel, Polars or other optional integrations eagerly.
Adapters should depend on evidence directly, rather than on `workflow.ingestion`.

### Prepare Evidence once and reuse table indexing

Give Table one reusable row-UUID lookup built from its validated rows. Preserve
ordered rows, unidentified rows, duplicate-ID rejection and existing lookup errors.
Only structural identity is indexed: Table's shallow freezing does not establish
that arbitrary cell values are safe to cache or use as validated Evidence.

Prepare an Evidence artifact once within an operation, retaining its validated
Claim/Source indexes, addressing and Issue-scope lookup, and fingerprint. Use the
same preparation for consuming the artifact and describing its identity. Keep the
preparation internal and bound to the exact artifact and applicable contracts;
do not introduce a global cache or trust an unrelated previous validation.

Move Evidence shape and address validation out of private table transformation
helpers so validation, fingerprinting and transformation have a clear dependency
direction. Reuse `evidence._index_claims()` where its contract matches; that reuse
already exists in ingestion validation and must not be presented as new work.
Preserve validation of independently supplied inputs and newly constructed outputs.

Construct table values from terminal Claims once. Remove the temporary skeleton
Table only when row/column normalization and its error contracts are preserved.
Use RF-010's Table construction rule to retain an already normalized Row with the
exact column order. Removing a skeleton does not remove Table's current Row copy;
test reuse at that boundary and normalization of raw mappings separately.
Selection and concatenation must preserve Claim identity and project Issue scopes;
raw Table operations cannot substitute for these evidence-aware operations.

### Share derivation and provenance preparation

Consolidate repeated derivation mechanics around a small operation that gathers
support, applies a declared value policy, records derived Claims and Issues, and
constructs output Evidence. Retain separate numeric and text interpretation policies.
Place predicate selection with Evidence table selection. Do not introduce a plugin
framework, arbitrary expression engine or universal transformation strategy hierarchy.

Preserve ordered transformation dependencies: a later derived column can consume
an earlier derived column in the same request. Preserve repeated operand values even
when their supporting Claims are deduplicated. Missing observations remain missing,
not zero; booleans, numbers, dates and other supported payload types remain distinct.

Settings identity must include complete supported content and lineage, not merely
the settings Claim UUID. The current helper constructs and fingerprints a one-cell
Evidence artifact. Replace that intermediate artifact only if the established
encoding is preserved or an explicit fingerprint-version migration is documented.

Prepare and convert source support once per Model composition. Keep an explicit
bridge from transient source Claims to canonical Model provenance records; reuse
canonical Model accessors for subsequent inspection. Workflow-specific decisions,
bindings and Fact attachment remain at the composition boundary.

Do not skip conflict checks when a UUID has already been encountered. The source
Evidence index currently enforces canonical object identity, while the publication
builder checks canonical record content for repeated identities. Share traversal
only where these contracts agree; do not silently tighten or weaken one by replacing
it with the other. Preserve cycle checks, source editions, support order, non-cell
Locations and configuration references. Attach object Facts after final Assembly
membership, and bind revision identity to the completed Model content.

### Reuse graph operations and compose comparison results

Coordinate with RF-009/RF-012/RF-013 to share this bounded operation within graph:

```text
selected canonical entities
  -> select recorded Values
  -> normalize units
  -> collect available quantities, selected Value IDs and contributor coverage
  -> reduce under the caller's explicit completeness policy
```

Current `Reduction.execute()` requires a Hierarchy. Workflow totals can use a flat
selection, so do not manufacture a hierarchy to reuse it or change RF-013's
hierarchy-pinned Aggregation into a generic workflow result. Extract the common
per-population work and retain hierarchy traversal and raw-contributor semantics.
Prepare the pinned Model and common lookups once per checking pass; scope-dependent
filters must still be evaluated for their actual comparison context.

Before replacing existing operand loops, characterize differences in empty scopes,
supported Value kinds, unit handling, numeric result types and summation behaviour.
Graph reduction currently restricts selection to scalar Measurements; workflow
quantity access does not impose the same kind check. Do not broaden graph eligibility
or silently narrow workflow eligibility. Share the matching lower-level work and
keep caller-specific admissibility until a behaviour change is explicitly agreed.

Workflow operands retain information which graph Coverage cannot represent: expected
business keys absent from the Model, source Claims, comparison targets and source-row
identities. Keep these alongside graph results. `Coverage.missing` contains selected
Model entity UUIDs and must not become a mixed list of business keys and row IDs.

Compose CheckResult from two operand-side results instead of flattening and copying
value, members, known subtotal and missing contributors into parallel fields. Remove
legacy `missing`/`known_subtotal` left-side aliases and migrate active consumers.
Keep support and targets with the side that produced them. Derive display counts
without discarding compared membership, and define an explicit JSON export instead
of making dataclass `asdict()` the saved-file contract.

Preserve both sides' incomplete results and known subtotals, tolerance rules,
type-sensitive matching, unavailable results, emission policy and target links.
Equal counts must not hide different members. Required columns must be checked even
for an empty table. Keep Model invariants and source-quality checks distinct from
two-sided comparisons, and do not turn source totals into physical graph quantities
without a declared unit and contributor contract.

### Simplify declarations, composition and runtime

Keep the four reviewed documents and the explicit closed operation catalogue.
Capability requests should own their strict parsing, dependency description,
execution, schema metadata and audit requirements. Remove parser special cases
based on field spellings such as `specifications`, while avoiding a second generic
schema framework. Validate shared declarations, including unused definitions, and
retain both authored references and expanded effective inputs for audit.

Retain prepared workflow declarations for execution rather than validating them
again along the same controlled path. Direct composition remains an independent
public boundary and must validate supplied declarations. Rename the workflow
`validate_model()` helper to make clear that it validates a Model declaration, not
a canonical Model. Do not merge the workflow input language into Model validation.

Keep the composition sequence explicit: definitions, objects, relationships,
memberships, Model publication. Share condition/binding/support preparation across
measurements, properties and labels, using a small bound-value result if it replaces
the current repeated tuple handling. Keep each characteristic's domain rules explicit.

Combine `_execution.py` with `runtime.py` and `_audit.py` with `implementation.py`
where this removes indirection and repeated preparation. Retain distinct exact-code
audit and computation-identity outputs. Keep operation contracts separate from the
catalogue assembly: adapters import the contracts and the catalogue selects adapters.
Merging these two owners would introduce circular dependencies.

Continue to use `operation.py` for invocation records and Outcomes. The workflow
dispatch record and a handler's native operation record have different provenance
roles; do not remove one as an apparent duplicate. Stop when a required step is
unavailable, retain diagnostics, and let unexpected programming errors remain visible.
Progress observers remain isolated from semantic results and computation identity.

Use RF-002 enums for closed choices where applicable. Operation names and declared
capability kinds remain catalogue identifiers, not an excuse for an open plugin API.
Reuse compatible guards from `validate.py`, and encoding from `_structured.py` and
`_encoding.py`. Resolve exception and exact-type differences before replacing guards.
Keep Evidence payload encoding, structured request encoding and record interchange
distinct; fold the small Evidence encoding wrapper into its owner while preserving
Evidence-specific errors. Remove legacy request aliases in `specification.__getattr__`
and migrate callers to the owning request definitions.

### Reporting, layout and atomic publication

Replace the ambiguous `review.py`/`_review.py` split with clear report preparation
and rendering responsibilities. Prepare decision usage, supported targets, references
and check sides once, then render HTML, JSON and notebook displays from that data.
Retain the distinction between declared decision usage and actual Fact support;
accepted mapping status must not imply that its evidence is complete.

Integrate atomic file mechanics into `io/_atomic.py` with explicit create-only and
replace contracts. Existing `write_new()` must continue to reject overwrite for
revision documents. A latest pointer requires atomic replacement. Share same-directory
temporary-file and durability handling without making these operations interchangeable
or claiming a multi-file transaction from a single atomic write.

Keep bundle schemas, required artifacts and build-specific checks with their
consumers. Reuse hashing and pointer/publication primitives where the contracts
match. Workbench coordinates inspect, execute, verify freshness and publish. Preserve
the before/after signature comparison and checks against the source bytes actually
used by the build. Stage a complete bundle before publishing its pointer. Failure
before replacement must retain the previous successful pointer without presenting
it as this attempt's output. A directory-sync failure after replacement leaves the
new pointer visible: report the completed publication with an explicit durability
diagnostic. Do not roll it back or report the old bundle as current. Display,
observer and status-record failures after publication must not relabel it as failed.

Move `workflow/layout_review.py` into the existing Cytoscape layout integration.
Consume an explicitly supplied Model and verified bundle metadata, rather than a
full workflow Attempt. Retain saved-geometry validation, Model-revision binding,
profile and implementation freshness, and the absence of implicit solver fallback.
Reconcile ordinary/layout build interruption handling explicitly and test it.

Review bundles and latest pointers do not become canonical revision-store documents
or mathematical Runs. No new storage engine, scheduler, general job framework,
source format, Model mutation or solver execution is introduced by this refactor.

### Identity, affected code and implementation sequence

Affected code includes the workflow package, `evidence.py`, `table.py`, shared
operation/encoding/argument guards, graph selection/reduction, `io/_atomic.py`,
Excel integration and Cytoscape layout publication. Migrate package exports,
test/typing/install fixtures, active examples and notebook consumers, and update
`docs/GRAPH_WORKFLOW_FORMATS.md`, `docs/CONSUMER_MIGRATION.md` and architecture guides.

Computation identity currently includes module paths and executable syntax.
File moves alone can change implementation fingerprints and derived provenance or
revision IDs. Update included capability groups and presentation exclusions, record
expected identity changes and use explicit format/method migrations when needed.
Preserve stable business-key identity independently of computation identity, and
never rewrite historical bundles to disguise a changed implementation. Issue IDs
exclude prose/severity/details, while Evidence fingerprints include them; retain
that distinction. Do not merge these hashes with RF-020 record equivalence.

#### Fingerprint inclusion rules

Maintain one explicit fingerprint inclusion/exclusion inventory across the final
owners. The current workflow manifest names `evidence.py` and only selected graph
files; moving code to `evidence/` or reusing selection/reduction must not remove it
from semantic identity. Include relevant `_record_index.py`, arithmetic, account,
currency catalogue and generated schema changes according to each computation's
actual dependency set. Keep presentation-only exclusions explicit and tested.

| Provenance owner | Required semantic inputs | Distinct boundaries |
| --- | --- | --- |
| Workflow computation | The new evidence package, Table and record/encoding rules, used graph selection/reduction/reducer operations, domain validation and units/schema resources, including jsonschema; include each selected handler's native computation modules and dependencies | Keep the complete installed-code audit separate; reporting, progress and viewer assets do not change assertion identities when they only present existing results |
| Scenario calculation | Method contracts, capture-to-calculation normalization, realization/path composition, the called calculation kernels and their shared helpers, relevant units/schema resources and dependency versions | Record the calculation manifest under RF-021; keep sampling generator/seed provenance separate; include a shared sampling module only if calculation uses its code |
| Execution compiler and evaluator | The respective preparation/normalization, compiler or arithmetic/acceptance modules and transitive semantic helpers/resources that affect that implementation's result | Give compiler and evaluator their own manifests; retain separate solver/backend version evidence and independent acceptance; replace the fixed `version="1"` identification where source changes would otherwise be invisible |

For each owner, follow the actual computation dependencies through module moves;
update includes and exclusions in the same change as the move or new reuse. Record
exact final file lists in W1 and keep them testable in installed packages. A broad
package prefix must not silently include presentation code or omit a newly shared
helper. Test one relevant edit in each affected group and one explicit exclusion;
also test deterministic identity with unchanged source, resources and dependencies.

Coordinate with RF-007/RF-008/RF-021 and execution's current compiler/evaluator
`version="1"` literals. Use deterministic source/dependency identity for changed
computation; a package-version string alone does not identify modified source.
Extract a small shared digest helper only where it replaces existing code; keep
workflow, scenario and execution manifests and provenance records separate.
Add tests for fingerprint stability and sensitivity to relevant source/resources,
including installed-wheel contents. Data fingerprints, ordered record equality,
schema equivalence and content-based revision IDs remain different contracts.

Implementation order:

1. Capture behaviour, identity, exports and size baselines across all affected
   owners. Freeze independent fixtures before changing shared implementations.
2. Establish evidence package imports, Table row indexing and per-operation
   Evidence preparation. Remove the obsolete cross-imports and migrate adapters.
3. Consolidate derivation and provenance work, preserving conflict and encoding
   contracts. Remove temporary artifacts and conversion loops where justified.
4. Establish shared graph population preparation with RF-004/RF-006/RF-009 and
   RF-011–RF-013; compose comparison sides and migrate exports/rendering consumers.
5. Simplify declaration preparation and orchestration, then report preparation,
   atomic file primitives and layout ownership. Remove aliases and retired modules.
6. Update fingerprint groups, explicit migrations, active callers and guides.
   Run focused and combined checks and record reduction and preparation evidence.

RF-019/RF-022 define domain Run/Specification boundaries, not replacement workflow
engines. RF-020 supplies record equivalence only where its contract applies.
Do not duplicate their preparation contexts or merge policy truth, solver acceptance
and workflow reconciliation into one validation or comparison framework.

Deletion targets are the old workflow ingestion location, redundant encoding and
request wrappers, repeated validation/indexing, duplicate derivation scaffolding,
repeated provenance conversion, legacy CheckResult fields, duplicate result assembly,
private runtime/audit forwarding splits and repeated artifact-writing mechanics.
Focused modules for bindings, operands, provenance and progress can remain where
they have a clear owner. Target a net reduction across workflow, evidence, table,
graph, IO and adapters; moving lines out of workflow alone is not reduction evidence.

Remaining implementation choices are the evidence package's internal file split,
visibility/naming of prepared results and graph helpers, the explicit check-export
version, and any necessary fingerprint migration. Resolve them against current
callers and the contracts above; they do not authorize additional runtime features.

### Verification and completion criteria

The 2026-10-07 review first passed 114 workflow, format-boundary, shared-declaration,
workbench and layout-workbench tests. The ingestion test module initially could
not collect because Polars was missing. With the user's permission, Polars 1.44.2
and its matching runtime were installed in `src/.venv`, matching `src/uv.lock`.
No dependency-file or implementation edit was needed. The expanded baseline passed
190 tests in 54.33 seconds using the following command from `src`:

```sh
.venv/bin/python -m pytest tests/test_ingestion_evidence.py tests/test_excel_ingestion.py tests/test_workflow.py tests/test_workflow_formats.py tests/test_workflow_shared.py tests/test_workflow_boundaries.py tests/test_workbench.py tests/test_layout_workbench.py -q
```

This is a pre-refactor local baseline, not acceptance of the proposed design or
proof of remote/installed-package behaviour. Polars remains an optional capability;
its test installation must not become an unconditional workflow dependency.

Verify independent expected outcomes for:

- Exact Evidence cell/Claim coverage, immutable supported payloads, explained None,
  conflicting Claim/Source identities, cycles, Issue identity and fingerprint changes.
- Stable row addressing through selection, order changes and concatenation; Issue
  scope projection; unchanged public errors; empty tables and unidentified raw rows.
- Numeric admissibility, exact type distinctions, settings content/lineage changes,
  derived-column dependencies, deterministic Claim identities and source editions.
- Provenance conversion with shared ancestors, repeated identities, decision/config
  support and non-cell Locations; Facts refer to final canonical declarations.
- Both operands' missing contributors/subtotals, absent business keys, empty scopes,
  required columns, wrong members with equal counts, tolerances and target links.
- Flat and hierarchy reductions under their distinct eligibility/coverage contracts;
  pinned revisions, units, callback validation and raw-contributor ordering.
- Strict request parsing, defaults and schema metadata, unused shared declarations,
  declared dependency kinds, native intermediates and unavailable prerequisites.
- Progress failure isolation, expected failure diagnostics and propagation of
  unexpected programming errors; interruption handling before and after publication.
- Create-only versus replace semantics, bundle completeness/integrity, input or
  implementation changes during execution, failed publication and retained pointers.
- Saved-layout/profile freshness, independent geometry checks and Model binding;
  no prior-build fallback as a new result and no implicit numerical solver execution.
- Import isolation, migrated public callers, explicit export/fingerprint versions,
  deterministic repeated builds and read-only preservation of historical artifacts.

Measure validation/traversal calls and row-lookup scaling on representative tables;
do not infer performance from file count or new helper names. Run the baseline suite,
affected graph/Model/IO/document-operation/adapter suites, typing and installed-package
checks, then applicable combined checks from [Verification](VERIFICATION.md).

Completion requires clear existing owners, one preparation per matching operation
scope, shared derivation and lookup work, composed comparison sides, explicit report
exports, preserved independent publication checks, retired aliases/modules, migrated
consumers and passing verification. Record added/removed/net implementation size
across every affected owner and justify necessary growth. Implementation follows
the execution instruction; acceptance is recorded below.

### Implementation record

Evidence now belongs to `evidence/`. Per-operation preparation validates once,
retains Claim/Source indexes and fingerprints, and indexes Issue scopes. Numeric
and text derivation share their cell-support rules. Text derivation extends the
Issue index as earlier derived columns produce explanations; it does not rescan
all Issues for each missing cell. Table row lookup uses one immutable index.

Workflow composition shares condition, binding and support preparation across
measurements, properties and labels. Provenance caches retain exact source
objects and still reject conflicting UUID content. A checking pass shares one
pinned View and the Model's existing record index. Flat totals use graph population
collection while retaining workflow-specific eligibility and summation.
`CheckResult` contains complete left/right operands and exports check format v2.

`workflow.reporting` prepares check sides, target usage and cell references once;
HTML rendering consumes those results. Layout review belongs to the Cytoscape
adapter and checks supplied Model content with strict type-sensitive equality.
Its fingerprint includes that comparison implementation. Atomic IO preserves
separate create-only and replacement contracts. Retired ingestion, request aliases,
`_execution` and `_audit` forwarding paths are removed.

Workflow method/semantic-manifest version 5 includes moved Evidence, shared graph,
record/index, schema, units and selected adapter code, the installed py-moneyed
version and actual currency catalogue codes. Exact installed-code audit remains
separate from computation identity. Regressions cover source/resource sensitivity,
preparation counts, ordered derived dependencies, rendered prepared data and
same-revision `0`/`False` rejection. Necessary enums and validation add code; the
combined size record reports that growth without claiming a net reduction. See
the [combined acceptance record](#combined-implementation-record) for final
verification, accounting and platform limits.
