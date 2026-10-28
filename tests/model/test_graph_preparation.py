"""Independent contracts for graph preparation and composed reduction results."""

from dataclasses import replace
from uuid import uuid4

import pytest

from rangekeeper.model.system import Coverage, Hierarchy, View
from rangekeeper.model.system import _reducers as reducers
from rangekeeper.model.system.errors import AggregationError
from rangekeeper.model.system.rollup import RollupEntry, RollupResult
from rangekeeper.model.system.table import (
    EntityField,
    FieldColumn,
    ValueColumn,
    to_table,
)
from rangekeeper.shared.table import Row, Table, TableError

from .test_graph import fixture, reduction


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
    from rangekeeper.model.system import table as projection

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
    copied = replace(result, entries=dict(result.entries))
    assert copied == result
    with pytest.raises(AggregationError, match="available"):
        RollupEntry(None, Coverage((a.id,), (a.id,), ()))
    with pytest.raises(AggregationError, match="exactly"):
        RollupResult(hierarchy, {}, result.value_ids, True)


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


def test_rollup_asks_each_contributor_rule_once_in_postorder():
    model, *_ = fixture()
    events = []

    def eligible(entity):
        events.append(entity.code)
        return entity.code != "root"

    result = View(model).rollup(definition=reduction(contributors=eligible))
    assert events == ["a", "b", "c", "root"]
    assert result.root_value.magnitude == 30


def test_shared_population_keeps_flat_and_hierarchy_policies_distinct():

    model, *_ = fixture(amounts=(1e16, 1, -1e16))
    rooms = tuple(e.id for e in model.system.entities if e.classification)
    population = View(model, entities=rooms).quantities("net", units="meter ** 2")
    # Python 3.12+ sum compensates floating-point error; model a naive fold explicitly.
    from functools import reduce
    from operator import add

    assert reduce(add, (q.magnitude for q in population.quantities), 0.0) == 0
    assert View(model).rollup(definition=reduction()).root_value.magnitude == 1


def test_projection_preflights_each_measure_once_and_reserved_name_first(monkeypatch):
    from rangekeeper.model import Measure
    from rangekeeper.schema.index import RecordIndex

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
    wrong[a.id] = RollupEntry(
        result.available_value(b.id), Coverage((b.id,), (b.id,), ())
    )
    with pytest.raises(AggregationError, match="subtree"):
        replace(result, entries=wrong)


@pytest.mark.parametrize(
    "reduce", (reducers.sum, reducers.mean, reducers.min, reducers.max)
)
def test_reducers_have_independent_finite_results_and_empty_errors(reduce):
    from rangekeeper.quantity import Quantity

    values = tuple(Quantity(magnitude=n, units="m") for n in (1, 3, 8))
    expected = {reducers.sum: 12, reducers.mean: 4, reducers.min: 1, reducers.max: 8}
    assert reduce(values) == Quantity(magnitude=float(expected[reduce]), units="m")
    with pytest.raises(AggregationError):
        reduce(())


def test_canonical_classification_lookups_reuse_the_model_index(monkeypatch):
    from rangekeeper.schema.index import RecordIndex

    model, *_ = fixture()
    view = View(model)

    def rebuilding_is_an_error(*args, **kwargs):
        pytest.fail("canonical Model lookup rebuilt its record index")

    monkeypatch.setattr(RecordIndex, "build", rebuilding_is_an_error)
    assert to_table(
        view, columns=(FieldColumn("kind", EntityField.CLASSIFICATION_CODE),)
    ).column("kind") == ("room", "room", "room", None)
    assert all(
        model.classification(e.classification).code == "room"
        for e in view.entities
        if e.classification
    )
