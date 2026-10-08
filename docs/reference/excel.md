# Excel snapshots, inspection and extraction

`rangekeeper.adapters.excel` reads local `.xlsx` editions into immutable snapshots,
then extracts declared physical ranges into [Evidence](evidence.md). It does not
recalculate formulas, infer units or decide which rows represent business objects.
The [source workflow](workflow.md) can compose these operations into a complete
Model build; the same APIs also work directly.

## Public API and boundaries

The adapter owns `Workbook`, `Worksheet`, `Cell`, `WorksheetInspection`, typed
extraction requests, `read`, `extract_table`, `classify_rows` and
`load_specification`. `adapters.document` owns recorded description, navigation,
inspection and search. `workflow.operation` owns their invocation records and
Outcomes. Source/Location/Claim/Method objects belong to transient workflow
Evidence; composition converts them to canonical Model provenance.

Importing the direct Excel API does not import openpyxl or PyYAML. Install the
`excel` extra to read workbooks and decode extraction YAML. Pin the actual project
environment for reproducible execution.

```python
from uuid import UUID
from rangekeeper.adapters import document, excel

outcome = excel.read(
    path,
    namespace=UUID("f7d7363f-b1c0-4e28-93dc-59c6f7eedc4d"),
    source_key="pricing",
    name="Pricing schedule",
    expected_checksum=expected_sha256,
)
if outcome.output is not None:
    workbook = outcome.output
    specification = excel.load_specification(yaml_text)
    extracted = excel.extract_table(workbook, specification)
```

Each read/describe/children/inspect/search/extract operation returns an Outcome.
Invalid arguments or requests raise exceptions. Expected source/capability
mismatches return no output with Diagnostics. An empty Table or search page can
be successful. Severity does not control availability. See the
[operation contract](workflow.md#operations-outcomes-and-diagnostics) for effective
settings, immutable parameters and type-sensitive fingerprints.

## Read one immutable edition

`read(path, *, namespace, source_key, name, expected_checksum=None)` captures local
bytes once. XML, formula and cached-value parsing all use those bytes. The optional
checksum accepts SHA-256 hexadecimal with or without `sha256:`;
`Source.checksum` stores lowercase hexadecimal. Path and acquisition time do not
determine source identity. The read operation records the installed openpyxl version.

The Source UUID derives from namespace, logical source key and byte checksum.
Changed bytes create a different source edition. `name` is descriptive metadata;
it affects the snapshot fingerprint, not the edition UUID. Use one canonical name
for a source within a build.

A Workbook contains native worksheets and metadata, not domain Entities. It retains
source dates and Excel epoch as observations, without substituting filesystem times.
Each Worksheet retains dimensions, state, merged ranges and cells ordered by
physical row/column.

A Cell retains its Location, raw value, formula, cached value, `cache_present`,
native types, number format, XML value/type/formula, formula attributes and merged
anchor. `cell.value` selects the cache for formulas and raw data otherwise. Native
number formats can yield Python date/time observations; the numeric serial remains
available as `xml_value`.

- Empty numeric formula `<v/>` means no cached value.
- A string cache `<v/>` with `t="str"` is an explicit empty string.
- Literal empty strings differ from physical blanks.
- An uncached formula is still physically populated.
- Reading does not recalculate formulas, copy merged anchors into covered cells,
  load external links or modify the source.

Snapshots contain no mutable parser objects. Parser resources are closed in one
resource scope. Only decode-boundary errors become invalid-workbook Diagnostics;
unexpected errors in snapshot construction propagate.

`workbook.sheet(name)` raises `KeyError` for a missing sheet.
`worksheet.cell("Z99")` returns a blank observation for an absent but valid
coordinate. Invalid syntax raises an API error. Snapshot fingerprints bind complete
observations and the read operation; they are calculated at construction and are
not a required intermediate persistence file.

## Bounded inspection

```python
document.describe(workbook)
document.children(workbook, location=None, limit=50, cursor=None)
document.inspect(workbook, location)
document.search(workbook, "04.01", limit=50, cursor=None, case_sensitive=True)
```

Description supplies Source, format, supported capabilities and immutable metadata.
Root children are worksheets in workbook order; worksheet children are populated
cells in physical order. Cell children are empty. Styled blanks remain available
in the snapshot but are not populated navigation entries.

Locations use `{}`, `{"sheet": "Pricing"}` or
`{"sheet": "Pricing", "cell": "A8"}`. They must be canonical and bound to this
Source edition. Returned Locations use its canonical Source instance. Native
navigation does not imply Model membership.

`Page` supplies `items` and `next_cursor`. Limits are 1–500, default 50. Cursors bind
to snapshot, operation and location/search query; page size may change. Malformed
cursors raise `ValueError`; a different snapshot/query produces a Diagnostic.
Cursors are navigation state, not build inputs.

`Inspection` supplies location, kind, typed content and `truncated`.
Worksheet previews include at most 50 merged ranges and their total count. Cell
text previews are bounded at 2,000 characters, including ellipsis. Full observations
remain available for extraction. Search is literal and case-sensitive by default,
over stored strings including cached strings. It does not search formula expressions
or numeric display formatting. A no-match search returns an empty successful page.

Source text is data, not evaluated code or trusted HTML. UI consumers must escape
it. Common Document functions record Outcomes once and report unsupported
capabilities explicitly. Other native Document backends are not implemented by
this Excel contract. The [CSV adapter](tables.md#csv) exchanges detached Tables;
it is not a source-bound Document reader.

## Extraction specification

Python uses `ExtractionSpec`, `Rows`, `StopBefore`, `Expectations` and ordered
`Column` objects, or `ExtractionSpec.from_mapping`. YAML uses the same schema.
See the [maintained example](../../examples/ingestion/excel_ingestion.yaml).

| Field | Contract |
| --- | --- |
| `id` | Nonempty logical extraction name used for Evidence naming and row identity. |
| `version` | Integer, exactly `1`. |
| `sheet` | Exact worksheet name. |
| `expect` | Optional cells mapping and `comparison`, default `exact`. |
| `rows.start` | Inclusive physical Excel row. |
| `rows.end` | Inclusive physical ending row; mutually exclusive with `stop_before`. |
| `rows.stop_before` | Required `column` and `equals`; comparison defaults to `exact`. Excludes the first match at/after start, within worksheet dimensions. |
| `columns` | Nonempty ordered sequence of `{name, column}`. Output names are unique; source columns may repeat. |
| `formula_values` | `cached` is the only value and the resolved default. |

Columns and coordinates must be uppercase and within Excel bounds. Unknown fields,
duplicate output names, contradictory bounds and unsupported versions raise errors.
The YAML loader rejects duplicate keys, executable tags, merge keys, cycles and
unsupported payloads. Ordinary scalar resolution precedes schema validation;
numeric strings are not coerced.

`exact` compares typed values. `trim` additionally strips surrounding string
whitespace for comparison without changing Evidence. Error cells and unavailable
formula caches cannot satisfy layout/stop guards. A missing required marker or
failed guard produces no extraction. A stop marker in the start row gives a
successful empty Table. Fixed bounds can include absent physical cells; extraction
records them explicitly as blanks.

`extract_table(workbook, specification, *, unique_stop=False)` optionally requires
a unique stopping marker. `unique_stop=True` requires a `stop_before` policy and
checks the complete physical column, including rows before extraction starts.
Anything other than one match produces `nonunique_stopping_marker`; the matching
row must still satisfy the extraction start rule. This option is separate from
the version-1 extraction document and is recorded in the versioned invocation.

All rows in the declared range enter Evidence, including physical blanks. Extraction
does not filter rows, classify records, parse numbers or assign units.

## Claims, Issues and identities

Ordinary cells use sourced Claims. Formula values, errors and covered merged cells
use sourced immutable native observations followed by a versioned derived Claim
for the usable value. Cache selection does not establish formula correctness or
freshness. Repeated mappings of one source cell share a canonical Claim.

| Cell condition | Terminal value | Issue code |
| --- | --- | --- |
| Ordinary value, including empty string, zero or dash text | Preserved scalar | None |
| Blank | `None` | `blank_cell` |
| Excel error, including cached error | `None` | `excel_error` |
| Formula without cache | `None` | `missing_formula_cache` |
| Merged cell covered by an anchor | `None` | `merged_cell_covered` |

Issues address `("rows", str(row_uuid), output_column)` and retain the terminal
Claim. They are not copied into invocation Diagnostics. Row UUIDs bind source
edition, extraction ID, worksheet and physical row. Column reordering preserves
those IDs; they are not business identities. Claim UUIDs bind operation fingerprint,
source address and native observation. Changed extraction semantics can therefore
change Claim identities.

## Physical row classification and health

`RowClassificationSpec` declares `identifier`, full-match `pattern`, optional
`output="row_group"` and optional observation `columns`. `classify_rows(evidence,
workbook, *, specification, settings=None, name=None)` adds derived `blank`,
`matched` or `other` labels. A physically present uncached formula does not become
a blank row. The original extracted Claims, row IDs and Issues remain.

Each selected observation must resolve to exactly one cell in this Workbook,
and those cells must share one physical row. Missing columns, an existing output
column, ambiguous native cells or inconsistent rows make the operation unavailable.
The optional settings Claim joins derivation lineage. Classification does not
itself discard rows; use [explicit selection](evidence.md#selection-and-concatenation).

`adapters.excel.inspection.health(workbook)` returns native observations of missing
formula caches and stored errors, including cached errors. It uses the snapshot
without reopening or recalculating the workbook and has no workflow-result dependency.
The workflow integration exposes these as declared native source checks.

## Diagnostic codes

Expected failures use stable codes and real source Locations when available.

| Code | Details |
| --- | --- |
| `source_unavailable` | `source_key`, requested `path`, OS `errno`; no Location. |
| `unsupported_format` | Requested `suffix`; no Location. |
| `checksum_mismatch` | `expected`, `actual`; actual captured source root. |
| `dependency_unavailable` | `dependency`; captured source root. |
| `invalid_workbook` | `reason`, `error_type`; captured source root. |
| `unsupported_workbook` | `sheet`, `relationship_type`; unsupported non-worksheet content. |
| `unsupported_formula` | `formula_attributes`; affected cell. |
| `missing_sheet` | `requested_sheet`, `available_sheets`; workbook root. |
| `layout_mismatch` | `expected`, `actual`, `comparison`; guard cell. |
| `missing_stop_marker` | `start`, normalized `stop_before`; worksheet. |
| `nonunique_stopping_marker` | No required details; the declared column did not contain exactly one marker. |
| `invalid_location` | No required details; relevant Location and explanatory message. |
| `source_mismatch` | Serialized `requested` Location; current document root. |
| `cursor_mismatch` | No required details; incompatible cursor. |
| `unsupported_capability` | `capability`, `format`; document root. |
| `missing_column`, `output_collision` | Row-classification request cannot be applied; message identifies the incompatibility. |
| `ambiguous_native_cell`, `inconsistent_native_row` | Classification cannot establish one native cell per observation or one common physical row. |

Messages and operating-system/parser prose explain failures; they are not stable
machine identifiers. Unexpected defects are not converted to empty successes.

## Examples and verification

The [executable companion](../../examples/ingestion/excel_ingestion.py) creates a
synthetic workbook by default, inspects it and applies the adjacent extraction YAML.
An optional real workbook needs an explicit checksum and is only read. From `src`:

```sh
python ../examples/ingestion/excel_ingestion.py
pytest tests/test_document_operations.py tests/test_excel_ingestion.py tests/test_ingestion_evidence.py
```

Tests cover native formula/cache states, immutability, source mismatch, strict YAML,
inspection and optional-import isolation. Run current acceptance commands from
[verification](../contributing/verification.md). Earlier first-slice results remain
[dated history](../history/source-workflows/2026-09-17-foundations.md), not a claim
about current or external environments.
