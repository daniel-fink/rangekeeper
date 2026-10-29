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


def _flow(magnitudes):
    from datetime import date, timedelta
    from uuid import uuid4

    from rangekeeper.flow import Flow, Movement

    start = date(2026, 1, 1)
    return Flow(
        units="m",
        movements=tuple(
            Movement(id=uuid4(), date=start + timedelta(days=i), magnitude=magnitude)
            for i, magnitude in enumerate(magnitudes)
        ),
    )


@pytest.mark.parametrize(
    "magnitudes, dtype",
    [
        ((1, 2, 3), pl.Int64),
        ((1.5, 2.0, None), pl.Float64),
        ((1, 2.0, None, 3.5), pl.Object),
        ((10**40, 1), pl.Object),
        ((), pl.Float64),
    ],
    ids=["integers", "floats", "mixed", "large", "empty"],
)
def test_polars_flow_round_trip_keeps_number_types(magnitudes, dtype):
    from rangekeeper.schema.validation import slots_for

    flow = _flow(magnitudes)
    frame = polars.to_frame(flow)
    assert frame.schema["magnitude"] == dtype
    assert set(frame.columns) == {*slots_for("Movement"), "_present"}
    assert frame.columns[0] == "id" and frame.columns[-1] == "_present"
    restored = polars.from_frame(frame, units=flow.units)
    assert [type(m.magnitude) for m in restored.movements] == [
        type(m) for m in magnitudes
    ]
    assert restored.to_data() == flow.to_data()


def test_polars_flow_columns_use_slot_types():
    frame = polars.to_frame(_flow(()))
    assert frame.schema == pl.Schema(
        {
            "id": pl.String,
            "key": pl.String,
            "date": pl.String,
            "period": pl.Null,
            "magnitude": pl.Float64,
            "claims": pl.List(pl.String),
            "_present": pl.List(pl.String),
        }
    )


def test_polars_to_frame_takes_a_flow_a_stream_or_a_table():
    from rangekeeper.flow import Stream

    stream = Stream(flows={"area": _flow((1, 2))})
    assert polars.to_frame(stream).equals(stream.to_frame())
    with pytest.raises(TypeError, match="Flow, a Stream or a Table"):
        polars.to_frame([1, 2])


def test_polars_dates_needs_another_magnitude_name():
    from rangekeeper.errors import Code, ContractError

    with pytest.raises(ContractError) as raised:
        polars.dates(_flow((1,)), name="date")
    assert raised.value.code is Code.CONTRACT
