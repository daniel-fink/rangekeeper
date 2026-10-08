# Tables and detached projections

`rangekeeper.shared.table` owns `Row`, `Table` and `TableError`. Tables provide
ordered, domain-independent data for inspection and interchange. They are not
Model persistence or a general dataframe API. Use [Evidence](evidence.md) when
cells must retain source support, and [canonical codecs](run-and-storage.md) to
save or reload a Model.

## Row and Table

```python
from rangekeeper.shared.table import Row, Table

table = Table(columns=("name", "area"), rows=({"name": "Room A", "area": 0},))
assert table.rows[0].values["area"] == 0
assert table.column("name") == ("Room A",)
```

`Row(values, id=None)` copies the cell mapping and exposes it as read-only.
`Table(columns, rows)` accepts Rows or mappings. Mappings become unidentified
Rows. Column names must be unique, nonempty strings, and every row must contain
exactly those columns. Invalid shape or duplicate identities raise `TableError`;
invalid argument types raise `TypeError`.

Supplied row IDs must be UUIDs and unique. Ordinary Tables can mix identified and
unidentified rows. A Table never invents IDs or derives them from current positions.
`Table.row(uuid)` returns the stored identified Row; it raises `TypeError` for a
non-UUID and `KeyError` for an absent UUID. `Table.column(name)` preserves row order
and raises `KeyError` for an unknown column. Identity is metadata, never an implicit
column.

Construction reuses a supplied Row when its columns already match in order.
Otherwise it creates a Row in the Table's column order without changing the input.
The outer containers are frozen, but cell values are unconstrained and only
shallowly frozen. A Table can hold native or mutable cells; an `Evidence[Table]`
applies a stricter immutable-value contract.

## Project a Model selection

Use `rangekeeper.model.system.projection.to_table` with a pinned `View` or
`Hierarchy`. See [system views](system.md) for selection and hierarchy rules.

```python
from rangekeeper.model.system import View
from rangekeeper.model.system.projection import (
    EntityField, FieldColumn, PropertyColumn, ValueColumn, to_table,
)

columns = (
    FieldColumn("model_id", EntityField.MODEL_ID),
    FieldColumn("entity_id", EntityField.ENTITY_ID),
    FieldColumn("name", EntityField.NAME),
    ValueColumn("net_area", "net", "meter**2"),
    PropertyColumn("notes", "notes"),
)
table = to_table(View(model), columns=columns)
```

| Column | Meaning |
| --- | --- |
| `FieldColumn(name, field)` | Requires an `EntityField` member: `MODEL_ID`, `ENTITY_ID`, `CODE`, `NAME`, `ENTITY_KIND`, `CLASSIFICATION_ID`, `CLASSIFICATION_CODE` or `CLASSIFICATION_NAME`. Raw strings are rejected. |
| `ValueColumn(name, key, units, measure=None)` | Selects one owner-local Value key and converts its quantity to explicit units. Optional `measure` asserts a Measure UUID; it does not select a Value by Measure. |
| `LabelColumn(name, key)` | Returns classification UUIDs for a local Label. It does not substitute potentially ambiguous codes. |
| `PropertyColumn(name, key)` | Returns detached decoded property content. A non-property Value raises `TableError`. Missing and explicit null return `None`; `False` and zero retain their types. |

`to_table(source, *, columns=DEFAULT_COLUMNS, units=default_units)` returns a
Table. Defaults are Model UUID, Entity UUID and name. Row IDs are Entity UUIDs;
View order determines row order. Include `model_id` when rows leave the pinned
View context. Missing or unresolved quantities project to `None`; a known zero
remains zero. Inspect the Model when absence must be distinguished from a declared
Value without a quantity.

Duplicate column names raise `TableError`. Wrong source, column or field types
raise `TypeError`. Incompatible units raise `UnitError`; a Measure mismatch raises
`SelectionError`. Requested units are validated even for empty selections.

A Hierarchy projection uses preorder and appends reserved `parent_id`. Choose
relationship or membership semantics before projection; shared membership is not
silently assigned to one parent. Model projections contain no source Claim map
and cannot be read back as Models.

## Polars

`rangekeeper.adapters.polars.to_frame(Table | Flow | Stream)` returns detached columns.
For Tables, row IDs and Claims remain separate metadata. Homogeneous supported
scalars use native Polars columns; opaque or mixed cells use Object columns to
avoid silent coercion. `to_table(frame)` copies frame cells into unidentified Rows.

For Flows, `to_frame` includes movement identity, coordinates, periods, Claim
references and `_present` field-presence metadata. `from_frame(frame, *, units)`
requires that explicit movement format and an explicit unit string. It validates
the resulting Flow; NaN is invalid, not an alias for missing. See
[calculations](calculations.md) for movement and missing-value rules.

`polars.dates(flow, *, name="magnitude", timing=None)` is a display projection.
A Period-only coordinate requires an explicit timing convention. A recorded payment
date takes precedence, including when the Movement also has a Period. This projection omits
movement IDs, matching keys, coverage and Claims; use `to_frame` for interchange.

## CSV

`rangekeeper.adapters.csv.write(table, path)` writes a textual projection and
creates parent directories. UUID cells become text. Unsupported rich cells and
nonfinite numbers raise `EncodingError`; values are encoded before dataframe
construction to avoid rounding large integers through inferred numeric columns.

`csv.read(path, *, schema_overrides=None)` uses Polars inference. Empty fields
become `None`, while `NA` remains text. Preserve leading-zero identifiers with an
explicit string override:

```python
import polars as pl
from rangekeeper.adapters import csv

table = csv.read("areas.csv", schema_overrides={"code": pl.String})
```

CSV and ordinary dataframe round trips do not restore Row UUIDs, Claims or a Model.
Export the required evidence separately under an explicit format contract.

## Flow and Stream display

`flow.display(name="Rent")` presents one Flow with the same renderer used by
Stream. The name defaults to `Flow` and changes only the display label. Both Flow
and Stream support notebook rich display. Rendering requires the `calculations`
extra; constructing a display object does not import Polars or IPython.

`Stream({"Rent": rent, "Expenses": expenses}).display()` returns a plain-text and
HTML table. Notebook rich display uses the same projection. Labels and units are
shown by default; UUIDs are not. `transpose=True` puts line items on rows.
`precision=2` changes formatting only. HTML labels are escaped. `—` means an absent
coordinate, `?` means an unknown amount, and a known zero is shown as `0.00`.

Display uses the Stream's alignment policy and does not resample or invent payment
dates. Period labels describe coverage. Coordinate conflicts identify the lines
that need explicit alignment or resampling. Use `join=AlignmentJoin.UNION` on the
Stream to display gaps across compatible coordinates.

`stream.to_frame()` and `polars.to_frame(stream)` return detached numeric line
columns with `date`, `period_start`, `period_end` and `key` coordinates. Those four
names are reserved in this projection. Line labels are the numeric column names;
units remain on the Stream. Absence and unknown amounts both project to null in
this numeric export; the display and source metadata distinguish them. This is
not the lossless Flow interchange format described above.
