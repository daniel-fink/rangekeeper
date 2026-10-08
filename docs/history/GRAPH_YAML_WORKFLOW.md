# Typed graph persistence and YAML workflows

> Historical design or implementation record. Names, commands and status below describe that checkpoint. Use the [current documentation](../README.md) for supported APIs.

> Historical source/Graph contract, superseded for new builds on 2026-10-03.
> Use [Model consumer migration](../reference/tables.md) for the current packages,
> workflow version 2, Value keys, and Model export. The earlier API names and
> acceptance results below remain evidence for the external migration gate (6E).

For the purpose of each API, read [Why the adapter APIs exist](../concepts/source-workflows.md).
The [boundary review](GRAPH_ADAPTER_REVIEW.md) records historical findings and
implemented resolutions. The [format-independent follow-up](../reference/workflow.md)
records the later delivery.

**Scope, 2026-10-02:** these are the existing graph persistence and source-building
APIs. Their `model.yaml`, `WorkflowSpec`, and workflow `run` are not the new
schema Model, mathematical Specification, or finalized Run. The graph JSON format
below is not the new Model interchange contract. Follow the
[library plan](../concepts/architecture.md) for their staged migration.

Install `rangekeeper[workflow]` for the bounded Excel/YAML workflow. YAML support is
optional and uses PyYAML's safe loader with duplicate-key and alias rejection. No
Pydantic, dynamic plugins, callable imports, Python expressions or formula
recalculation are added by this API.

## Graph JSON

```python
from rangekeeper.graph.adapter import json
content = json.dumps(graph)
restored = json.loads(content)
json.write(graph, path)
restored = json.read(path)
```

The `rk.graph` format has integer version `1`, a sorted identity-record list and a
root object. Explicit registered type names are data tags, never import paths.
Identity references restore canonical definitions, graph objects, Sources and
shared Claims; Facts target the registered graph instances. Constructors validate
the decoded graph. Duplicate identities, unknown fields/types/versions, dangling
or cyclic references, unreferenced records and invalid constructor state fail.

Supported payloads are None, booleans, integers, finite floats (hexadecimal), text,
UUID, date/datetime/time/timedelta, fixed or named timezones with fold, RK enums,
scalar Pint quantities/units, dict/mappingproxy, list, tuple, frozenset and registered
RK graph-state values. Mapping order and value-type distinctions are preserved.
Unsupported objects and cyclic containers raise `AdapterEncodingError`; values
are never silently stringified. Write validates first and atomically replaces one
file. The format is intentionally explicit rather than general Python persistence.

## Workflow API

```python
from rangekeeper.graph.workflow import load, run, schema
spec = load(spec_directory)
outcome = run(spec, input_root=input_directory)
if outcome.output is not None:
    result = outcome.output
```

`WorkflowSpec` is immutable. `WorkflowResult` contains the native RK Graph, named
Evidence, comparison/source-check results, findings, ordered Operations and
reproducibility metadata. `run` exports nothing. Missing/incompatible source inputs
return an unavailable Outcome with Diagnostics; malformed declarations raise
validation errors. Execution stops at the first failed prerequisite. There is no
artifact fallback or scheduler.

```sh
python -m rangekeeper.graph.workflow \
  --spec spec --inputs inputs --output artifacts/rebuild
```

The CLI writes graph JSON, checks, manifest, an offline graph/provenance viewer and
escaped Evidence/check review HTML only after a successful build. A difference or
an unavailable comparison is a review result, not an invocation failure. The
shared `workflow.review.render` and explicit `export` functions also serve notebooks.

## Four documents

Every file has `version: 1`; this is the RK workflow schema, not any earlier project
schema. `load` reads exactly `sources.yaml`, `model.yaml`, `decisions.yaml` and
`checks.yaml`. No includes, YAML aliases or implicit source-selected imports exist.

### Sources

Declare `namespace` and ordered `steps`. Each step has a unique `id`, a registered
`operation` and its typed request fields. Inputs must name earlier outputs of the
right kind. `schema()` returns JSON-serializable parameter schemas for this closed
catalog. `StepSpec.from_mapping`/`to_mapping` round-trip effective requests;
nested extraction, numeric and transformation requests use their own strict types.

| Operation | Request fields | Output |
| --- | --- | --- |
| `read` | `files`, `source_key`, optional `checksum` | Native Workbook snapshot. Multiple candidate filenames must contain identical bytes. Resolved paths stay beneath input root. |
| `extract` | `input`, `specification: ExtractionSpec`, optional `unique_stop` | Evidence Table; layout guards and cached formula policy are inherited from Excel extraction. |
| `classify_rows` | `input`, `workbook`, `specification: RowClassificationSpec` | Original columns plus `blank`, `matched` or `other` in the declared output column. |
| `numbers` | `input`, `specifications: output → NumberSpec` | Original observations plus numeric Claims. |
| `transform` | `input`, `specifications: output → TransformSpec` | Ordered derived columns; later transformations may reference earlier appended columns. |
| `select` | `input`, optional `columns`, `row_ids` or `where` | Preserved Claims/row IDs. `where` declares one column and `equals` or `in`. |
| `concat` | ordered `inputs` | Compatible tables with original Claims and confined Issue scopes. |

`unique_stop` requires exactly one declared stopping marker anywhere in its native
column. `excel.classify_rows` consumes existing native observations without opening
Excel again: a formula without a cache is occupied, not physically blank. Selected
columns must resolve to cells in one physical row. Classification preserves all
source Claims and Issues. `RowClassificationSpec` declares `identifier`, `pattern`,
optional `output` and optional physical `columns`.

`ingestion.transform.TransformSpec` declares `operation`, ordered input `columns`
and only applicable options:

- `normalize`: trim and optional `case` (`preserve`, `lower`, `upper`, `casefold`).
- `capture`, `capture_integer`, `match`: full-match `pattern`, numeric `group` and
  optional `flags: ignorecase`. Integer conversion is confined to an explicit
  capture; NumberSpec still rejects numeric strings.
- `lookup`: explicit `values` and optional `default` for an available unknown text.
- `agreement`: available observations must agree in both value and type. A conflict
  is unavailable with an Issue; all unavailable inputs remain unavailable.
- `fallback`: choose the first available observation in declared order.
- `format`: a literal `template` using only plain declared input names. Attribute
  access, conversion flags and format expressions are rejected.

Every derived Claim includes its source Claims and effective configuration Claim.
Unknown suffixes stay unknown. Source Issues remain available; unavailable derived
outputs carry applicable explanations. Issue severity never chooses availability.

### Shared numeric specifications

`number_sets` in `sources.yaml` names complete ordered mappings of output columns
to existing NumberSpec declarations. A `numbers` step chooses exactly one of
inline `specifications` or `specifications_ref`:

```yaml
number_sets:
  equipment_sizes:
    number_size:
      column: size
      integer: false
      nonnegative: true
      missing_markers: ['-', '–', '—']
steps:
  # Earlier read/extract/select steps remain explicit.
  - id: numeric
    operation: numbers
    input: selected
    specifications_ref: equipment_sizes
```

This shares admissibility policy, not observations or Claim identities. Each use
still derives its own Claims from its own input Evidence and configuration.
Whole-set references preserve order. There is no inheritance, nested reference,
merge, override, external include or executable substitution. Unused definitions
are validated too. Existing inline version-1 documents remain valid.

### Model

Declare `taxonomy`, ordered `classifications` (with optional parent code), `measures`
(with units, QuantityKind and AggregationRule), `templates`, `objects`,
`relationships` and selected `memberships` classification codes. `acyclic` defaults
to true for those membership relationships. Multiple Assemblies may share a member;
atomic graph totals do not double-count it.

Templates declare `id`, `table`, `kind: entity|assembly`, `identity_kind`, `key`,
`name` and `classification`. Explicit objects omit `table` and use a literal key.
Optional features, measurements, labels, evidence, decisions, conditions and findings
are evaluated through the same native graph constructors. No parallel graph or
project record type is introduced.

Bindings are exactly `{column: name}`, `{evidence: prior_output, column: name}`
(for single-row context Evidence), or `{value: literal}`. Heading/context Claims
remain named sourced Evidence; they need not be copied across table rows.
Conditions declare `binding` and exactly one of `equals`, `in` or `available`.

A feature declares `name`, `binding`, optional `omit_unavailable`; a measurement
has `measure`, `binding` and optional `on_unavailable` finding/raw-feature policy.
Measurements accept interpreted numeric values and use canonical Measure units.
Labels declare `name` and ordered `bindings` resolving classification codes;
unavailable classifications are omitted. Each can attach specific Evidence and
reviewed decision IDs. Every supported object and characteristic receives a Fact.

Relationship endpoints declare `{kind, key: binding}` business references.
`identity_kind` and `key` use `{source_key}`, `{target_key}`, `{source_id}` and
`{target_id}` only. Missing endpoints default to failure; explicit `unmatched:
finding` retains the unsupported association as a finding. Assembly membership is
constructed from exactly the selected outgoing relationships. Duplicate business
keys and relationship identities fail.

Identity is `uuid5(uuid5(NAMESPACE_URL, namespace), json.dumps([kind, key],
ensure_ascii=False))`, including the standard JSON separator spaces. Derived
characteristics use owner UUID and declared characteristic key. Source rows,
editions and measured values do not form part of business identity.

Optional `findings`, supporting `deferred` row declarations and deferred `aggregates`
retain limitations. Enabled aggregate calculations must be explicit check operands;
a deferred model policy does not perform an allocation or alter Measure semantics.

### Shared measurement bindings

`measurement_sets` in `model.yaml` names ordered lists of the existing measurement
declarations. A template or explicit object chooses inline `measurements` or a
`measurements_ref`, never both:

```yaml
measurement_sets:
  equipment_readings:
    - measure: size
      binding: {column: number_size}
      on_unavailable:
        topic: Unavailable measurement
        explanation: No zero is inferred from absent source evidence.
# Within an existing row-driven template:
# measurements_ref: equipment_readings
```

By default relative bindings use the consumer's current row. Add
`measurements_evidence: reported_total` beside `measurements_ref` to bind them to
named single-row Evidence instead. This applies to the measurement value,
conditions, additional supporting Evidence and on-unavailable bindings. Explicit
`evidence` references and literal values retain their meaning. Each use receives
an independent copy; assigning one total cannot mutate another consumer's policy.
An explicit object must provide context for every relative binding. A multi-row
named context returns the existing unavailable `ambiguous_evidence` Outcome when
consumed; an unknown context is a declaration error. Duplicate measures within
one measurement list are rejected, including conditional duplicates; use one
explicit selection upstream rather than ambiguous declarations.

Resolution belongs to `load`, before `WorkflowSpec` construction. Direct
`StepSpec`, `NumbersSpec`, `WorkflowSpec` and composition APIs continue to receive
effective inline declarations. Definitions and uses are frozen in
`WorkflowSpec.declarations`, alongside the authored file hashes and resolved
`to_mapping()` values. Definitions carry consumer/definition paths in `uses`, plus
any explicitly supplied Evidence context. Unknown or malformed sets fail before
source execution. Errors identify the definition or consumer and set name.

For builds using sets, `manifest.json` includes `effective_specification` with
resolved declarations, original definitions and reference origins. The review
HTML exposes the same data under **Shared declarations and effective specification**.
`schema()` describes shared definitions and use fields as well as the operation
catalog; it does not yet describe the complete graph/check language. Configuration
hashes and derived Claim IDs may change after re-authoring; business identity,
source support and substantive results must be compared separately.

### Decisions

`decisions` retain `id`, `status`, `text`, `source`, `date` and optional category,
mapping IDs and references. Mapping guidance may be retained under `mappings`.
Referenced decision IDs must exist; unresolved status is not automatically accepted.
Decisions and effective configuration enter derivation lineage. Source checksums
and complete specification hashes bind every build to its reviewed inputs.

### Checks

`comparisons` contain stable IDs, group/scope, left/right operands, optional ordered
`each` Evidence, scope column, tolerance, evidence, condition, purpose and category.
Supported operands: literal value, bound Evidence/column, graph keys/counts,
individual measurements, graph totals, table keys/counts/totals and Assembly member
keys. Population selectors, explicit eligibility tables, unit conversion and
membership scopes are declared data. `report: counts` retains the actual member
lists and compares those lists before displaying counts. Incomplete totals remain
unavailable and retain known subtotals and missing contributors. `purpose` separates
fidelity from independent reconciliation. Source-internal exceptions may use
`report_when: difference` without selecting a canonical graph value.

`invariants` include `fact_coverage`, `membership` and `defined_kinds`. Native source
checks include `workbook_health`, `identities`, `occupied_rows`, `numeric_issues`
and explicit deferred checks. The numeric checker reports unavailable observations
by source/reason without substituting zero. `notes` and `deferred` preserve scope.

## Reproducibility and examples

Operations record effective requests, ordered named input fingerprints and versioned
methods. Composition binds actual Evidence fingerprints; metadata also records RK
Python implementation hashes, package versions, specification hashes and source
editions. Repeated runs of identical inputs produce identical graph/Claim bytes.
Environment/checkpoint manifests should additionally pin repository revisions or
an exact uncommitted patch overlay; an editable dependency alone is not a pin.

See [the synthetic examples](../guides/source-workflows.md). The contract suite
covers canonical serialization, unsafe/malformed specs, cache/error/missingness
handling, conflicting interpretations, identity stability, wrong equal-count joins,
cycles, shared memberships, coverage and incomplete totals.

## Refactored package and identity contract

The CLI is `python -m rangekeeper.graph.workflow`; ingestion is imported from
`rangekeeper.graph.workflow.ingestion`. Format adapters remain under
`rangekeeper.graph.adapter`. The former adapter workflow/ingestion module paths
are no longer the public API. See the [API rationale guide](../concepts/source-workflows.md)
for direct composition/checking and shared-contract ownership.

Configuration fingerprints include the complete settings Claim lineage. Distinct
Issues with colliding projected identities make the operation unavailable rather
than discard an explanation. Both YAML loaders reject aliases, duplicate keys and
executable tags. Source-check and comparison operand fields are validated by kind.

Version-2 workflow and composition identities use a conservative manifest of
semantic Python ASTs; exact source bytes remain separately recorded for audit.
The AST encoder omits comments/docstrings, and presentation/CLI modules are outside
the computation manifest. This is intentionally conservative: any executable
change within the declared computation set invalidates derived identities.
`step_operations` links workflow dispatch fingerprints to their native invocations.


## Format-independent execution

The existing operation names and YAML shape are unchanged by the format-boundary
refactor. Operations are explicitly registered by RK code; their native input and
output kinds are validated before execution. YAML cannot install a handler or
select an import. See [ownership and extension guidance](../reference/workflow.md).

Check results now retain both operands' missing contributors and known subtotals.
The older `missing` and `known_subtotal` fields retain their left-side meaning.
Review references include configuration and non-Excel locations. Native source
metadata comes from producing handlers, and the manifest includes structured
`deferred_evidence` alongside existing Excel deferred-record tokens.
