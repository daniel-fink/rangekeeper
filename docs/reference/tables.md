# Tables and detached projections

`rangekeeper.shared.table` owns `Row`, `Table` and `TableError`. `shared` is
internal, and `Row` and `Table` have no public path yet
([#101](https://github.com/daniel-fink/rangekeeper/issues/101)); import
`TableError` from `rangekeeper.errors`. Tables provide
ordered, domain-independent data for inspection and interchange. They are not
Model persistence or a general dataframe API. Preserve source support through
the [canonical provenance records](../../schema/provenance.yaml). Use
[canonical codecs](run-and-storage.md) to save or reload a Model.

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
non-UUID and `MissingReferenceError` for an absent UUID. `Table.column(name)`
preserves row order and raises `MissingReferenceError` with the nearest column
names for an unknown column. `MissingReferenceError` is a `LookupError`, not a
`KeyError`. `Table.head(count=5)` returns a Table of the first rows, with the same
columns and Row IDs; a negative count raises `ContractError`. Identity is
metadata, never an implicit column.

Construction reuses a supplied Row when its columns already match in order.
Otherwise it creates a Row in the Table's column order without changing the input.
The outer containers are frozen, but cell values are unconstrained and only
shallowly frozen. A Table can hold native or mutable cells; an `Evidence[Table]`
applies a stricter immutable-value contract.

## Display

A notebook shows a Table as an HTML table, for example `Specification.roles` or
`Outcome.table(...)`. The display does not change the cells, and it needs no
optional dependency:

- The header has one column for each Table column. When each cell of a column
  that has a value is a Quantity in the same units, the header gives the units,
  as `cost [AUD]`, and the cells give the magnitudes. Other Quantities show their
  units in the cell.
- A UUID cell that identifies another row of the Table shows that row's `key`,
  `name` or `code` cell, for example a `parent_id`. Only a label that one row has
  identifies a row. Other UUIDs show their first eight hexadecimal digits.
- An enum shows its text value, or its name. `None` shows as `—`. Numbers have
  digit groups. A float shows six significant digits, or all the digits of its
  integer part.
- The display shows the first 50 rows. A last line gives the number of the other
  rows. Read all the cells from `Table.rows`, or export them with
  [Polars](#polars).

`repr(table)` gives the shape and the column names, for example
`Table(22 rows, 4 columns: key, movement, role, quantity)`. The
[docs site](../contributing/README.md#docs-site) keeps the HTML display of a
lesson output.

## Project a Model selection

Use `rangekeeper.model.system.table.to_table` with a pinned `View` or
`Hierarchy`. See [system views](system.md) for selection and hierarchy rules.

```python
from rangekeeper.model.system import View
from rangekeeper.model.system.table import (
    EntityField,
    FieldColumn,
    PropertyColumn,
    ValueColumn,
    to_table,
)

columns = (
    FieldColumn(name="model_id", field=EntityField.MODEL_ID),
    FieldColumn(name="entity_id", field=EntityField.ENTITY_ID),
    FieldColumn(name="name", field=EntityField.NAME),
    ValueColumn(name="net_area", key="net", units="meter**2"),
    PropertyColumn(name="notes", key="notes"),
)
table = to_table(source=View(model=model), columns=columns)
```

| Column | Meaning |
| --- | --- |
| `FieldColumn(*, name, field)` | Requires an `EntityField` member: `MODEL_ID`, `ENTITY_ID`, `CODE`, `NAME`, `ENTITY_KIND`, `CLASSIFICATION_ID`, `CLASSIFICATION_CODE` or `CLASSIFICATION_NAME`. Raw strings are rejected. |
| `ValueColumn(*, name, key, units, measure=None)` | Selects one owner-local Value key and converts its quantity to explicit units. Optional `measure` asserts a Measure UUID; it does not select a Value by Measure. |
| `LabelColumn(*, name, key)` | Returns classification UUIDs for a local Label. It does not substitute potentially ambiguous codes. |
| `PropertyColumn(*, name, key)` | Returns detached decoded property content. A non-property Value raises `TableError`. Missing and explicit null return `None`; `False` and zero retain their types. |

`to_table(*, source, columns=DEFAULT_COLUMNS, units=None)` returns a
Table. Without `units`, conversion uses `Model.unit_system` of the View's Model. Defaults are Model UUID, Entity UUID and name. Row IDs are Entity UUIDs;
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

Install `rangekeeper[calculations]`. The public names of `rangekeeper.io.polars`
are `to_frame`, `from_frame`, `to_table`, `dates` and `text_frame`.
`rangekeeper.io.polars.to_frame(Table | Flow | Stream)` returns detached columns;
a Stream gives the frame of `Stream.to_frame()`.
For Tables, row IDs and Claims remain separate metadata. Homogeneous supported
scalars use native Polars columns; opaque or mixed cells use Object columns to
avoid silent coercion. `to_table(frame)` copies frame cells into unidentified Rows.

For Flows, `to_frame` has one column for each Movement slot, in schema order,
then `_present` field-presence metadata. The columns and their types come from the
generated slot metadata, not from a list in the code:

| Slot | Polars type |
| --- | --- |
| UUID, string and date (wire text) | `String` |
| UUID collection, such as `claims` | `List(String)` |
| Record, such as `period` | `Struct`; `Null` when no row has a value |
| Number, such as `magnitude` | `Int64` when all values are integers, `Float64` when all are floats, `Object` when they mix or exceed `Int64` |

The round trip is lossless: integer magnitudes stay integers and floats stay floats.
`from_frame(*, frame, units)` requires that explicit movement format and an
explicit unit string. It validates the resulting Flow; NaN is invalid, not an alias
for missing. See [calculations](calculations.md) for movement and missing-value rules.

`polars.dates(*, flow, name="magnitude", timing=None)` is a display projection.
A Period-only coordinate requires an explicit timing convention. A recorded payment
date takes precedence, including when the Movement also has a Period. This projection omits
movement IDs, matching keys, coverage and Claims; use `to_frame` for interchange.
Its magnitudes and the line columns of a Stream frame are `Float64` numerical
projections, so integers become floats. A magnitude column with the name
`date` raises `ContractError`.

## Text and CSV projections

Use `rangekeeper.io.polars.text_frame(table)` before writing CSV. It converts supported
scalar cells to text before Polars can infer a mixed numeric column. This preserves large
integers. Rich cells and non-finite numbers require an explicit encoding and are rejected.

```python
import polars as pl
from rangekeeper.io import polars

polars.text_frame(table).write_csv("areas.csv")
restored = polars.to_table(
    pl.read_csv("areas.csv", schema_overrides={"code": pl.String})
)
```

CSV has no canonical record identity, units or provenance contract. Retain those separately
or use canonical Model IO. Configure input types explicitly when leading zeroes or text
values such as `NA` matter.
