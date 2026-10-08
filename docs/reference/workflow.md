# Source workflow configuration and builds

`rangekeeper.workflow` loads reviewed source configuration and builds a canonical
Model with its Evidence, checks and invocation records. `WorkflowSpec` is distinct
from mathematical `Specification`; a source `Outcome` is distinct from a solver
`Run`. Read the [concepts](../concepts/source-workflows.md) and
[build guide](../guides/source-workflows.md) for rationale and execution steps.

## Configuration

`load(spec_directory)` reads `sources.yaml`, `model.yaml`, `decisions.yaml` and
`checks.yaml`. Each outer document requires integer `version: 2`; there is no
implicit conversion of earlier versions. Excel extraction policies retain their
own version 1. The loader records exact file hashes, expands shared declarations
and returns an immutable `WorkflowSpec`.

| Document | Responsibility |
| --- | --- |
| `sources.yaml` | Namespace, ordered named steps, explicit dependencies and optional `number_sets`. |
| `model.yaml` | Definitions, object templates, explicit objects, Values, Labels, relationships, memberships, findings and optional `measurement_sets`. |
| `decisions.yaml` | Reviewed decision identities, status, text, source, date and mapping references. |
| `checks.yaml` | Comparisons, invariants, native source checks and declared deferred/review metadata. |

`StepSpec` binds `id`, `operation` and a typed request. The closed catalog validates
operation names, request types and dependency kinds. Dependencies must reference
earlier steps. Unknown operations, missing/later inputs, invalid fields and
malformed configuration fail before source execution. YAML is data; it cannot
select an arbitrary import or callable. The shared YAML decoder rejects duplicate
keys, executable tags, merge keys and cyclic structures.

Shared number and measurement sets are expanded before request construction.
Definitions are validated even when unused. Each use gets its own resolved
settings; sharing does not infer a dependency, row context or total policy. Import
request contracts from their capability owner, such as `adapters.excel.workflow`
or `workflow._table_operations`. Those private integration modules are not a
runtime plugin API.

## Model declarations

A Measure supplies `code`, `name`, `units`, optional `definition` and `tags`.
Aggregation and interpretation policy belong to the operation using it. Each
`measurements` entry requires its own `key`, `measure` and `binding`:

```yaml
measurements:
  - key: net
    measure: area
    binding: {column: parsed_net}
  - key: gross
    measure: area
    binding: {column: parsed_gross}
```

Entries create owner-local Values. `kind` defaults to `measurement`; `parameter`
and `decision` are explicit alternatives. `integer: true` rejects fractional
readings. Numeric bindings require interpreted finite numeric evidence; booleans
and numeric strings are not measurements. An unavailable reading creates a declared
Value with no quantity. A false `when` condition omits the Value. Multiple keys
can use one Measure; duplicate local keys fail.

`properties` entries use `key` and `binding` to create property Values with encoded
content. `on_unavailable.property` can retain a descriptive source fallback beside
an unresolved measurement and a finding. This does not convert missing quantities
to zero. Legacy `features` and `on_unavailable.feature` are rejected. Supported
property content belongs in Values, not opaque Claims used as substitute state.
Labels bind declared classifications; they do not infer classification from an
unreviewed source label.

Composition uses stable business-key UUIDs for objects and owner-local keys for
Values. Assemblies live in `System.assemblies`. Relationships and memberships are
explicit. A Model revision UUID derives from the complete built content, including
provenance. Identical builds have the same revision; changed source content or
support changes the revision. A source build does not infer a predecessor. Use
`Model.revise` when a predecessor relationship is intended.

`Model.create` validates the candidate before returning it. An invalid candidate
is not stored as a partial Model. See [Model contracts](model.md) and
[identity](identity.md) for canonical validation and revision rules.

## Operations, outcomes and diagnostics

`rangekeeper.workflow.operation` owns these immutable records:

| Record | Fields and contract |
| --- | --- |
| `Operation` | Versioned `method`, effective `specification` and named `inputs` fingerprints. A `None` input fingerprint identifies an input that could not be acquired. |
| `Diagnostic` | Stable `code`, canonical `Severity`, human `message`, real source `locations` and structured `details`. |
| `Outcome[T]` | `operation`, optional `output` and `diagnostics`. No output requires at least one diagnostic. An empty Table can be a successful output. |

An Operation describes an invocation; it is neither an executable algorithm nor a
unique job ID. Structured settings are defensively copied and deeply frozen.
Mappings have string keys, lists/tuples become tuples, and supported immutable
scalar types remain distinct. Unsupported objects and nonfinite numbers are
rejected without stringification. Normalization does not trim observations,
coerce numeric strings or infer a project rule.

`operation.fingerprint` binds method code/version, effective settings and named
inputs using `rk.operation/v1`. Mapping insertion order is irrelevant; sequence
order matters. `1`, `1.0`, `True` and `"1"` differ. Timestamps and job IDs are not
part of this invocation identity. Exact source/configuration file hashes are
separate recorded inputs and can affect the build even when only formatting
changes.

Expected source/request incompatibilities return unavailable Outcomes with
Diagnostics. Invalid API types, invalid requests and unexpected programming errors
remain exceptions at the direct operation/runner boundary. The workbench has a
separate attempt boundary described below. A search with no matches returns a
successful empty page. Severity is for review; it does not determine availability.

Diagnostics concern an invocation and can exist before output exists. Addressed
[Evidence Issues](evidence.md#issues) concern a produced artifact. Do not duplicate
cell Issues into Diagnostics just to announce them again. A missing sheet refers
to the actual workbook root; an unavailable file has no fabricated Source or
Location. Use codes and documented detail fields for machine handling, not message
or operating-system exception prose.

## Build result and checks

`run(spec, *, input_root, on_progress=None)` returns `Outcome[WorkflowResult]`.
It reads declared sources, executes steps, composes and checks. It does not export,
publish revisions or solve equations. Expected unavailable inputs and invalid
Model candidates return diagnostics with no output; unexpected defects propagate.
Observer failures become reporting diagnostics and do not change Model content or
semantic fingerprints.

`WorkflowResult` retains `model`, named `evidence`, `checks`, `source_checks`,
`findings`, `operations` and immutable `metadata`. Metadata retains source
fingerprints, effective configuration, decisions, deferred evidence and exact and
semantic implementation manifests.

Source Claims preserve native observations, locations, source checksums, methods
and upstream support. `workflow.provenance` converts these transient chains to
schema Claims using `rk.source-value/v1`. Dates, tuples, `False`, zero and
unavailable observations remain distinct. Fact Claims record their supported
declarations with canonical UUID links. See [Evidence](evidence.md) for the
transient/canonical distinction.

Check operands include `table_keys`, `table_count`, `table_total`, `model_keys`,
`model_count`, `model_total`, `model_value` and `membership_keys`, plus explicit
value/binding operands. Model Value selection uses `value_key`; total and individual
quantity comparisons require `units`. Missing columns produce a `missing_column`
Diagnostic, including for empty scopes.

Each `CheckResult.left` and `.right` is an operand with `value`, Claims, targets,
missing contributors and a known subtotal. A known subtotal is not a complete
result. Count displays retain their underlying members. `CheckStatus` is `AGREE`,
`DIFFERENCE` or `UNAVAILABLE`; authored categories remain strings. Exported checks
use `rk.workflow-checks/v2` with explicit left/right operands. Report preparation
is shared by HTML and JSON so completeness is not lost in presentation.

All source Locations survive reporting. Format integrations can supply readable
references; unknown formats use structured fallback text. Deferred metadata retains
Evidence table/row identity and structured source locations, rather than inventing
Excel addresses for other formats. Check reports do not select a conflicting Fact
Claim as an RK Reconciliation would.

## Workbench and publication

`workflow.review.export(result, destination)` explicitly writes `model.json`,
`checks.json`, `manifest.json`, `viewer.html` and `review.html`. Use a fresh
destination; canonical JSON writing is create-only. A viewer is a display document,
not Model persistence. Use [revision stores](run-and-storage.md) for durable domain
revision storage.

| Workbench operation | Result and side effects |
| --- | --- |
| `workbench.inspect(spec_directory, *, input_root, output_root)` | Returns `Inspection` with source/configuration state and previous successful bundle. Creates no files. Changed/missing inputs or damaged output become diagnostics. |
| `workbench.build(spec_directory, *, input_root, output_root, on_progress=None)` | Runs an independent build, verifies inputs did not change, exports and checks a new bundle, then publishes its pointer. Returns an `Attempt`; a failed attempt has no result. |
| `workbench.notebook_progress()` | Creates an optional IPython observer. Display failures do not become semantic build failures. |

The workbench records unexpected exceptions as failed-attempt diagnostics with
their type and message. `KeyboardInterrupt` still propagates. Prior success remains
explicitly historical and is not substituted as a new failed attempt's result.
Bundles include Model diffs, decision/clarification review and integrity metadata.
Their `run.json` is workbench metadata, not a mathematical Run.

Publication distinguishes visibility from durability. Before successful pointer
replacement, a failure leaves the previous bundle current. If replacement succeeds
but directory synchronization fails, the new bundle is current and the returned
attempt remains completed with a durability diagnostic. Later observer or status
record failures also retain completion. Cancellation after publication exposes
`completed_attempt` on the interruption, even if its status record could not be
written. Layout review uses the same publication mechanics; its own input and
geometry contract is in [viewer/layout](viewer.md).

## Capability ownership and implementation identity

The closed catalog is the only assembly point that selects native integrations.
The runner resolves named outputs without importing Excel or switching on native
types. Each declaration keeps request parsing, input/output kinds, schema fields,
execution, native fingerprinting and code/dependency groups together.
`Produced` keeps a native value, its fingerprint and optional Source without
forcing it into a Table. Only supported table Evidence feeds Model composition.

Shared computation and selected capabilities contribute to workflow semantic
identity. The current run Method and semantic manifest use version 5. The manifest
covers Evidence, shared system operations, schema/record behavior and selected
integrations, including actual `jsonschema`, `py-moneyed` and currency-catalogue
inputs. Semantic source hashing excludes comments and docstrings. Presentation-only
reporting changes are excluded from computation identity; exact installed-file
hashes still record those files. Dependency metadata is captured during the build;
export does not impose unused Excel dependencies afterward.

To add a capability:

1. Implement and test the native adapter independently. Native snapshots need no
   common superclass and need not pretend to be Tables.
2. Add an immutable request and strict mapping policy. Declare dependencies,
   repeated inputs, output kind, schema fields, executor, native description and
   computation/dependency groups together.
3. Include it explicitly in the private catalog. Add native checks and location
   formatters only when needed.
4. Test invalid requests, wrong input kinds, failed prerequisites, locations,
   native metadata, fingerprints and repeated builds through the runner.

The catalog is not a public dynamic plugin API. There is no YAML-selected import,
automatic plugin discovery, scheduler or general expression engine. The current
source-document implementation is Excel. CSV Table interchange does not provide
source-bound Document/Evidence acquisition. IFC, PDF, Word and live Google document
connectors are not implemented. Evidence validation currently accepts only the
exact Table type; a new representation needs its own grounded contract.
