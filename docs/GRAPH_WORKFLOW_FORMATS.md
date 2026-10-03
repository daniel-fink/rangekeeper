# Format-independent workflow execution

> Historical source/Graph contract, superseded for new builds on 2026-10-03.
> Use [Model consumer migration](CONSUMER_MIGRATION.md) for the current packages,
> workflow version 2, Value keys, and Model export. The earlier API names and
> acceptance results below remain evidence for the external migration gate (6E).

**Scope, 2026-10-02:** the implementation and validation below concern the
existing source-to-Graph workflow. The [library architecture](LIBRARY_ARCHITECTURE.md)
plans its later migration to canonical Model objects. This workflow executor is
separate from the implemented equation-solving `rangekeeper.execution` service;
its delivery counts are historical acceptance evidence.

Implemented and pushed as RK `588b5b412e52f5b32919a72a19d31df423378edb`, paired
with projects `68baa2b88324d9f7fcaf794f59512a8bce720c0a`. The existing YAML
operation names and `load`, `run`, `schema` entry points are preserved.
The paired delivery PRs are [RK #32](https://github.com/daniel-fink/rangekeeper/pull/32)
into `feature/graph` and [Projects #1](https://github.com/daniel-fink/whirlwind-projects/pull/1)
into `main`. These exact implementation checkpoints remain the reproduction pins.

## Ownership

| Module | Purpose |
| --- | --- |
| `workflow/catalog.py` | Explicitly assemble the RK-owned operations and native source checks. This is the only composition point that selects concrete format integrations. |
| `workflow/_contracts.py` | Declare request parsing, dependency kinds, schema fields, execution and audit identity together. `ExecutionContext` contains only ambient inputs; `Produced` carries a native value, fingerprint and optional Source without changing its representation. |
| `adapter/excel/workflow.py` | Connect existing Excel APIs to the catalog; own Excel request wrappers, source-check registration and native address presentation. Importing the direct Excel API does not import this integration. |
| `adapter/excel/inspection.py` | Inspect cached formulas and error cells in the existing Workbook snapshot. Its health observations have no dependency on workflow result types. |
| `workflow/_table_operations.py` | Connect existing format-independent Evidence transformations to declarations; own their request contracts and schema fields. |
| `workflow/_execution.py` | Resolve earlier named outputs, pass read-only declared inputs to each handler, retain dispatch/native operation records and stop on unavailable prerequisites. |
| `workflow/runtime.py` | Establish configuration, execute steps, compose, check and return. It contains no Excel import, native type switch or format operation names. |
| `workflow/_audit.py`, `implementation.py` | Establish configuration/decision lineage, retain source and deferred-record metadata, and fingerprint shared computation plus selected capabilities' declared module groups. |
| `workflow/_schema.py`, `specification.py` | Assemble the published step schema and load/validate the four reviewed documents. Shared policy expansion still precedes request construction. |
| `workflow/_model_validation.py`, `composition.py` | Validate declarations, then build definitions, object characteristics, relationships and final Assembly membership. One private construction object owns temporary indexes and attaches final object Facts after membership finalization. |
| `workflow/_operands.py`, `checking.py` | Keep each operand's value, support, targets and completeness together; evaluate comparisons and graph invariants separately. |
| `workflow/references.py` | Preserve every Location. Registered formatters improve presentation; other locations use a deterministic structured fallback. |
| `graph/_encoding.py`, `_structured.py`, `operation.py` | Shared scalar encoding, structured requests, severity and invocation contracts with no dependency on workflow ingestion or adapters. |

`AdapterError` and `AdapterEncodingError` remain compatibility imports for the shared
boundary errors. Evidence-specific encoding failures still raise
`EvidenceValidationError`. Existing Python request imports from `specification`
remain available; their implementations now live with the corresponding capability.

## Adding a capability

1. Implement and test its native adapter independently of the runner. Native
   snapshots need no common superclass and do not need to masquerade as tables.
2. Add an immutable request dataclass and strict mapping policy in its workflow
   integration. Declare named dependencies, output kind, schema fields, executor,
   output description and computation-module/dependency groups.
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

- `CheckResult.left_missing`, `right_missing`, `left_known_subtotal` and
  `right_known_subtotal` preserve both operands. Legacy `missing` and
  `known_subtotal` retain their left-side meaning. HTML review exposes incomplete
  operands without suggesting that a known subtotal is complete.
- Missing check columns produce `missing_column` Diagnostics, including on empty
  table scopes. Unexpected programming errors are not converted into Outcomes.
- Review references now also show configuration and non-cell Locations. Existing
  source references remain present. The historical Mandarin comparator excludes
  only configuration locations verified against the recorded run fingerprint;
  arbitrary added or removed source references still fail comparison.
- Deferred metadata adds `deferred_evidence`, containing table/row identity and
  structured source locations. Excel's existing deferred tokens remain unchanged;
  other formats have a row-identity fallback.
- Workflow-run, checks and semantic-manifest versions are updated. Derived Claims
  and configuration fingerprints change; business identities and graph meaning do
  not. Exact-code audits remain separate from conservative semantic fingerprints.
- Export uses dependency metadata captured during the build, rather than imposing
  an Excel dependency list after execution.

## Acceptance

The RK graph/serialization/operation/Excel/ingestion/workflow suite passes 291
checks, including 12 new format-boundary regressions. Before fixes, the six initial
regression cases failed as expected. Ruff and focused type checks pass.

Mandarin and both East Whisman scenarios retain complete graph content and each
Fact's source-cell and reviewed-decision support. Existing check operands, outcomes,
scopes, source checks, findings and deferred records remain equivalent. Only the
explicit additions above are normalized during cross-implementation comparison.

Project validation, clean-environment checks and notebook evidence are recorded in
the projects repository's `docs/format-independent-workflow.md` and ignored
`artifacts/format-refactor/` directories. No source interpretation is resolved by
this architectural change. No project YAML or handwritten notebook content changes.
