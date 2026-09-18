# Ingestion evidence contract

Status: Evidence, document operations, Excel snapshots/extraction and shared
table transformations are implemented as of 18 September 2026. The wider workflow
sections also describe later stages; a general interpretation/composition YAML
executor remains deferred. This is not a hosted service, full IFC/GIS adapter,
or graph persistence format.

The [declarative ingestion workflow](ingestion-workflow.md) defines the overall
system and fresh-environment reproducibility requirement. This document specifies
the detailed Evidence data/API contract within that workflow.

## Purpose and boundaries

An adapter operation returns content together with inspectable evidence for its
declared outputs. The content may be tabular, spatial, a building model, or an
immutable reference to such content. Tabular structure is one specialization.

- RK implements source readers, addressing, typed transformations, graph
  composition and checks.
- Project specifications declare source locations, interpretations, mappings,
  identities, hierarchy, applicability and decision references.
- Project notebooks orchestrate those operations and present review results.
- A future service may store artifacts and expose the same operations as tools.

Reuse `graph.table.Table`, and provenance `Source`, `Location`, `Claim`, `Method`,
`Fact` and `Provenance`. Do not create another Record/RecordSet, source identity,
claim graph or graph-object model. `Fact` binds evidence to an existing graph
target; source Claims may exist before a graph is constructed.

## Core container

The public type in `rangekeeper.graph.adapter.ingestion` is:

```python
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, Generic, TypeVar
from uuid import UUID

from rangekeeper.graph.table import Table
from rangekeeper.graph.provenance import Claim

T = TypeVar("T")
EvidenceKey = tuple[str, ...]

@dataclass(frozen=True)
class Evidence(Generic[T]):
    name: str
    data: T
    claims: Mapping[EvidenceKey, Claim[Any]]
    issues: tuple[Issue, ...] = ()
```

`name` is a descriptive dataset name, not an identity or cache key. `data` is a
validated snapshot, not necessarily the original source. Its declared outputs
may be derived from several sources. `claims` associates output addresses with
one terminal Claim per output. Its upstream Claims retain candidates and inputs.
`issues` describes missing, invalid, conflicting or qualified outputs.

There is no universal `location_ids` or ordered object list. Ordering and native
object identity belong to the content adapter. Source identity and location
already exist in `Source` and `Location` reached through Claims.

The container's Python type is not its serialization format. JSON schemas and
artifact encodings must be versioned separately when implemented. Do not pickle
native sessions or use arbitrary object stringification as a transport contract.

## Addressing

An EvidenceKey identifies an output within one Evidence artifact. It is a tuple
of nonempty strings, with an adapter-defined grammar. In a tool request it is a
JSON array of strings, accompanied by the immutable artifact handle.

| Content | Address example |
| --- | --- |
| Tabular cell | `("rows", "<row UUID>", "interior_area")` |
| Tabular row, for issue scope | `("rows", "<row UUID>")` |
| Spatial geometry, illustrative | `("features", "<feature ID>", "geometry")` |
| IFC property, illustrative | `("objects", "<GlobalId>", "properties", "<set>", "<property>")` |
| Whole artifact, for issue scope | `()` |

Only the tabular grammar is specified for initial implementation. Spatial and
IFC grammars will be published by their respective adapters. They may use native
stable identifiers; UUID conversion is not universally required. Raw tuple
segments are not split on dots or slashes. Column keys are stable declared field
identifiers, separate from presentation labels.

Claim addresses must resolve to declared output values. Issue addresses may
identify valid cells, rows or the whole artifact. A nonexistent output cannot be
used as if it existed: an unmatched relationship target is reported against the
actual input row, with the attempted key in structured issue details.

Output addresses and source Locations are different. For example, a grouped
area total has one output address and may trace to hundreds of source cells.
A derived output need not have any single source Location of its own.

For native models, the Claims map defines which values have been extracted and
are supported as operation inputs. Other native content can remain available for
inspection, but a downstream interpretation must extract it with evidence before
using it. Do not invent Claims for every IFC property or geometry coordinate.
A whole immutable geometry may be one output value, or an immutable artifact
reference with a checksum.

## Tabular specialization

Table stores ordered `Row` objects, each bundling cell values with optional
identity. No existing Python Record class is present in the current RK graph
package; Row lives alongside Table rather than introducing a separate table or
provenance model.

```python
@dataclass(frozen=True, slots=True)
class Row:
    values: Mapping[str, object]
    id: UUID | None = None

@dataclass(frozen=True, slots=True, init=False)
class Table:
    columns: tuple[str, ...]
    rows: tuple[Row, ...]

    def __init__(self, columns, rows): ...
```

The tabular type is `Evidence[Table]`. Access cell values through
`evidence.data.rows[i].values` and identity through `evidence.data.rows[i].id`.
There is no parallel Table.row_ids field.
`Table.row(row_id: UUID)` returns the stored Row, including in mixed ordinary
Tables. It skips unidentified rows, raises TypeError for a non-UUID (including
None), and KeyError for an absent UUID. `tabular.row(evidence, row_id)` delegates
to it; evidence address failures are translated to `invalid_address` errors.

- Table construction accepts Row objects or plain mappings, normalizing mappings
  to unidentified Rows. Existing mapping-based construction remains valid;
  callers reading stored rows must use row.values (including dict(row.values)).
- Values are copied into a read-only mapping in Table column order. Row is frozen;
  Table permits arbitrary cell payloads, while Evidence enforces deep immutability.
- Ordinary Tables may contain multiple unidentified rows, or a mixture of
  identified and unidentified rows. Supplied IDs must be UUIDs and unique.
- Evidence requires an ID on every row; mixed/unidentified nonempty Tables are
  rejected. Empty Tables are valid without a separate identity marker.
- Table never generates random row IDs or infers them from current row positions.
  Readers and transformations supply IDs under their declared identity rules.
- `Table.from_view()` uses Entity UUIDs as row IDs. `from_arborescence()` preserves
  those IDs in its resulting traversal order. Spreadsheet extraction uses
  evidence-row UUIDs. These meanings remain distinct from each other.
- Sorting and filtering preserve surviving IDs. Joins, splits and grouping use
  the declared transformation identity rules below.
- IDs are metadata, not an automatic column. An explicitly selected `entity_id`
  column remains an ordinary exported column. Plain CSV/pandas conversions do
  not implicitly export metadata IDs or reconstruct them from values or an index;
  preserving IDs requires an explicit adapter encoding/mapping.

Every cell has a terminal Claim at `("rows", str(row_id), column)`. Claims,
source references and parsing issues remain in Evidence and existing provenance
objects, not in Table. Passing the plain Table to an existing display or format
adapter does not by itself carry lineage.

Construct tabular evidence from terminal Claims so values are not independently
entered twice:

```python
tabular.from_claims(
    *, name, columns, row_ids, claims, issues=()
) -> Evidence[Table]

tabular.row(evidence, row_id) -> Row
tabular.claim(evidence, row_id, column) -> Claim
tabular.issues_for(evidence, row_id, column=None) -> tuple[Issue, ...]
```

`from_claims` accepts row IDs to define the output order, then bundles each ID
with its Row. It does not store a parallel identity sequence. `tabular.row`
returns the complete Row; read a cell through `row.values[column]`.

`from_claims` derives each Table cell from the corresponding Claim.value and
validates the complete artifact. `row` resolves by ID, never by display index.
`issues_for` includes ancestor-scoped issues applicable to the requested row or
cell. Transformation methods are not also methods on Evidence: selection, join,
parse and reduction have one canonical operation implementation each.

## Value and lineage semantics

A typical spreadsheet extraction is:

1. A sourced Claim holds the original cell payload, including formula, cache,
   type and format as required, at the existing RK Location.
2. A derived Claim holds the extracted or parsed scalar, with the source Claim
   and the applicable rule evidence upstream.
3. The Table cell equals that terminal Claim's value.
4. A later unit assignment creates a new derived Claim and new output artifact.
5. Composition binds supported outputs to graph targets using existing Facts.

If extracting an unchanged scalar directly is sufficient, a sourced scalar Claim
may be terminal. A transformation must not relabel a derived value as sourced.
Unchanged outputs may reuse Claims. Decisions and specification rules enter
lineage as existing Claims; user attribution must remain distinguishable from an
LLM proposal. No acceptance is inferred from successful execution or silence.

`None` means no resolved output value in this ingestion contract, not a domain
assertion of nonexistence. It requires an applicable explanatory Issue; the operation catalogue will define
which codes explain which outcomes.
This initial contract does not use a separate semantic-null domain value. If a
future adapter needs that distinction, it must declare a typed value explicitly.

| Situation | Terminal value | Issue code example |
| --- | --- | --- |
| Valid zero | `0` | None |
| Blank input | `None` | `missing_value` |
| Formula without cached result | `None` | `missing_formula_cache` |
| Text rejected by numeric parser | `None` | `invalid_number` |
| Conflicting candidates | `None` | `conflicting_values` |
| Lookup without a recognized match | `None` | `unmatched_value` |
| Measured value needing review | Actual value | Advisory issue |

For a conflict, the terminal derived Claim has value None and references all
candidate Claims and the resolution rule. This says the operation did not resolve
a value; it does not select a candidate. The eventual graph's Fact/Reconciliation
semantics remain unchanged. A check report is not an RK Reconciliation, which
specifically selects a Claim for a conflicting Fact.

Downstream operations must use the declared availability and issue policy, not
only truthiness or `value is not None`. Zero and False remain real values. Missing
optional data can be informational; missing required identity data may block an
operation. Applicability is decided by the mapping or contributor-selection rule,
not by the mere presence or absence of a value.

## Issues

The shared type describes what happened, without deciding what another operation
may do with the evidence:

```python
class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

@dataclass(frozen=True, slots=True, kw_only=True)
class Issue:
    rule_id: str
    code: str
    severity: IssueSeverity
    message: str
    at: tuple[EvidenceKey, ...]
    related_claims: tuple[Claim[Any], ...] = ()
    details: Mapping[str, object] = field(default_factory=dict)
    id: str = field(init=False)
```

There is no `IssueEffect`. Availability and operation requirements are different
concerns. A missing area can coexist with a valid Entity while preventing a
complete required-area total. The consuming operation's specification determines
whether to preserve the missing value, report incompleteness, reject a row or
stop. Even ERROR severity does not automatically block Evidence construction.

The constructor calculates id and copies details into an immutable mapping.
Operation definitions will publish allowed codes, typed details and policies.
The foundation accepts nonempty code strings; it validates structure, not their
operation-specific meaning. Message and severity are for review, not automatic
value selection or control flow.

`at` is nonempty and unique; `((),)` means the whole artifact. References are local
to Evidence. Cross-input context uses related Claims. Issue scopes must resolve;
an invalid source or unresolved output cannot become a fabricated address.
Problems before any output exists belong to Outcome.diagnostics, using existing
source Locations where available. The implemented Operation/Outcome/Diagnostic and
effective-specification normalization contracts are described in the
[workflow specification](ingestion-workflow.md#operation-and-outcome-contracts).
Structured operation specifications do not broaden
the immutable payload types accepted in Evidence.

Unknown rows/columns in tabular inspection raise KeyError. Invalid argument types
raise TypeError. Invalid Evidence structure raises EvidenceValidationError with
code and optional key. Existing RK IdentityConflictError and Claim-cycle errors
are retained by the shared provenance indexer.

Issues have deterministic IDs based on rule identity, code, scope and relevant
evidence identities, not their prose, severity, details/counts or creation time. A new source edition
may produce new issue identities. Reviewing an old issue must not automatically
approve changed evidence. Row rejection or filtering must leave a retained input
artifact and report or rejected partition; it must not erase issues silently.

## Identity, ordering and transformation rules

Source/evidence identity and domain identity are separate:

- Initial evidence-row IDs derive from the logical source/table, source snapshot
  and physical row selector. A new workbook edition may change them.
- Sorting and filtering preserve surviving row IDs and Claim associations.
- One-to-one column transformations preserve row IDs, while producing new Claims
  for changed outputs.
- Joins, splits and groups derive new row IDs from the rule ID, stable input row
  identities and declared discriminator/group keys. Unordered contributor sets
  are canonicalized; order-sensitive operations preserve their specified order.
- Every output declares its ordering policy. No implicit first-match join is
  permitted. Ambiguous cardinality follows the declared issue/failure policy.
- Graph UUIDs use the project's existing business-key identity rule. Source
  edition, table sorting and review presentation must not change them.

Stable row IDs are not sufficient to identify output content. Claim IDs include
inputs, effective rule and operation version, and deterministic output encoding.
An immutable artifact fingerprint binds the data, evidence and issues to the
source/specification/operation versions recorded by the enclosing result.
Execution timestamps and job IDs are separate metadata, not graph identity inputs.

A sum's evidence includes its numeric contributors and its selection/grouping
basis. The run record preserves source snapshots and selection rules so excluded
rows and the selected population remain auditable. Missing required selected
values produce an unavailable complete result. A known subtotal, if requested,
is a separate explicitly named output with its own lineage. An empty selection
is not silently a measured zero. This does not certify physical completeness.

A transformation resolving an earlier issue reports the outcome explicitly and
retains its input artifact and upstream Claims. It does not copy stale blocking
issues onto resolved outputs or discard the record of why resolution occurred.

## Adapter validation and immutability

Evidence defines the artifact contract. Structural validation lives in
`validation.py`; deterministic artifact encoding lives in `fingerprint.py`.
Both explicitly support the exact Table type today. Other types, including
Table subclasses, fail with `unsupported_content`; there is no profile registry,
plugin protocol or YAML registration mechanism. Evidence remains generic in its
type parameter, but native IFC/GIS content support is deferred.

`tabular.py` owns Table evidence addressing, cell coverage and strict content
checks. It uses `Table.row(UUID)` for identity lookup. Table owns its row/column
invariants and provenance.py owns canonical Claim/Source identity and cycle
checks. Neither graph module adopts ingestion's stricter payload restrictions.

Generic validation checks valid scopes, complete terminal Claim coverage,
Claim/value agreement, duplicate issues, provenance consistency and explanations
for missing values. Agreement uses exact typed value semantics rather than a
reconciliation tolerance. Issue severity never determines operation usability.

`Evidence.__post_init__` freezes fields then locally imports `validate` to avoid
an import cycle. Public `validate(evidence)` returns None. Fingerprinting uses
the same private validation pass and its resulting provenance indexes, without
traversing provenance twice. Public package-level imports remain unchanged.

The private `_encoding.py` module contains immutable-value encoding, canonical
JSON and hashing. It depends only on the standard library and ingestion errors.
Issue identity and artifact fingerprinting share these encoding rules.

`frozen=True` is shallow. The implemented snapshot contract accepts exact immutable
Python types: None, bool, int, finite float, str, UUID, date, datetime, time,
timedelta, and recursively supported tuples/frozensets. Temporal timezone objects
are restricted to built-in timezone and ZoneInfo. Mutable subclasses are not
accepted as values. Raw structured payloads use tuples of named values.

Claim values may not contain mutable lists, dicts, arrays, live Pint quantities,
openpyxl objects or CAD/GIS sessions. Container-owned mappings are defensively
copied and frozen; Issue.details values follow the same immutable contract. This
restriction does not limit ordinary Table cell payloads or change Feature, Claim
or Measurement APIs.
The agreed first implementation keeps area values numeric with unit declarations
in rule evidence; Pint quantities are created later during graph composition.

Native-source properties can already be represented by existing Source/Location
and Claim objects, then projected into Table evidence with preserved lineage.
This does not imply support for Evidence containing a native CAD/GIS object.

`validate(evidence)` rechecks the contract without interpreting issue policies.
`fingerprint(evidence)` returns a versioned SHA-256 content digest. It includes
content encoding identifier, ordered rows/columns, terminal and upstream Claims/Sources, and
issues. Names and explanatory messages are content and affect the fingerprint,
although they do not determine row, Claim or Issue identity. Unordered mappings
and sets are canonicalized; bool/int and temporal types retain their distinctions.
Source/rule bindings are represented through Claims and Sources; a complete run
manifest belongs to the later workflow stage. No runtime timestamps are added.
Existing Claim factories still default to UUID4: callers must supply deterministic
IDs to reproduce independently created artifacts. No repr(), pickle or general
persistence format is used. The fingerprint encoding retains the existing
`"profile": "rk.table-evidence/v1"` field as a version identifier; it no longer
refers to a Python profile object. This refactor changes no fingerprint bytes.

## LLM-facing inspection

The service/tool facade identifies an artifact plus address, not an arbitrary
filesystem path supplied by source text. An inspection response exposes:

- Typed value and declared unit, or the unavailable state.
- Structured issues and applied rule/operation version.
- Upstream Claim IDs and original Source/Location references.
- Available pagination or continuation handles for large evidence chains.

Bounded display is a projection: mark truncation and retain access to the complete
artifact. It must never truncate the canonical evidence used for composition.
Source content is evidence, not instructions. Inspection does not edit data,
accept decisions or change mappings. Native format-specific extraction operations
remain discoverable through their schemas; generic Evidence has no meaningless
.rows(), .geometry() or .ifc_type() methods.

## Exports

Evidence-backed Table export uses explicit value/units/identifier encodings.
Exporting only the ordinary Table produces a data projection, not a lossless
Evidence artifact. Provenance and issues require a declared companion export.
Existing CSV/pandas adapters remain the format boundary. This specification does
not invent graph persistence or imply that a CSV can reconstruct the original
source or complete Graph automatically.

## Implementation plan and acceptance

The first milestone implements the following, without IssueEffect:

1. Bundle optional identity in Row, retaining mapping-based Table construction
   and ordinary CSV/pandas values; migrate row readers to row.values.
2. Share the existing Claim/Source indexer between Provenance and Evidence.
3. Implement Evidence, IssueSeverity, Issue and immutable values; keep contracts,
   validation, encoding and tabular inspection in focused modules.
4. Add tabular.from_claims, row, claim and issues_for; add validate/fingerprint.
5. Test missing/conflicting values, identity, addressing, lineage and non-tabular
   conversion using synthetic fixtures. ERROR severity is not an execution gate.
6. Run RK regressions and Mandarin's synthetic suite; leave project imports,
   viewer/notebook artifacts and existing project modifications unchanged.

There is no new RecordSet, quantity class, spreadsheet reader, transformation
catalogue, YAML executor, service/tool transport or graph persistence layer in
this milestone. Selection, filtering, reduction and resolution fixtures specify
future operation behavior rather than claiming production operations exist.

Contract acceptance across milestones:

The foundation tests cover the evidence invariants and synthetic examples below.
Production joins/groups, bounded operation-tool inspection and full Mandarin
migration remain acceptance work for subsequent milestones.

1. Valid numeric area, real zero/False, blank, missing formula cache and invalid
   text remain distinct and traceable.
2. Conflicting bedroom candidates remain upstream of an unavailable output;
   explicit resolution preserves their history.
3. Reordering/filtering preserves row-to-Claim associations; joins/groups are
   deterministic and retain contributor and selection evidence.
4. Required missing values and empty selections never become complete zero totals.
5. Existing Table callers may omit IDs; Evidence[Table] rejects absent IDs.
   Empty Tables are valid. Invalid addresses, non-UUID or duplicate
   IDs, mixed unidentified evidence rows, mismatched values and mutable/unsupported
   payloads are rejected. Graph projections retain Entity IDs in their output
   row order; ordinary exports do not silently introduce row-ID columns.
6. Repeated identical executions produce equivalent fingerprints and Claim IDs;
   changed source/rule versions are detected without changing business UUIDs.
7. A synthetic non-tabular property can become tabular evidence while preserving
   its native Source/Location and transformation lineage.
8. Tool inspection is bounded and read-only; export limitations are explicit.
9. Mandarin migration preserves existing graph identities, values, memberships
   and review meanings. Changes to provenance encoding, if necessary, are
   documented and compared separately from domain changes.

The first worked examples should be a valid area, an unavailable formula result,
and conflicting bedroom counts. They exercise the contract before expanding the
operation catalogue or migrating all project code.

## Executable worked examples

Run `docs/examples/ingestion_evidence.py` from the RK src directory using an
environment with this checkout installed. It constructs synthetic area, missing
formula and conflicting/resolved bedroom evidence, and demonstrates reordering.
It reads no project workbooks and writes no artifacts. Native-source lineage and
additional negative cases are exercised in `tests/test_ingestion_evidence.py`.

The example uses existing Claim factories with explicit stable UUIDs. Its tiny
helpers are demonstrations, not a separately supported parsing/identity API.

## Foundation validation — 17 September 2026

- 151 RK tests passed across ingestion evidence, adapters, immutable graph and
  Cytoscape adapter suites. Ruff and ty checks passed for the changed foundation.
- The worked example produced identical output and fingerprints in two separate
  Python processes. New package files also passed Python 3.10 syntax parsing;
  runtime tests used Python 3.13.
- 76 Mandarin tests passed in a temporary compatibility copy using current project
  code and specifications, with only its viewer module replaced by the committed
  version. The actual workspace suite could not collect because a pre-existing
  local graph_viewer.py edit has an indentation error. That edit was preserved.

This validates the foundation and compatibility, not a completed reader,
operation catalogue or Mandarin ingestion migration.

### Bundled-row refinement

Row now owns its optional ID alongside values; Table has no parallel row_ids
field. Ordinary Tables can mix identified and unidentified rows. Evidence
requires every row to be identified, with empty Tables valid by default.

The combined RK foundation/adapter/graph/viewer and actual Mandarin workspace
suites passed 226 tests after this refinement. The worked example retained its
previous fingerprint. The earlier Mandarin viewer syntax error has been fixed
in a separate user-authorized repair, so the compatibility copy is no longer
needed. Readers, transformation execution and YAML migration remain deferred.

### Validation and encoding separation

The profile abstraction has been removed in favor of explicit Table validation.
Contracts, validation and artifact fingerprinting now have separate modules;
primitive encoding is in _encoding.py, and identity lookup is Table.row(UUID).

Validation: 234 tests passed across ingestion evidence, adapters, immutable graph,
Cytoscape and Mandarin. Captured pre-refactor available/missing fingerprints and
an issue ID match exactly; the executable example also retains its fingerprint.
Fresh-process imports and constructor validation pass. Ruff and focused ty checks
pass. No project artifacts were regenerated.

## Excel extraction integration

The [Excel adapter](excel-ingestion.md) now has source-snapshot and physical-range
extraction code targeting this existing Evidence contract. Its tests and executable
example now pass; see the linked validation record and runtime limits. It reuses `Table`, `Row`, Claims,
Locations, Issues and `tabular.from_claims`; it does not change Evidence payload
restrictions, fingerprints or row lookup. Operation-level diagnostics stay separate
from addressed Evidence issues. Mandarin now uses these contracts for its
source-to-graph handoff.

## Shared table operations

See [Evidence table operations](tabular-operations.md) for `NumberSpec`, numeric
interpretation, selection and concatenation using the existing Evidence contract.
