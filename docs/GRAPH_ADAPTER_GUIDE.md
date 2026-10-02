# Why the graph adapter APIs exist

**Scope, 2026-10-02:** this guide describes the existing graph ingestion APIs.
The [library plan](LIBRARY_ARCHITECTURE.md) replaces canonical domain records
first, then migrates these adapters and workflows. `WorkflowSpec` remains a
source-building configuration, distinct from the new mathematical `Specification`.
The APIs below are not evidence that the new Model executor is implemented.

This guide explains the purpose of the ingestion and workflow APIs. See the
[YAML contract guide](GRAPH_YAML_WORKFLOW.md) for syntax and the
[boundary review](GRAPH_ADAPTER_REVIEW.md) for the original findings and their resolution.
The class and method docstrings explain the same ownership in the Python API.
The later [format-independent execution refactor](GRAPH_WORKFLOW_FORMATS.md)
records the catalog, native-handler boundaries and explanation fixes.

## Responsibilities

| Layer | Why it exists |
| --- | --- |
| `graph.provenance` | Establish which observations and decisions support a graph assertion. |
| `adapter.excel` | Preserve distinctions that disappear in plain tables, such as a physically blank cell versus a formula with no cached result. |
| `workflow.ingestion` | Carry values and explanations together before deciding what belongs in a graph. Its operations are callable without YAML or the runner. |
| `graph.operation` | Record a reproducible invocation and distinguish a failed invocation from a usable output containing missing values. |
| `graph.workflow` | Connect named inputs, reviewed configuration, graph mappings and checks into one repeatable build. Composition and checking can also be called directly. |
| `adapter.json` / review | Preserve a reloadable graph and make its evidence inspectable. Export is an explicit boundary. |

For example, a missing numeric cell can yield a successful `Outcome` whose
`Evidence` contains an unavailable value and an `Issue`. An absent input column
prevents the requested transformation and yields an unavailable `Outcome` with a
`Diagnostic`. Those cases must remain distinguishable.

## Evidence and invocation contracts

| API | Utility and reason |
| --- | --- |
| `Source`, `Location`, `Claim` | Identify an edition, an address within it, and an observation or derivation. Following Claim sources explains a value without reopening the original file or trusting a display label. |
| `Fact` | Connect Claims to an actual canonical graph object or characteristic. Evidence alone does not assert that an observation is the accepted graph value. |
| `Evidence[Table]` | Binds every output cell to a terminal Claim and carries applicable Issues. This prevents a table from drifting away from the observations that justify its values; row UUIDs survive reordering. Although generic in annotation, validation currently supports Table content only. |
| `EvidenceKey` | Addresses a row or cell independently of its display position. Prefix scopes let one explanation apply to a whole table, one row, or selected cells. |
| `Issue` / `IssueSeverity` | Preserve an explanation alongside affected content. Severity supports presentation; the consuming rule determines availability. Otherwise a warning could accidentally erase a valid zero or turn a missing result into a usable value. |
| `ingestion.validate` | Enforces coverage, Claim/value agreement, valid scopes and explanations for missing values. It establishes structural trust, not business correctness. Construction already invokes it. |
| `ingestion.fingerprint` | Detects changes to the complete Evidence, including lineage and explanations. It is a content digest, not a reload format or business identity. |
| `Operation` / `operation.fingerprint` | Record the effective method/version, parameters and input fingerprints. They identify the requested computation reproducibly, rather than inventing a new identity for every execution. |
| `Outcome[T]` / `Diagnostic` | Let a valid request report that its sources cannot support execution. Caller mistakes remain exceptions; expected input incompatibilities can be reviewed without pretending a result exists. |
| `_invoke` / `_Failure` (internal) | Centralize conversion of anticipated operation failures to Outcomes. They are implementation support, not another public pipeline API. |

Sources: [provenance](../src/rangekeeper/graph/provenance.py),
[Evidence](../src/rangekeeper/graph/workflow/ingestion/evidence.py),
[validation](../src/rangekeeper/graph/workflow/ingestion/validation.py),
[fingerprints](../src/rangekeeper/graph/workflow/ingestion/fingerprint.py),
[operations](../src/rangekeeper/graph/operation.py).

## Source and table operations

| API | Utility and reason |
| --- | --- |
| `excel.Workbook`, `Worksheet`, `Cell` | Retain a native snapshot, including formula/cache/error and physical-population information. A missing extracted value cannot by itself tell us whether the source cell was empty. |
| `excel.read` | Bind a snapshot to source bytes and an edition checksum before interpretation. Later operations reuse that snapshot instead of observing a possibly changed file. |
| `ExtractionSpec`, `Rows`, `StopBefore`, `Expectations`, `Column` | Make layout assumptions reviewable and testable. Explicit columns, boundaries and guards help prevent a shifted workbook from silently supplying the wrong observations. |
| `excel.extract_table` | Produce Claims while applying the reviewed layout, keeping source addresses available through later transformations. It consumes cached values; it does not calculate formulas. |
| `RowClassificationSpec` / `excel.classify_rows` | Separate physical emptiness, identifier matches and other occupied rows before selecting records. This avoids treating an uncached formula as an empty row or a note as a business object. |
| `tabular.from_claims` | Build values from Claims rather than constructing two independent copies and hoping they agree. It is the assembly point for a supported Evidence table. |
| `tabular.row`, `claim`, `issues_for` | Give consumers stable access to an observation and its explanations. Use these when a value must retain provenance rather than reading values alone. |
| `NumberSpec` / `tabular.numbers` | Declare numeric admissibility while preserving original observations. Strict numeric types prevent accidental conversion of labels, booleans or missing markers into measurements; negative and integer policies stay explicit. |
| `TransformSpec` / `transform` | Express a bounded interpretation of labels and multiple observations with derived Claims. Explicit capture-to-integer, agreement and fallback make conversion and conflict policy reviewable instead of hiding it in arbitrary expressions. |
| `tabular.select` | Restrict/reorder existing observations while preserving Claim identity and trimming Issue scopes. This is useful for separately reviewing detail, notes and blank rows. |
| `tabular.concat` | Combine compatible ranges without recreating their observations. Input-wide Issues are confined to their own rows so one range's explanation cannot contaminate another. |

Sources: [Excel API](../src/rangekeeper/graph/adapter/excel/__init__.py),
[extraction declarations](../src/rangekeeper/graph/adapter/excel/specification.py),
[physical classification](../src/rangekeeper/graph/adapter/excel/classification.py),
[table API](../src/rangekeeper/graph/workflow/ingestion/tabular.py),
[interpretation](../src/rangekeeper/graph/workflow/ingestion/transform.py).

## Declarative build APIs

| API | Utility and reason |
| --- | --- |
| `StepSpec` and its request types | Bind a named prior output to a reusable operation. `NumbersSpec` supplies an input name and a mapping of `NumberSpec` policies; it does not implement numeric conversion a second time. The same wiring distinction applies to extraction and transformation requests. |
| `WorkflowSpec` | Retain one immutable reviewed build declaration and reject invalid dependency order before source execution. Model/check sections currently use validated frozen mappings; they are not all separate typed specification classes. |
| `load` / `schema` | `load` establishes the four-file configuration boundary and its hashes. `schema` helps author registered steps; it currently describes the step catalog, not the complete model/decisions/checks language. |
| `run` | Resolve declared inputs, invoke operations, compose the graph and evaluate checks without exporting files. Callers can inspect a failed prerequisite or a successful result before choosing what to persist. |
| `WorkflowResult` | Return the graph together with the evidence needed to scrutinize it. Named Evidence, checks, findings, operations and metadata avoid requiring a second build just to explain the first. |
| `binding`, `condition`, `template` (internal) | Connect mappings to row observations, single-row context, literals and business keys without allowing executable expressions. Bindings return Claims as well as values so composition can retain support. |
| `composition.compose` | Turn Evidence and reviewed declarations into actual RK objects and Facts. Stable business keys preserve identity across source editions; canonical construction and relationship-derived membership preserve graph meaning. |
| `CheckResult` / `checking.evaluate` | Keep operands, scopes, missing contributors and graph targets available after a comparison. This distinguishes exact membership agreement, source fidelity and independent reconciliation from a bare pass/fail count. |
| `SourceCheck` / `source_checks.evaluate` (internal) | Report source health and unavailable observations, including material intentionally excluded from the graph. A valid graph does not prove its supporting workbook was complete or freshly calculated. |
| `Finding` (internal) | Retain a construction limitation or deferred interpretation that does not map neatly to an input cell or a numeric comparison. It explains why something was omitted or remains provisional. |
| `review.render` / `export` | Provide shared inspection and an explicit artifact-writing boundary for CLI and notebook callers. Rendering does not replace Claims; exporting does not occur implicitly inside `run`. |
| `json.dumps` / `loads` / `write` / `read` | Preserve the actual graph and canonical shared references for independent comparison and later use. A viewer projection or fingerprint cannot serve as a complete reloadable reference. |

Sources: [specifications](../src/rangekeeper/graph/workflow/specification.py),
[runtime](../src/rangekeeper/graph/workflow/runtime.py),
[composition](../src/rangekeeper/graph/workflow/composition.py),
[checks](../src/rangekeeper/graph/workflow/checking.py),
[source checks](../src/rangekeeper/graph/workflow/source_checks.py),
[review](../src/rangekeeper/graph/workflow/review.py),
[persistence](../src/rangekeeper/graph/adapter/json.py).

## Package boundary and direct use

Format-specific code belongs to `graph.adapter`; reusable graph-building code
belongs to `graph.workflow`, with table Evidence in `workflow.ingestion`.
`graph.operation` and `graph.provenance` retain shared invocation and assertion
contracts. The workflow package loads lazily: Excel imports do not load the runner.

`composition.compose(model, outputs, settings, decisions, operation,
namespace=...)` takes explicit reviewed declarations and named Evidence.
`checking.evaluate(checks, graph, by_key, outputs)` compares an existing graph.
Neither API requires a `WorkflowSpec`. `bindings.py` owns bounded value/condition
resolution; `references.py` owns presentation; `provenance.locations` owns generic
lineage traversal. The runner connects these capabilities through registered operation handlers.
Excel workflow wiring and native source health/addressing belong to
`adapter.excel.workflow`; the generic runner never inspects native objects.

`ingestion.predicates.Predicate` and `select_where` provide exact-type filtering
through existing selection semantics. `excel.extract_table(..., unique_stop=True)`
checks the entire native marker column, including rows before extraction starts,
using the same error/cache-aware matcher as extraction.

`OperationDeclaration` joins parsing, dependencies, schema fields, execution and
output description in one closed descriptor. The catalog explicitly assembles
RK-owned handlers; it is not a plugin API.
`schema()` describes steps only; model/check validation is performed by `load`.
`implementation.manifests` retains full Python byte hashes for audit and a separate
versioned semantic AST manifest. Comments, docstrings and presentation modules do
not change semantic identities; executable changes in the declared computation
modules do. `metadata.step_operations` associates dispatch/native records.

## Named policy ownership

Project YAML may share complete numeric specification sets and measurement binding
sets. `workflow._shared` resolves those two forms at load time; it does not execute
steps or add a template language. `composition.validate_measurements` validates
both definitions and resolved uses so unused invalid policies are caught and
measurement collisions cannot be silently overwritten. `WorkflowSpec.declarations`
retains origins for review and configuration lineage. Existing ingestion and
composition algorithms still consume explicit declarations. See the
[shared policy contract](GRAPH_YAML_WORKFLOW.md#shared-numeric-specifications).
