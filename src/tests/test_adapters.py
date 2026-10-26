from dataclasses import FrozenInstanceError

import numpy as np
import polars as pl
import pytest

from rangekeeper.io import polars
from rangekeeper.shared import table as table_module


def test_table_normalizes_and_freezes_columns_and_rows():
    table = table_module.Table(
        columns=["name", "value"],
        rows=[{"value": 1, "name": "First"}],
    )

    assert table.columns == ("name", "value")
    assert tuple(table.rows[0].values) == table.columns
    assert table.column("value") == (1,)
    assert not hasattr(table, "group_by")
    with pytest.raises(TypeError):
        table.rows[0].values["value"] = 2
    with pytest.raises(FrozenInstanceError):
        table.columns = ("changed",)


@pytest.mark.parametrize(
    ("columns", "rows", "message"),
    (
        (("",), (), "non-empty strings"),
        (("name", "name"), (), "duplicates"),
        (("name",), ({"name": "First", "extra": 1},), "extra"),
        (("name", "value"), ({"name": "First"},), "missing"),
    ),
)
def test_table_rejects_invalid_columns_and_rows(columns, rows, message):
    with pytest.raises(table_module.TableError, match=message):
        table_module.Table(columns=columns, rows=rows)


def test_table_rejects_string_columns_and_non_mapping_rows():
    with pytest.raises(TypeError, match="iterable of strings"):
        table_module.Table(columns="name", rows=())
    with pytest.raises(TypeError, match="must be a mapping"):
        table_module.Table(columns=("name",), rows=("First",))


def test_polars_table_round_trip_preserves_columns_rows_and_runtime_values():
    runtime_value = object()
    table = table_module.Table(
        columns=("entity_id", "value"),
        rows=(
            {"entity_id": "first", "value": runtime_value},
            {"entity_id": "second", "value": None},
        ),
    )

    frame = polars.to_frame(table)
    restored = polars.to_table(frame)

    assert tuple(frame.columns) == table.columns
    assert restored.columns == table.columns
    assert restored.rows[0].values["value"] is runtime_value
    assert restored.rows[1].values["value"] is None


def test_polars_adapter_preserves_empty_columns():
    frame = pl.DataFrame(schema={"name": pl.String, "value": pl.Float64})

    table = polars.to_table(frame)

    assert table.columns == ("name", "value")
    assert table.rows == ()
    assert tuple(polars.to_frame(table).columns) == table.columns


def test_polars_keeps_mixed_and_nested_table_cells():
    table = table_module.Table(
        columns=("mixed", "nested"),
        rows=(
            {"mixed": 1, "nested": ("a", "b")},
            {"mixed": "1", "nested": {"x": 1}},
        ),
    )
    assert polars.to_table(polars.to_frame(table)) == table


def test_table_exports_preserve_large_integers(tmp_path):
    integer = np.int64(2**63 - 1)
    table = table_module.Table(
        columns=("value",), rows=({"value": integer}, {"value": 1.5})
    )
    path = tmp_path / "large.csv"
    polars.text_frame(table).write_csv(path)
    assert path.read_text().splitlines()[1] == str(integer)
    restored = polars.to_table(pl.read_csv(path, schema_overrides={"value": pl.String}))
    assert restored.column("value") == (str(integer), "1.5")
    huge = table_module.Table(columns=("value",), rows=({"value": 10**40},))
    assert polars.to_table(polars.to_frame(huge)) == huge
