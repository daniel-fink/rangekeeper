# Format-independent source workflows

The workflow catalog connects declared operations to format-owned handlers.
Source workflows build canonical Models; the mathematical executor consumes
Model and Specification revisions separately. See [consumer contracts](CONSUMER_MIGRATION.md).

## Ownership

| Module | Purpose |
| --- | --- |
| `workflow/catalog.py` | Explicitly assemble the RK-owned operations and native source checks. This is the only composition point that selects concrete format integrations. |
| `workflow/_contracts.py` | Declare request parsing, dependency kinds, schema fields, execution and audit identity together. `ExecutionContext` contains only ambient inputs; `Produced` carries a native value, fingerprint and optional Source without changing its representation. |
| `adapters/excel/workflow.py` | Connect existing Excel APIs to the catalog; own Excel request wrappers, source-check registration and native address presentation. Importing the direct Excel API does not import this integration. |
| `adapters/excel/inspection.py` | Inspect cached formulas and error cells in the existing Workbook snapshot. Its health observations have no dependency on workflow result types. |
| `workflow/_table_operations.py` | Connect existing format-independent Evidence transformations to declarations; own their request contracts and schema fields. |
| `workflow/runtime.py` | Establish configuration, resolve named outputs, execute declared steps, retain native operation records, compose, check and return. It contains no Excel import, native type switch or format operation names. |
| `workflow/implementation.py` | Fingerprint shared computation and the declared module groups for selected capabilities; retain the full installed-code audit separately. |
| `workflow/provenance.py` | Establish configuration/decision lineage, convert source support to canonical records, and retain source and deferred-record metadata. |
| `workflow/_schema.py`, `specification.py` | Assemble the published step schema and load/validate the four reviewed documents. The specification owner expands shared number and measurement declarations before request construction. |
| `workflow/_model_validation.py`, `composition.py` | Validate declarations, then build definitions, object characteristics, relationships and final Assembly membership. One private construction object owns temporary indexes and attaches final object Facts after membership finalization. |
| `workflow/_operands.py`, `checking.py` | Keep each operand's value, support, targets and completeness together; evaluate comparisons and graph invariants separately. |
| `workflow/references.py` | Preserve every Location. Registered formatters improve presentation; other locations use a deterministic structured fallback. |
| `shared/encoding.py`, `shared/structured.py`, `workflow/operation.py` | Shared scalar encoding and structured requests; lightweight source invocation contracts load no catalog, runner or adapter. |

Use `BoundaryError` and `EncodingError` from `rangekeeper.shared.errors`. The former
`AdapterError` and `AdapterEncodingError` aliases are removed. Evidence-specific encoding failures still raise
`EvidenceValidationError`. Request types are imported from their capability owner,
such as `adapters.excel.workflow` or `workflow._table_operations`; the dynamic
aliases in `workflow.specification` are removed.

`workflow/evidence/` owns Claims, Table Evidence, validation, fingerprints and transforms.
`Produced.from_evidence` retains the exact Evidence object and its fingerprint without
creating a native Source. Source checks reuse preparation only for the same Evidence
object within one call. Each new call prepares its inputs again.
`workflow.reporting` prepares shared report data once for HTML and exported checks;
`workflow.review` owns HTML and publication. `io._atomic` owns file replacement and
create-only mechanics; both review builders use its `replace_json` operation. Layout review is separate at
`adapters.cytoscape.layout.review`, with an explicit Model and bundle input.

Publication distinguishes visibility from durability. A failure before pointer
replacement leaves the previous bundle current. If replacement succeeds but the
directory sync fails, the new bundle is current; workflow and layout review report
completion with a durability diagnostic. Later observer or status-record failures
also retain the completed result. Cancellation still raises `KeyboardInterrupt`;
after publication its `completed_attempt` retains the output and diagnostics even
if the completed status record cannot be written. The workflow implementation fingerprint and
exported dependency metadata include `jsonschema`, which validates domain records.

## Adding a capability

1. Implement and test its native adapter independently of the runner. Native
   snapshots need no common superclass and do not need to masquerade as tables.
2. Add an immutable request dataclass and strict mapping policy in its workflow
   integration. Declare named dependencies, output kind, schema fields, executor,
   output description and computation-module/dependency groups. Nested request
   policies are parsed by the request's `from_mapping` method. Repeated inputs are
   declared explicitly; the catalog does not infer policy or wiring from field names.
3. Explicitly include its declarations in the closed catalog. Add a native source
   check or location formatter only when that capability needs one.
4. Test parsing, mismatched inputs, missing prerequisites, native source metadata,
   fingerprints, locations and determinism through the existing runner.

The synthetic record-document test in `test_workflow_formats.py` demonstrates this
path without importing a native source into table Evidence prematurely. It covers
native intermediates, table extraction, graph composition, record-addressed
provenance, source checks, deferred metadata, failed prerequisites and repeated runs.
It also confirms that unused Excel dependency versions are not queried.

This does not implement CSV, IFC or PDF. Production Evidence validation remains
Table-only; new representations require contracts grounded in actual inputs.
There is no plugin discovery, import selected by YAML, adapter inheritance tree,
scheduler or expression engine. The operation and source-check catalogs are private
RK implementation assembly, not public runtime extension APIs.

## Explanation and compatibility changes

- `CheckResult.left` and `right` retain each operand's value, Claims, targets,
  missing contributors and known subtotal. The old flattened fields are removed.
  Count reports derive display counts without discarding members. Explicit
  `to_mapping()` output uses `rk.workflow-checks/v2`; HTML uses the same prepared
  report and exposes both operands' completeness. `status` is `CheckStatus`;
  authored report categories remain strings.
- Missing check columns produce `missing_column` Diagnostics, including on empty
  table scopes. Unexpected programming errors are not converted into Outcomes.
- Review references now also show configuration and non-cell Locations. Existing
  source references remain present. The historical Mandarin comparator excludes
  only configuration locations verified against the recorded run fingerprint;
  arbitrary added or removed source references still fail comparison.
- Deferred metadata adds `deferred_evidence`, containing table/row identity and
  structured source locations. Excel's existing deferred tokens remain unchanged;
  other formats have a row-identity fallback.
- Workflow-run and semantic-manifest versions are 5. Derived Claims and
  configuration fingerprints change; business identities and graph meaning do not.
  The semantic manifest covers the evidence package, shared graph operations,
  record/index behavior and the selected integrations. It includes the actual
  `py-moneyed` dependency version and the actual currency catalogue codes.
  Presentation-only report changes are excluded;
  exact installed-code audits still record those files.
- Export uses dependency metadata captured during the build, rather than imposing
  an Excel dependency list after execution.
