"""Independent contracts for graph preparation and composed reduction results."""

from dataclasses import replace
from uuid import uuid4

import pytest

from rangekeeper.model.system import Coverage, Hierarchy, View, reducers
from rangekeeper.model.system.errors import AggregationError
from rangekeeper.model.system.projection import (
    EntityField,
    FieldColumn,
    ValueColumn,
    to_table,
)
from rangekeeper.model.system.reduction import AggregateEntry, Aggregation
from rangekeeper.shared.table import Row, Table, TableError

from .test_model_graph import fixture, reduction


def test_table_retains_normalized_rows_and_rebuilds_only_changed_order():
    values = {"a": 1, "b": 2}
    row = Row(values, uuid4())
    table = Table(("a", "b"), (row,))
    assert table.rows[0] is row and table.row(row.id) is row
    values["a"] = 9
    assert table.row(row.id).values["a"] == 1
    reordered = Table(("b", "a"), (row,))
    assert reordered.rows[0] is not row
    assert tuple(reordered.row(row.id).values) == ("b", "a")
    assert replace(table, rows=()).rows == ()
    with pytest.raises(TableError, match="unique"):
        Table(table.columns, (row, row))


def test_projection_prepares_columns_before_cells_and_uses_hierarchy_order(monkeypatch):
    from rangekeeper.model.system import projection

    model, root, *_ = fixture()
    hierarchy = Hierarchy(View(model))
    column = ValueColumn("net", "net", "meter ** 2")

    def factory_must_not_run(*args, **kwargs):
        pytest.fail("projection constructed a selector for a cell")

    monkeypatch.setattr(projection, "select_value", factory_must_not_run)
    tree = to_table(hierarchy, columns=iter((column,)))
    assert tuple(row.id for row in tree.rows) == hierarchy.preorder()
    assert tree.row(root.id).values["parent_id"] is None
    assert to_table(hierarchy.view, columns=(column,)).columns == ("net",)
    with pytest.raises(TableError, match="reserved"):
        to_table(hierarchy, columns=(FieldColumn("parent_id", EntityField.NAME),))
    with pytest.raises(TypeError, match="EntityField"):
        FieldColumn("name", "name")


def test_aggregate_entries_enforce_structure_without_reducing_again():
    model, root, a, *_ = fixture(missing=True)
    hierarchy = Hierarchy(View(model))
    result = reduction().execute(hierarchy)
    assert result.root_value is None
    assert result.available_value(root.id).magnitude == 10
    calls = []

    def wrapped(values):
        calls.append(values)
        return reducers.sum(values)

    wrapped_result = reduction(reducer=wrapped).execute(hierarchy)
    assert wrapped_result.available_value(root.id).magnitude == 10
    observed = len(calls)
    copied = replace(wrapped_result, entries=dict(wrapped_result.entries))
    assert len(calls) == observed and copied == wrapped_result
    with pytest.raises(AggregationError, match="available"):
        AggregateEntry(None, Coverage((a.id,), (a.id,), ()))
    with pytest.raises(AggregationError, match="exactly"):
        Aggregation(hierarchy, {}, result.value_ids, True)


def test_table_constructs_each_raw_mapping_row_once(monkeypatch):
    calls = []
    initialize = Row.__post_init__

    def counted(row):
        calls.append(row)
        initialize(row)

    monkeypatch.setattr(Row, "__post_init__", counted)
    raw = {"b": 2, "a": 1}
    table = Table(("a", "b"), (raw,))
    assert calls == list(table.rows)
    assert tuple(table.rows[0].values) == ("a", "b")
    raw["a"] = 3
    assert table.column("a") == (1,)


def test_reduction_preserves_callback_interleaving_and_raw_contributor_order():
    from rangekeeper.model.system.selection import select_value

    model, *_ = fixture()
    events = []
    selector = select_value("net")

    def eligible(entity):
        events.append(("eligible", entity.code))
        return entity.code != "root"

    def select(model, entity):
        events.append(("select", entity.code))
        return selector(model, entity)

    def reduce(values):
        events.append(("reduce", tuple(q.magnitude for q in values)))
        return reducers.sum(values)

    View(model).aggregate(
        reduction(select=select, reducer=reduce, contributors=eligible)
    )
    assert events == [
        ("eligible", "a"),
        ("select", "a"),
        ("reduce", (10,)),
        ("eligible", "b"),
        ("select", "b"),
        ("reduce", (20,)),
        ("eligible", "c"),
        ("select", "c"),
        ("reduce", (0,)),
        ("eligible", "root"),
        ("reduce", (10, 20, 0)),
    ]


def test_shared_population_keeps_flat_and_hierarchy_policies_distinct():
    from rangekeeper.workflow._operands import operand

    model, *_ = fixture(amounts=(1e16, 1, -1e16))
    request = {
        "kind": "model_total",
        "value_key": "net",
        "units": "meter ** 2",
        "classification": "room",
    }
    assert operand(request, None, None, model, {}, {}).value == 0
    assert View(model).aggregate(reduction()).root_value.magnitude == 1


def test_projection_preflights_each_measure_once_and_reserved_name_first(monkeypatch):
    from rangekeeper.schema.index import RecordIndex
    from rangekeeper.model import Measure

    model, _, _, _, _, _, measure = fixture()
    columns = (
        ValueColumn("first", "net", "meter ** 2", measure.id),
        ValueColumn("second", "gross", "meter ** 2", measure.id),
    )
    calls = []
    original = RecordIndex.get

    def counted(index, uid, kind=None):
        if kind is Measure:
            calls.append(uid)
        return original(index, uid, kind)

    monkeypatch.setattr(RecordIndex, "get", counted)
    to_table(View(model), columns=columns)
    assert calls == [measure.id, measure.id]
    to_table(View(model, entities=()), columns=columns)
    assert calls == [measure.id] * 4
    with pytest.raises(TableError, match="reserved"):
        to_table(
            Hierarchy(View(model)),
            columns=(
                FieldColumn("parent_id", EntityField.NAME),
                ValueColumn("invalid", "net", "not_a_real_unit"),
            ),
        )


def test_aggregate_mapping_copy_and_subtree_ownership():
    model, root, a, b, *_ = fixture()
    result = reduction().execute(Hierarchy(View(model)))
    entries = dict(result.entries)
    copied = replace(result, entries=entries)
    entries.clear()
    assert copied.root_value == result.root_value
    wrong = dict(result.entries)
    wrong[a.id] = AggregateEntry(
        result.available_value(b.id), Coverage((b.id,), (b.id,), ())
    )
    with pytest.raises(AggregationError, match="subtree"):
        replace(result, entries=wrong)


@pytest.mark.parametrize(
    "reduce", (reducers.sum, reducers.mean, reducers.min, reducers.max)
)
def test_reducers_have_independent_finite_results_and_empty_errors(reduce):
    from rangekeeper.model import Quantity

    values = tuple(Quantity(magnitude=n, units="m") for n in (1, 3, 8))
    expected = {reducers.sum: 12, reducers.mean: 4, reducers.min: 1, reducers.max: 8}
    assert reduce(values) == Quantity(magnitude=float(expected[reduce]), units="m")
    with pytest.raises(AggregationError):
        reduce(())


def test_canonical_classification_lookups_reuse_the_model_index(monkeypatch):
    from rangekeeper.schema.index import RecordIndex
    from rangekeeper.workflow._operands import operand

    model, *_ = fixture()
    view = View(model)

    def rebuilding_is_an_error(*args, **kwargs):
        pytest.fail("canonical Model lookup rebuilt its record index")

    monkeypatch.setattr(RecordIndex, "build", rebuilding_is_an_error)
    assert to_table(
        view, columns=(FieldColumn("kind", EntityField.CLASSIFICATION_CODE),)
    ).column("kind") == ("room", "room", "room", None)
    assert (
        operand(
            {
                "kind": "model_total",
                "value_key": "net",
                "units": "m**2",
                "classification": "room",
            },
            None,
            None,
            model,
            {},
            {},
            view=view,
        ).value
        == 30
    )
