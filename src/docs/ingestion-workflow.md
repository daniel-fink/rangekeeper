# Reproducible ingestion workflow

Status: target architecture agreed 17 September 2026. The Evidence foundation is
implemented. Shared operation/document contracts and the first Excel reader and
extraction slice have passed focused validation, including synthetic and local
JLL examples and RK/Mandarin regressions. See [Excel ingestion](excel-ingestion.md)
for the concrete API/schema. Retained Mandarin adapters now apply this boundary
to JLL, GFA and MGP; notebooks and composition consume their Evidence.
Compatibility is checked against a pre-migration snapshot. No new RK API was
introduced by that project migration.

## Reproducibility requirement

Source files, a complete YAML specification, retained project adapter code, and
a pinned RK execution environment must be sufficient to reproduce the graph.
Rebuilding must require no LLM, human intervention, notebook state, conversation
history or previously generated graph artifacts.

The YAML specification is the primary durable record of the interpretation work.
It may comprise several files. Together with the original sources, retained
adapters and pinned software, it must determine the graph. YAML holds settings,
reviewed meanings and expectations; Python supplies executable algorithms.

No additional manually maintained project artifact is required beyond the YAML
and retained adapter code. Notebooks, Markdown guides and conversations may help
author or review these inputs, but cannot contain indispensable instructions
absent from the executable build.
This document describes the software contract; it is not another project build
input.

## Authoring and execution

The workflow has two distinct activities:

1. **Authoring:** a user supplies source files or references to them. An LLM and
   user inspect evidence, propose mappings, discuss ambiguities and update the
   YAML specification and, where needed, project adapter code. Notebooks or a
   future application can host this exchange. Instructions in YAML can guide code
   generation; the resulting Python is reviewed, tested and retained before use.
2. **Execution:** Retained adapters and RK apply the reviewed settings using
   versioned, deterministic operations, producing a graph with evidence and check
   results. Execution neither regenerates Python nor asks an LLM to reinterpret
   the sources.

A substantive decision must reach the specification before it affects a build.
Its rationale may be prose, but its executable consequence must be represented
by explicit mappings, parameters, selections or policies. Decision prose is not
executable configuration; silence in a review is not acceptance.

Unresolved choices must have explicit behavior: preserve unavailable evidence,
create an authorized provisional representation, defer the affected scope, or
report that the requested output cannot be produced. Execution must not silently
resolve them or prompt for a decision during a reproducible build.

## Complete build inputs

| Input | Required content |
| --- | --- |
| Sources | Exact source bytes, bound to content checksums and logical source references. A path or URL alone does not identify an edition. |
| YAML specification | Source selection and layouts, extraction and parsing rules, definitions, classifications, business identities, relationships and memberships, reviewed interpretations, unresolved-choice policies, and checks. |
| Retained adapters | Exact project Python and supporting modules, identified by revision/content hashes. Retain the files, not only the hashes. |
| Execution environment | Pinned RK implementation, operation versions and relevant dependency/runtime versions sufficient to reproduce their behavior. |

External facts used by a build must be captured as declared source evidence or
explicit specification values. Mutable services, current working directories,
wall-clock time and unrecorded local settings cannot supply hidden graph inputs.
A changed source edition or incompatible layout must be reported rather than
silently substituted or satisfied from an older generated artifact.

Reusable reading, evidence, provenance and graph operations belong in RK. Project
YAML selects settings and reviewed interpretations. Project adapters may implement
source-specific algorithms using these APIs; promote helpers into RK when reuse
is demonstrated. Do not require a universal YAML transformation language or a new
RK operation for every source arrangement. Prefer ordinary Python modules over
code embedded in YAML, and never rely on an unrecorded notebook override.

An LLM may author an adapter from YAML prose, but prose is not a reproducible
substitute for its generated implementation. Validate behaviour against reviewed
source examples and expectations; repeatability alone does not establish correct
interpretation. Changed authoring instructions require review of the retained
implementation before adopting a new build.

## Execution stages and responsibilities

- **Read:** capture a source edition and preserve native observations, including
  workbook formulas, cached values and source locations. Reading does not
  recalculate formulas or modify sources.
- **Inspect:** expose bounded descriptions and samples for authoring and review.
  Inspection does not accept mappings or change evidence.
- **Extract:** select the declared physical worksheet ranges and columns. Preserve
  stored values and distinctions such as blanks, errors and unavailable caches.
  Layout comparison normalization is explicit and does not rewrite raw evidence.
- **Interpret:** perform explicit row selection, parsing, classification,
  resolution and other transformations under the specification. Retain evidence
  for excluded rows and the basis for selection and derivation.
- **Compose and check:** construct the graph with stable business identities,
  provenance and explicit memberships; run the declared reconciliation and
  coverage checks without inventing missing associations.

For the first Excel slice, extraction reads the declared physical range. Selecting
apartment records happens in a subsequent operation; unmatched or blank rows do
not silently disappear during extraction.

Reuse existing RK types and invariants. Detailed content, Claims, issues,
validation and fingerprinting are specified in the
[ingestion evidence contract](ingestion-evidence.md). Each object's own invariants
belong in its owning module; content-to-Claim associations belong in ingestion.

## Operation and outcome contracts

These runtime types are implemented in `adapter.operation`. All collections are
immutable snapshots.

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Operation:
    method: Method
    specification: Mapping[str, object]
    inputs: Mapping[str, str | None]

@dataclass(frozen=True, slots=True, kw_only=True)
class Diagnostic:
    code: str
    severity: IssueSeverity
    message: str
    locations: tuple[Location, ...] = ()
    details: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True, slots=True, kw_only=True)
class Outcome(Generic[T]):
    operation: Operation
    output: T | None
    diagnostics: tuple[Diagnostic, ...] = ()
```

Method identifies the algorithm and version. Operation is its immutable invocation
description, not an executable algorithm class. Its inputs bind named source or
artifact fingerprints; None denotes an input that could not be obtained.
Specification records the effective parameters, including resolved defaults.

Outcome records a successful or unsuccessful invocation. No output requires at
least one diagnostic; a produced output may coexist with qualifications. An empty
Table is a successful output, distinct from None. Severity is presentational and
does not determine output availability or operation policy.

Diagnostics concern the invocation and can exist before any output exists.
Evidence issues concern valid addresses in a produced artifact. Do not duplicate
cell issues into operation diagnostics simply to announce them again. Reuse one
severity enum, along with existing Source, Location and Method types.

A missing worksheet diagnostic refers to the actual workbook Source through a
root Location; its details record the requested sheet and available alternatives.
If no source snapshot exists, locations may be empty. Record the requested logical
source in the operation/diagnostic details; never invent a Source checksum.
Operation codes and their diagnostic detail schemas must be documented. Message
text is for people, not a control-flow interface. Diagnostics have stable codes and documented detail schemas; this first slice
does not assign persistent diagnostic IDs. Invocation fingerprints supply operation
context rather than deriving identity from prose alone.

Expected source/request mismatches produce diagnostics: missing files or sheets,
changed layout guards, absent required stopping markers, unsupported inspection
capabilities and locations belonging to another snapshot. Invalid API argument
types or specifications and unexpected programming defects raise exceptions.
A search with no matches produces a successful empty page, not a failure.

### Effective specification normalization

Validation, normalization and execution are separate responsibilities:

1. The operation-specific schema rejects invalid/unknown parameters and resolves
   defaults. A YAML loader rejects duplicate keys and arbitrary executable tags.
2. A shared normalizer recursively copies and freezes the effective request.
3. The operation attempts execution against its declared input snapshots.

| Supplied value | Normalized representation |
| --- | --- |
| Mapping | Read-only mapping with string keys and recursively normalized values |
| List or tuple | Tuple in the supplied order |
| Supported immutable scalar | Same type and value |
| Unsupported object, callable or non-finite number | Rejected without stringification |

Normalization must not infer project interpretation, coerce numeric strings,
trim source values or introduce hidden defaults. Such transformations require an
explicit operation/schema rule. Changes to caller-owned nested collections after
construction must not alter the Operation or Diagnostic.

Fingerprint the effective specification using deterministic type-sensitive
encoding. Mapping insertion order, YAML comments and formatting do not matter;
sequence order does. Integer 1, float 1.0, string "1" and boolean true remain
distinct. Bind the operation fingerprint to Method code/version, effective
specification and named input fingerprints. Do not include execution timestamps
or job IDs. This identifies a reproducible invocation, not a unique execution.

Keep structured-specification encoding separate from strict Evidence payload
encoding. Reuse the existing immutable scalar rules without permitting arbitrary
mapping payloads in Claims or weakening Evidence validation.

Ordering that affects output must be explicit in the effective specification.
For example, extraction columns are an ordered sequence:

```yaml
columns:
  - name: unit
    column: A
  - name: area
    column: J
```

This refines the earlier illustrative column mapping: output column order must
not depend on mapping insertion order that fingerprinting intentionally ignores.
Mandarin's current column mappings are unchanged until the migration explicitly
converts them to the new schema while preserving their declared output order.

## Documents and format boundaries

Source is the durable identity of an original evidence artifact. Document is the
adapter's read-only access to content bound to a captured edition. Keep them
separate: retaining a Claim must not require loading an entire workbook or model.
Reuse Document.source rather than duplicating Source names/checksums.

Document's common behavior is bounded description, navigation, inspection and
literal text search. Workbook/Worksheet/Cell describe Excel-native structure;
other implementations may describe CSV records, Word/Google Docs elements, PDF
pages and regions, IFC objects/properties, or Google Sheets ranges. Do not force
these formats into worksheet cells or infer graph ownership from navigation.

A Document need not eagerly load every object into memory. It must expose stable,
read-only observations from its snapshot without leaking mutable library sessions.
A frozen wrapper alone is insufficient. Locations identify native content within
that snapshot; they need not remain valid across source editions.

Acquisition belongs to readers/connectors, outside the common inspection
interface. Live Google references must be captured with enough content and
structure for reproducible execution; a URL/revision label alone is insufficient
if the same bytes/content cannot be recovered. Capture becomes source material,
not another manually maintained interpretation artifact. Authentication is not a
semantic graph input. Inspection of a captured source must not silently query
newer live content.

PDF embedded text and OCR-derived text must remain distinguishable. OCR is an
explicit versioned transformation whose evidence references the original page.
Lack of OCR support is a capability diagnostic, not evidence that the page is
empty. Actual PDF, CSV-document, Word, IFC and Google connectors are deferred.

### Common inspection responses

```python
@dataclass(frozen=True)
class ContentItem:
    location: Location
    kind: str
    label: str

@dataclass(frozen=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    next_cursor: str | None

@dataclass(frozen=True)
class Inspection(Generic[T]):
    location: Location
    kind: str
    content: T
    truncated: bool
```

Labels need not be unique; Locations carry addressing. Inspection content has a
documented format-specific type rather than an undocumented universal dictionary.
Paged results and bounded previews disclose incompleteness. Cursors bind to the
snapshot and query; they are navigation state, not graph build inputs. Search is
literal with specified matching and ordering rules, not implicit semantic search.
Description fields and Excel-specific inspection payloads and limits are defined
in [Excel ingestion](excel-ingestion.md).

Every published read/describe/children/inspect/search/extract operation returns
Outcome, carrying the invocation record. Common inspection functions delegate to
Document implementations; record construction is shared rather than independently
implemented in each adapter. Format-specific reads/extractions retain explicit
specifications. Read-only convenience accessors such as Table.row remain ordinary
object methods, not separately recorded workflow operations.

Inspection supports authoring. A value that will affect the graph must enter
through retained extraction/interpretation code with explicit settings and Claims. Preview
text and conversation history cannot become undeclared graph inputs.

### First implementation slice

- Shared Operation/Outcome/Diagnostic contracts and Document inspection responses.
- Excel .xlsx acquisition, immutable source observations and bounded inspection.
- Physical-range extraction with explicit layout guards, stopping behavior,
  ordered columns and cached-formula-value policy; no formula recalculation.
- Claims, issues and diagnostics preserving blank, error and formula-cache states.
- Optional format-specific dependencies, loaded only by the relevant adapter.
- Comparison against JLL/Mandarin observations before replacing project parsing.

Implementation placement is graph.adapter.operation and graph.adapter.document
for shared contracts, graph.adapter.excel for Excel behavior, and the existing
adapter.ingestion package for Evidence. The concrete reader/extraction schema and
snapshot identity encoding are documented in [Excel ingestion](excel-ingestion.md).
This first slice has passed the checks recorded there; it does not implement
project interpretation transforms or complete graph execution from these inputs.

## Generated results and identity

The graph, Evidence artifacts, operation records, diagnostics, manifests and
review exports are generated results. They may be held in memory or persisted for
inspection, but no separately persisted intermediate or report is mandatory for
the next build. A cache may accelerate execution; correctness must not depend on
its presence.

Operation instances bind input snapshots, the effective specification and its
fingerprint, and the existing RK Method/version. These explain execution without
duplicating rule text in every cell Claim. Their shape is defined above; their
versioned export schema remains to be specified.

Source/evidence identities describe source editions and observations. Graph
identities use declared business-key rules. Reordering rows or changing an area
value must not accidentally replace the corresponding apartment Entity.

The same source bytes, effective specification and pinned implementation must
produce equivalent graph content and stable identities, including deterministic
Claims and substantive diagnostics. Compare canonical content rather than Python
object addresses or incidental export formatting. Execution timestamps and job
IDs are separate operational metadata; they must not affect graph identities or
semantic fingerprints.

## Acceptance and migration

The acceptance test is a fresh-environment rebuild with access only to the
specified sources, YAML, retained adapter modules and pinned software. Run it
without an LLM, human input, project notebooks, undeclared code or prior generated
graph artifacts. Repeated
builds must agree on graph content, identities, evidence bindings and substantive
check outcomes. Rebuilding with caches removed must produce the same result.

Include tests for altered source editions and specifications, unavailable values,
explicit unresolved choices, and stale/missing intermediates. Verify that no
fallback introduces an undeclared input. A declared blocking condition must
produce a reproducible failure outcome instead of reusing an older graph.

Mandarin is the proving project. Its JLL and GFA/MGP adapters now feed RK Evidence
into source review, graph composition and reconciliation. The duplicate Excel
decoder was removed; review records are presentation views. A captured baseline
checks source values, graph identities, topology, characteristics and review
meanings, while handoff tests check the intentionally richer Claim lineage.
The reviewed `NumberSpec`, `tabular.numbers`, `tabular.select` and `tabular.concat`
operations now provide reusable table transformations; see
[their API contract](tabular-operations.md). Project interpretation remains local.
Further promotions require explicit user review of the contract, existing
ownership and demonstrated reuse.

A hosted file receiver, storage service and LLM tool transport are future delivery
mechanisms. They must use the same contracts, but are not prerequisites for a
local notebook-assisted authoring workflow and deterministic rebuild.
