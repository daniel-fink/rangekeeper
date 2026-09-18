# Excel source ingestion

Status: first Excel slice validated on 17 September 2026. The synthetic and
checksum-bound local JLL examples, relevant RK/Mandarin regressions and focused
code checks passed. No Mandarin source reader has been replaced and no project
artifacts have been regenerated. See the validation record below for limits.

This slice implements source snapshots, inspection and physical extraction from
`.xlsx`. It does not yet execute the complete interpretation/composition YAML
workflow described in [the workflow contract](ingestion-workflow.md).

## Ownership and public API

`graph.adapter.operation` owns `Operation`, `Outcome[T]`, `Diagnostic` and
`fingerprint(operation)`. `Method`, `Source` and `Location` remain graph-owned.
`IssueSeverity` is reused from ingestion. `Issue` and `Evidence` retain their
existing contracts and fingerprint format.

`graph.adapter.document` owns the `Document` interface and recorded inspection
functions. `graph.adapter.excel` owns immutable `Workbook`, `Worksheet`, `Cell`,
`WorksheetInspection`, typed extraction requests, `read`, `extract_table` and
`load_specification`. Dependencies are lazy: importing these APIs does not import
openpyxl or PyYAML. Install the `excel` extra to use the reader and YAML decoder.
The project must pin the full environment for reproducible execution; dependency
ranges in RK are compatibility declarations, not a project lockfile.

```python
from uuid import UUID
from rangekeeper.graph.adapter import document, excel

outcome = excel.read(
    path,
    namespace=UUID("f7d7363f-b1c0-4e28-93dc-59c6f7eedc4d"),
    source_key="jll",
    name="JLL pricing",
    expected_checksum=expected_sha256,
)
if outcome.output is not None:
    workbook = outcome.output
    specification = excel.load_specification(yaml_text)
    extracted = excel.extract_table(workbook, specification)
```

Every read/describe/children/inspect/search/extract call returns an Outcome.
Invalid typed arguments/specifications raise exceptions. Anticipated source or
capability mismatches return `output=None` with diagnostics. Severity does not
control execution. An empty extracted Table is successful output.

Operations contain the effective specification (including defaults), versioned
Method and named input fingerprints. A source that could not be acquired has a
`None` input fingerprint; no fictitious Source is created. Structured parameters
are deeply frozen. Mapping order is irrelevant to fingerprints; sequence order
and scalar types matter. In particular `1`, `1.0`, `True` and `"1"` differ.

## Class boundaries and reuse

| Existing contract | Adapter responsibility |
| --- | --- |
| `Source` and `Location` | `Document`/`Workbook` provide read-only content access; they reference Source instead of redefining it. |
| `Claim`, `Method` and provenance indexing | Extraction constructs existing Claims and uses existing lineage/identity validation. `Operation` records the effective invocation of a Method. |
| `Table` and `Row` | These remain extracted data. Excel `Column`, `Rows`, `StopBefore` and `Expectations` are extraction instructions, not replacement table structures. |
| `Evidence` and `Issue` | These describe produced content and addressed issues. `Outcome`/`Diagnostic` describe an invocation, including failure before any content exists. |
| Existing scalar encoder and digest helpers | Structured specification encoding reuses these primitives, adding only mapping/sequence structure; Evidence payload restrictions remain unchanged. |
| `rangekeeper.validate` | Shared text/UUID checks are reused. Format/schema/address checks stay in the adapter. |

Excel coordinate rules live independently in `_coordinates.py`, so native
snapshots do not depend on the extraction request schema. Missing-sheet handling
is shared between inspection and extraction. Generic document functions own
capability checks and recorded invocation behavior. `TEXT_PREVIEW_LIMIT` supplies
the common text-preview bound used by the Excel backend.

The reader separates byte capture, library/XML decoding, native cell conversion
and immutable snapshot construction. Only decoding-boundary errors are converted
to invalid-workbook diagnostics; programming defects during snapshot construction
propagate. A single resource scope closes both parser workbooks.

Mandarin's `sources.py` now projects these snapshots into notebook review views;
its duplicate Excel decoder has been removed. Retained project adapters interpret
JLL, GFA and MGP and pass their Evidence to composition. Project-specific numeric
policies and labels remain outside RK. Shared numeric interpretation, selection
and concatenation use the reviewed [table operations](tabular-operations.md).
The existing CSV adapter remains a simple
Table projection API; it does not yet provide source-bound Document/Evidence
reading. The Cytoscape `document.py` validates display data, not source documents.
Neither API is silently reinterpreted by this addition.

## Reading and immutable native observations

`read(path, *, namespace, source_key, name, expected_checksum=None)` reads local
`.xlsx` bytes once. All XML, formula and cached-value parsing uses those same
bytes. The optional checksum accepts SHA-256 hex with or without `sha256:`;
Source.checksum stores lowercase hex. Path and acquisition time do not contribute
to identities. The reader operation records openpyxl's installed version.

The Source UUID is derived from namespace, logical source key and byte checksum.
Changing a source edition changes its Source UUID. `name` is descriptive Source
metadata; it affects the snapshot fingerprint, not the edition UUID. Use one
canonical name for a source within a build.

A Workbook contains native worksheets and metadata, not domain entities. It
retains source dates and Excel epoch as observed metadata without substituting
filesystem times. A Worksheet contains row/column dimensions, state, merged
ranges and cell observations. Stored cells are ordered by physical row/column.

A Cell retains its Location, raw value, formula expression, cached value,
`cache_present`, native types, number format, raw XML value/type/formula,
formula attributes and merged anchor. `cell.value` selects cached values for
formulas and raw values otherwise; it does not interpret units or classifications.
Excel number formats may produce Python date/time observations; the underlying
numeric serial remains available as `xml_value`.

- Empty numeric formula `<v/>` is a missing cache.
- A string cache `<v/>` with `t="str"` is an explicitly stored empty string.
- Literal empty strings remain different from blanks.
- No formula recalculation, merged-anchor propagation or external-link loading.
- Snapshot mappings and observations are immutable; mutable parser objects never
  leave the reader. All parser resources are closed.
- `workbook.sheet(name)` raises KeyError if missing. `worksheet.cell("Z99")`
  returns a blank observation when the valid coordinate is absent. Invalid
  coordinate syntax raises an API error.

The snapshot fingerprint binds its complete observations and reader operation.
It is computed once at construction. It is an identity encoding, not an additional
persistence format or required intermediate file.

## Inspection

```python
document.describe(workbook)
document.children(workbook, location=None, limit=50, cursor=None)
document.inspect(workbook, location)
document.search(workbook, "04.01", limit=50, cursor=None, case_sensitive=True)
```

Description contains `source`, `format`, `capabilities` and immutable metadata.
Workbook description/inspection reports worksheet and populated-cell counts.
Root children are worksheets in workbook order. Worksheet children are populated
cells in row/column order; cell children are empty. Styled blank cells remain
available in the snapshot but are not populated navigation entries.

Locations use `{}`, `{"sheet": "Unit Pricing"}` or
`{"sheet": "Unit Pricing", "cell": "A8"}`. References must be canonical and
bound to the same Source edition. Returned Locations use the document's canonical
Source instance. Native navigation does not imply domain containment.

`Page` contains `items` and `next_cursor`. Limits are 1–500, default 50. Cursors
bind to snapshot, operation kind and location/search query; page size may change.
Malformed cursors raise ValueError; another snapshot/query produces a diagnostic.
Cursors are transient navigation state and do not become extraction inputs.

`Inspection` contains location, kind, typed content and a `truncated` flag.
WorksheetInspection previews at most 50 merged ranges and reports their total.
Cell inspection previews text fields at 2,000 characters (including ellipsis).
Full observations remain in the snapshot and extraction. Search is literal,
case-sensitive by default, across stored string values, including cached strings;
formula expressions and numeric display formatting are not searched. Search
labels are previews; inspect/extract through the returned Location for evidence.

Source text is returned as data, never evaluated or rendered as HTML. UI callers
must escape it. This adapter adds no browser renderer.

Future Document backends may use lazy, snapshot-bound access rather than eager
storage. They implement the protected inspection methods and advertise supported
capabilities; common public functions record outcomes once. Unsupported capability
is explicit, not an empty success. Other formats remain unimplemented.

## Extraction specification

See [the executable YAML example](examples/excel_ingestion.yaml). Python callers
construct `ExtractionSpec` with `Rows`, `StopBefore`, `Expectations` and ordered
`Column` objects, or use `ExtractionSpec.from_mapping(mapping)`. YAML and typed
callers converge on the same schema.

| Field | Contract |
| --- | --- |
| `id` | Nonempty logical extraction name, used for evidence naming and row identities. |
| `version` | Integer schema version, currently exactly `1`. |
| `sheet` | Exact worksheet name. |
| `expect` | Optional cells mapping and `comparison`, default `exact`. |
| `rows.start` | Inclusive physical Excel row. |
| `rows.end` | Inclusive physical ending row; mutually exclusive with `stop_before`. |
| `rows.stop_before` | Required `column`, `equals`; comparison defaults to `exact`. First match at/after start, within worksheet dimensions, is excluded. |
| `columns` | Nonempty ordered sequence of `{name, column}`. Output names unique; repeated source columns allowed. |
| `formula_values` | Only `cached`, also the resolved default. |

Columns and cell coordinates must be uppercase, within Excel bounds. Unknown
fields, duplicate output names, contradictory bounds and unsupported versions
raise errors. The YAML loader rejects duplicate keys, arbitrary executable tags,
merge keys, cycles and unsupported payloads. Ordinary YAML scalar resolution
applies before schema validation; the schema does not coerce numeric strings.

`exact` uses typed value equality; `trim` additionally strips surrounding
whitespace on string operands, without changing evidence. Error cells and missing
formula caches cannot satisfy layout/stop guards. A missing required marker or
failed guard produces no extraction, with a diagnostic. A marker in the start row
produces a successful empty Table. Fixed bounds may include absent physical cells;
these become explicitly blank evidence.

No row filtering, classification parsing, numeric coercion or unit assignment is
performed. All physical rows in the range, including blank rows, enter Evidence.

## Claims, issues and identities

Ordinary values use sourced Claims. Formula values, Excel errors and covered
merged cells use a sourced immutable tuple of native observations followed by a
versioned derived Claim selecting the usable value. Formula-cache selection does
not confirm formula correctness or freshness. Claims retain original Locations
and a shared canonical Source; no parallel provenance validator is introduced.

| Cell condition | Terminal value | Evidence Issue code |
| --- | --- | --- |
| Ordinary value, including empty string, zero and dash text | Preserved scalar | None |
| Blank | `None` | `blank_cell` |
| Excel error, including cached error | `None` | `excel_error` |
| Formula with no cache | `None` | `missing_formula_cache` |
| Merged cell covered by another anchor | `None` | `merged_cell_covered` |

Issues address `("rows", str(row_uuid), output_column)` and reference the terminal
Claim. They are not duplicated in Outcome diagnostics. Repeated mappings of one
source cell share a canonical Claim.

Row UUIDs bind source edition, extraction ID, worksheet and physical row. They
survive column reordering but are not apartment/business identities. Claim UUIDs
bind operation fingerprint, source address and native observation. Changes in
extraction semantics therefore change Claim identities. Existing Evidence
fingerprint bytes/format and Issue identity algorithms remain unchanged.

## Diagnostic codes

All expected failures return one error-severity Diagnostic in this slice. Locations
are the real source root or relevant native location when available.

| Code | Detail fields |
| --- | --- |
| `source_unavailable` | `source_key`, requested `path`, OS `errno`; no Location. |
| `unsupported_format` | Requested `suffix`; no Location. |
| `checksum_mismatch` | `expected`, `actual`; Location identifies actual bytes. |
| `dependency_unavailable` | `dependency`; install the optional Excel extra. |
| `invalid_workbook` | `reason`, `error_type`; captured source root. |
| `unsupported_workbook` | `sheet`, `relationship_type`; unsupported non-worksheet content. |
| `unsupported_formula` | `formula_attributes`; affected cell. |
| `missing_sheet` | `requested_sheet`, `available_sheets`; workbook root. |
| `layout_mismatch` | `expected`, `actual`, `comparison`; affected guard cell. |
| `missing_stop_marker` | `start`, normalized `stop_before`; worksheet. |
| `invalid_location` | No required detail fields; inspect message and relevant Location. |
| `source_mismatch` | Serialized `requested` Location; current document root. |
| `cursor_mismatch` | No required detail fields; cursor is incompatible. |
| `unsupported_capability` | `capability`, `format`; document root. |

Messages and OS/parser exception prose are explanatory, not machine identifiers.
Unexpected programming errors are not silently converted to empty results.

## Example and verification

The [executable companion](examples/excel_ingestion.py) creates a synthetic
workbook by default, inspects it and extracts the adjacent YAML. It asserts JLL's
illustrative row values and repeat Evidence/Issue identities. An optional local
JLL workbook requires an explicit checksum and is only read.

Example commands (run from the RK Python project, `src`):

```sh
python docs/examples/excel_ingestion.py
python docs/examples/excel_ingestion.py --workbook /absolute/path/to/jll.xlsx --checksum SHA256
pytest tests/test_document_operations.py tests/test_excel_ingestion.py tests/test_ingestion_evidence.py
```

The new tests include synthetic XML formula caches, source immutability, source
mismatches, strict YAML, non-Excel Document fixtures and optional-import isolation.
Use the project's pinned environment; invoking an unpinned global interpreter is
not a reproducibility guarantee.

## Validation — 17 September 2026

- 211 RK tests passed: the 48 new operation/document/Excel tests plus ingestion
  Evidence, adapters, immutable graph, Cytoscape adapter and shared validation.
- 81 Mandarin tests and 27 Cytoscape JavaScript tests passed. Mandarin source
  parsing and viewer behavior were not migrated or redesigned.
- Ruff lint/format checks passed on the changed Python files. Focused ty checks
  passed for the new adapter code and executable example. Mandarin Ruff checks
  and focused source-reader/viewer type checks also passed.
- The synthetic demo passed, including repeated extraction with identical Evidence
  fingerprints and Issue IDs. Fresh-process identity and optional-import isolation
  tests passed.
- The checksum-bound local JLL demo passed. All previously retained cells matched
  Mandarin's current reader across raw/formula/cache/type/format/XML fields. The
  new snapshot additionally retains explicit unpopulated cell observations. Source
  checksums before and after matched; no project artifact was regenerated.
- The original Evidence example retained its baseline fingerprint:
  `sha256:e2d03a8472a7db27cae45f5c9388bd93d5673106056d444eb22a6d99c33260e9`.
- Runtime: Python 3.13.15, openpyxl 3.1.5, PyYAML 6.0.3, pytest 9.1.1,
  Ruff 0.16.6 and ty 0.0.79. Ten new adapter/example files also passed Python
  3.10 syntax parsing. Python 3.10–3.12 runtime execution was not performed.

Validation corrected typing at the immutable-container and optional-row-ID
boundaries, made the YAML resolver import explicit, aligned import/export ordering,
and updated the existing adapter export-list regression for the three new modules.
No source interpretation or graph model was changed.

This validates the first reader/extraction slice, not full declarative graph
execution. Those first-slice results preceded the later Mandarin migration, which
now uses the existing RK APIs for all three workbooks. See the project
`docs/source-adapters.md` for its separate compatibility checks and ownership review.
Other document adapters remain deferred.
