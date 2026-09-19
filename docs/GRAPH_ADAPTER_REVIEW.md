# Ingestion and workflow boundary review

Reviewed and refactored 18 September 2026 on the uncommitted
`feature/mandarin-yaml-rebuild` implementation. The findings below describe the
pre-refactor code. Their resolution is recorded here; Dagster remains outside scope.

## Implemented resolution

- Adopted `graph.adapter` for formats, `graph.workflow.ingestion` for Evidence,
  `graph.workflow` for composition/checks/declarative execution, and
  `graph.operation` for shared invocation contracts. Active callers and CLI use
  the new paths; old adapter ingestion/workflow imports are intentionally removed.
- Shared complete configuration-lineage fingerprints and strict Issue collision
  handling. Colliding, distinct explanations return an unavailable Outcome with
  `conflicting_issue`; they are never silently deduplicated.
- Centralized request parsing and input/output kinds in a closed descriptor.
  Added discriminated required/allowed check fields and shared safe YAML decoding,
  rejecting aliases consistently. Schema remains explicitly steps-only.
- Moved whole-column marker uniqueness into native Excel extraction and exact-type
  table predicates beside selection. Preserved physical row and business policies.
- Exposed direct composition/check APIs, separated bindings/reference presentation,
  and moved visited-once structured location traversal into provenance.
- Separated exact byte manifests from version-2 semantic AST identity and linked
  dispatch/native records by step. Business UUID recipes remain unchanged.

Validation is recorded in Mandarin `docs/yaml-rebuild.md` and local
`artifacts/adapter-refactor/`; the earlier checkpoint remains preserved separately.

## Validation result

The refactored candidate passes 186 RK contract tests (37 added boundary cases),
five Mandarin build tests, the separate complete reference comparison, Ruff and
focused ty checks. An isolated checkout with a newly synchronized locked environment
repeats those checks and runs the thin notebook in a fresh kernel. Graph JSON,
checks, manifest, review HTML and viewer HTML are byte-identical to the working
candidate. All 54 archived files and original source-workbook hashes remain intact.
No commits or publication were performed.

## Assessment

Keep ingestion and workflow separate. Ingestion owns reusable transformations of
Evidence; workflow should supply names, configuration and execution order. The
runner already delegates numbers, transformations, selection and concatenation.
Its request wrappers generally represent wiring, not duplicate algorithms.

The larger problem is uneven ownership: `workflow` also owns graph composition,
source-quality logic, binding evaluation and presentation helpers. Duplicated
boundary logic has already produced inconsistent behavior. Moving everything into
one package would hide those differences rather than reduce maintenance.

## Recommended work, in order

### 1. Share derivation support; fix divergent lineage and Issue handling

[tabular.numbers](../src/rangekeeper/graph/workflow/ingestion/tabular.py) fingerprints
the complete settings Claim lineage by making temporary one-cell Evidence.
[transform](../src/rangekeeper/graph/workflow/ingestion/transform.py) and
[classify_rows](../src/rangekeeper/graph/adapter/excel/classification.py) record only
its ID. The latter operations also independently assemble derived Claim IDs and
parents. Extract a small internal Claim-lineage fingerprint helper and shared
Issue projection/merge support; keep numeric and label policies distinct.

**Confirmed:** two separate transform calls with the same settings ID but changed
settings text produce the same operation fingerprint and derived Claim ID, despite
different resulting Evidence fingerprints. Workflow-generated settings IDs usually
change with configuration, masking this standalone API inconsistency. The shared
helper should make effective configuration content count in every operation.

**Confirmed:** an unavailable source cell with different table-wide and cell-scoped
Issues can lose the cell-specific explanation at the derived address. Projecting
both to the same address gives the same Issue ID; transform silently retains the
first. `tabular._unique_issues` instead rejects conflicting records. Reuse one
explicit collision policy that preserves explanations or reports incompatibility;
do not deduplicate distinct explanation metadata by ID alone.

Acceptance: settings-content/lineage changes affect fingerprints; both explanation
scopes survive or fail explicitly; unchanged specifications remain deterministic;
NumberSpec still rejects arbitrary numeric strings and booleans. Preserve existing
identity recipes initially, or version any intentional change.

### 2. Give specification validation one owner per operation

[StepSpec/schema](../src/rangekeeper/graph/workflow/specification.py) repeat
operation knowledge across request types, mapping conversion, dependency typing
and handwritten schemas. Model and check validation use another family of mapping
validators. A small static operation descriptor could connect parser, input kinds,
schema and executor; it must remain a closed registry, not plugin infrastructure.
Validate discriminated model/check declarations at load time and add type
annotations at their callable boundaries before introducing more abstractions.

**Confirmed:** `source_checks.validate([{"id": "bad", "operation": "identities"}], {})`
passes, but execution raises `KeyError('table')`. Required fields depend on operation
kind and are not consistently checked. This violates the intended early-validation
boundary even though the current Mandarin declarations pass.

The [Excel YAML loader](../src/rangekeeper/graph/adapter/excel/specification.py) and
workflow loader also duplicate safe-loader/key handling with different alias and
error policies. Share decoding support only after making those differences explicit.
The published `schema()` currently covers steps only; decide whether to keep that
narrow promise or add full model/check schemas, and test it against actual parsing.

Acceptance: missing/wrong fields fail while loading with a useful declaration path;
parser/schema agreement; no executable tags, arbitrary imports or expression engine.

### 3. Move source and table policy out of the runner

[runtime.run](../src/rangekeeper/graph/workflow/runtime.py) implements its own
stopping-marker matcher and table `where` predicate. Excel extraction already owns
[_matches/_last_row](../src/rangekeeper/graph/adapter/excel/extraction.py); workflow's
matcher omits the native error/cache guards. Composition conditions and check
filters independently repeat exact-type comparisons.

Keep workflow-specific names and paths in the runner. Put marker matching and
uniqueness under Excel extraction, with an explicit scan scope; put a small reusable
table-predicate contract beside Evidence selection. Reuse existing selection for
scope projection. Share exact-type predicate primitives where semantics agree;
do not replace them with an expression language or merge different total/coverage
rules merely because their loops look similar.

Acceptance: native and workflow entry points apply identical marker rules,
including errors, missing caches and scan boundaries; zero and booleans remain
distinct; selected Claims and Issue scopes remain unchanged.

### 4. Decouple composition/checking from workflow and Excel helpers

[composition](../src/rangekeeper/graph/workflow/composition.py) receives the
whole WorkflowSpec although it needs model/identity policy and Evidence. Checking
and rendering import its binding or reference-formatting helpers. Generic Claim
location traversal lives in `excel.classification`, so graph composition depends on
an Excel row classifier simply to inspect provenance.

Give composition an explicit model/context contract independent of WorkflowSpec;
likewise expose checks against Graph and named Evidence. Move generic lineage
traversal to provenance support, keep Excel-address formatting in presentation,
and keep binding/condition support independent of graph construction. Traverse
shared Claim ancestors once and retain structured Locations before formatting them.
Composition/checking can become adjacent adapter capabilities when these boundaries
are clear; renaming directories alone is not the objective.

Source checks can reuse native workbook inspection and generic Evidence summaries.
Keep `Issue`, `Diagnostic`, `CheckResult` and `Finding` distinct: cell explanation,
invocation failure, comparison result and construction limitation are different
contracts. Share reference and formatting utilities rather than flattening results.

Acceptance: direct Python composition/checking with no WorkflowSpec; no generic
provenance dependency on Excel classification; canonical Fact targets, source and
decision lineage, exact membership and unavailable comparisons remain intact.

### 5. Separate reproducibility metadata from semantic identity

[runtime.run](../src/rangekeeper/graph/workflow/runtime.py) hashes every Python
file beneath the installed `rangekeeper` package and feeds that aggregate into configuration and composition
identities. A renderer-only or docstring edit therefore changes derived Claim IDs.
It also records a workflow dispatch Operation plus the underlying native Operation
for many steps, without an explicit parent/child record relating the two.

Retain the complete code manifest for audit, but define which implementation
versions influence each semantic operation. Preserve distinct dispatch and native
records where they explain effective selection; associate them with their step
instead of pretending they are independent executions. Removing records requires
an explicit compatibility decision, not a blind deduplication pass.

Acceptance: relevant semantic changes invalidate derived identities; presentation
changes do not; manifests still identify exact implementation bytes. Review these
identity changes against the frozen graph/check equivalence contract.

## Keep these distinctions

- `NumberSpec` versus `NumbersSpec`: conversion policy versus named-input wiring.
- Evidence fingerprints versus Operation fingerprints versus graph JSON: content,
  invocation and reloadable persistence. `_structured` already reuses immutable
  scalar encoding while allowing structured request containers. Do not broaden
  Evidence payload types merely to share serialization code.
- Operation availability versus unavailable cells versus check differences:
  independent outcomes requiring different consumer decisions.
- RK generic mechanisms versus project YAML meaning: no project-specific branches.

The current Evidence constructor validates, and fingerprints/operations can
validate it again. Profile repeated validation and lineage traversal after the
correctness work; no performance claim or caching design is justified by this
review alone. Avoid arbitrary file-count or line-count targets.

## Delivery approach and evidence

First make items 1–2 small correctness changes with regression tests. Then extract
shared boundary helpers and independent composition/check APIs, retaining public
imports where practical. Finally tighten fingerprints/operation history as an
explicitly versioned change. After each semantic change, run the relevant synthetic
contracts and Mandarin's separate full equivalence comparison; rerun clean bootstrap
when the refactored candidate is stable.

This review used source/call-site inspection and three isolated synthetic probes:
settings lineage with a reused ID, conflicting projected Issue metadata, and a
source-check declaration missing required fields. All three produced the behavior
reported above. They did not read project workbooks or modify runtime files.
Documentation links and API names were checked locally. Runtime tests and notebook
execution were not repeated for this documentation-only change.
