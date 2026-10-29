"""Pivot one recorded Value over a rows tree and a Taxonomy's columns."""

from dataclasses import replace
from statistics import fmean
from uuid import uuid4

import pytest

from rangekeeper.model import (
    Assembly,
    Characteristics,
    Classification,
    Definitions,
    Entity,
    Measure,
    Metadata,
    Model,
    System,
    Taxonomy,
    Value,
    ValueKind,
)
from rangekeeper.model.system import (
    Contributor,
    CoverageStatus,
    Hierarchy,
    Pivot,
    PivotColumn,
    QuantityRollup,
    Reducer,
    RollupError,
    View,
    classified,
)
from rangekeeper.quantity import Quantity
from rangekeeper.shared.errors import MissingReferenceError


def taxonomy(code, *pairs):
    """Build a Taxonomy from (code, parent code) pairs in declaration order."""
    made = {}
    for name, parent in pairs:
        made[name] = Classification(
            id=uuid4(),
            code=name,
            name=name,
            parent=None if parent is None else made[parent].id,
        )
    return Taxonomy(
        id=uuid4(), code=code, name=code, classifications=tuple(made.values())
    ), {name: item.id for name, item in made.items()}


UNITS = (
    # code, level, classification, price
    ("u1", "L1", "2B", 100),
    ("u2", "L1", "2B+S", 200),
    ("u3", "L1", "3B", 400),
    ("u4", "L1", "retail", 1000),
    ("u5", "L1", None, 60),
    ("u6", "L2", "2B-C", 300),
    ("u7", "L2", "3B", 500),
    ("u8", "L2", "2B+S", 250),
    ("u9", "L2", "north", 70),
)


def project(*, missing=()):
    units, kinds = taxonomy(
        "units",
        ("unit", None),
        ("apartment", "unit"),
        ("2B", "apartment"),
        ("2B+S", "2B"),
        ("2B-C", "2B"),
        ("3B", "apartment"),
        ("retail", "unit"),
    )
    aspects, sides = taxonomy(
        "aspects", ("aspect", None), ("north", "aspect"), ("south", "aspect")
    )
    kinds.update(sides)
    measure = Measure(id=uuid4(), code="price", name="Price", units="AUD")
    entities = []
    for code, _, kind, price in UNITS:
        quantity = (
            {}
            if code in missing
            else {"quantity": Quantity(magnitude=price, units="AUD")}
        )
        entities.append(
            Entity(
                id=uuid4(),
                code=code,
                name=code,
                classification=None if kind is None else kinds[kind],
                characteristics=Characteristics(
                    values=(
                        Value(
                            id=uuid4(),
                            key="price",
                            kind=ValueKind.MEASUREMENT,
                            measure=measure.id,
                            **quantity,
                        ),
                    )
                ),
            )
        )
    ids = {item.code: item.id for item in entities}
    levels = {
        level: Assembly(
            id=uuid4(),
            code=level,
            name=level,
            entities=tuple(ids[code] for code, at, _, _ in UNITS if at == level),
        )
        for level in ("L1", "L2")
    }
    building = Assembly(
        id=uuid4(),
        code="building",
        name="Building",
        entities=tuple(item.id for item in levels.values()),
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        definitions=Definitions(measures=(measure,), taxonomies=(units, aspects)),
        system=System(
            entities=tuple(entities), assemblies=(building, *levels.values())
        ),
    )
    ids.update({level: item.id for level, item in levels.items()})
    ids["building"] = building.id
    rows = Hierarchy.from_membership(View(model), root=building.id)
    return model, rows, kinds, ids


def price(reducer=Reducer.SUM, **kw):
    return QuantityRollup(
        key="price",
        reducer=reducer,
        units="AUD",
        contributors=Contributor.LEAVES,
        **kw,
    )


def magnitude(pivot, row, column=None):
    value = pivot.value(row=row, column=column)
    return None if value is None else value.number


def records(ids, *codes):
    return tuple(ids[code] for code in codes)


def test_single_column_pivot_is_the_same_as_execute():
    model, rows, kinds, ids = project()
    reduction = price()
    expected = reduction.execute(rows)
    for pivot in (reduction.pivot(rows), reduction.pivot(rows, by=kinds["2B+S"])):
        assert [column.classification for column in pivot.columns] == [None]
        assert pivot.column().result == expected
        for id in rows.preorder():
            assert pivot.cell(row=id) == expected.entries[id]
            assert pivot.value(row=id) == expected.value(id)
    assert magnitude(pivot, ids["building"]) == 2880


def test_columns_include_sub_types_with_subtotals_through_the_tree():
    model, rows, kinds, ids = project()
    pivot = price().pivot(rows, by=kinds["apartment"])
    assert [(c.classification, c.parent, c.depth) for c in pivot.columns] == [
        (None, None, 0),
        (kinds["2B"], None, 1),
        (kinds["3B"], None, 1),
    ]
    assert magnitude(pivot, ids["building"], kinds["2B"]) == 850
    assert magnitude(pivot, ids["L1"], kinds["2B"]) == 300
    assert magnitude(pivot, ids["L2"], kinds["2B"]) == 550
    assert magnitude(pivot, ids["building"], kinds["3B"]) == 900
    assert magnitude(pivot, ids["u2"], kinds["2B"]) == 200
    assert pivot.value(row=ids["u3"], column=kinds["2B"]) is None
    assert (
        pivot.coverage(row=ids["u3"], column=kinds["2B"]).status is CoverageStatus.EMPTY
    )
    assert pivot.children() == pivot.columns[1:]


def test_deeper_columns_name_their_parent_column():
    model, rows, kinds, ids = project()
    pivot = price().pivot(rows, by=kinds["apartment"], depth=2)
    assert [(c.classification, c.parent, c.depth) for c in pivot.columns] == [
        (None, None, 0),
        (kinds["2B"], None, 1),
        (kinds["2B+S"], kinds["2B"], 2),
        (kinds["2B-C"], kinds["2B"], 2),
        (kinds["3B"], None, 1),
    ]
    assert magnitude(pivot, ids["building"], kinds["2B+S"]) == 450
    # Records classified exactly as 2B are in no sub-column of 2B.
    split = pivot.partition(row=ids["building"], column=kinds["2B"])
    assert not split.complete
    assert split.uncovered == records(ids, "u1")
    assert split.overlap == () and split.outside == ()
    assert pivot.partition(
        row=ids["building"], column=kinds["2B+S"]
    ).uncovered == records(ids, "u2", "u8")


def test_exclusive_columns_match_only_their_own_class():
    model, rows, kinds, ids = project()
    pivot = price().pivot(rows, by=kinds["apartment"], depth=2, exclusive=True)
    assert magnitude(pivot, ids["building"], kinds["2B"]) == 100
    split = pivot.partition(row=ids["building"], column=kinds["2B"])
    assert split.uncovered == records(ids, "u1")
    assert split.outside == records(ids, "u2", "u6", "u8")
    assert not split.complete


def test_overlapping_sibling_columns_are_reported():
    model, rows, kinds, ids = project()
    reduction = price()

    def column(kind):
        rule = classified(model=model, classification=kinds[kind])
        leaf = lambda entity: not rows.children(entity.id) and rule(entity)
        aggregation = replace(reduction, contributors=leaf).execute(rows)
        return PivotColumn(
            classification=kinds[kind], parent=None, depth=1, result=aggregation
        )

    pivot = Pivot(
        rows=rows,
        columns=(
            PivotColumn(
                classification=None,
                parent=None,
                depth=0,
                result=reduction.execute(rows),
            ),
            column("2B"),
            column("2B+S"),
        ),
    )
    split = pivot.partition(row=ids["building"])
    assert split.overlap == records(ids, "u2", "u8")
    assert split.uncovered == records(ids, "u3", "u4", "u5", "u7", "u9")
    assert not split.complete


def test_unclassified_records_are_uncovered():
    model, rows, kinds, ids = project()
    pivot = price().pivot(rows, by=kinds["unit"])
    assert [c.classification for c in pivot.columns] == [
        None,
        kinds["apartment"],
        kinds["retail"],
    ]
    split = pivot.partition(row=ids["building"])
    assert split.uncovered == records(ids, "u5", "u9")
    assert not split.complete
    assert pivot.partition(row=ids["L1"]).uncovered == records(ids, "u5")
    # Restricted to the Taxonomy, the columns add up to All.
    scoped = price().pivot(rows, by=kinds["unit"], only=kinds["unit"])
    assert scoped.partition(row=ids["building"]).complete
    assert magnitude(scoped, ids["building"]) == magnitude(
        scoped, ids["building"], kinds["apartment"]
    ) + magnitude(scoped, ids["building"], kinds["retail"])


def test_incomplete_coverage_stays_visible_per_cell():
    model, rows, kinds, ids = project(missing=("u7",))
    pivot = price().pivot(rows, by=kinds["apartment"])
    assert pivot.value(row=ids["building"], column=kinds["3B"]) is None
    assert (
        pivot.available_value(row=ids["building"], column=kinds["3B"]).magnitude == 400
    )
    coverage = pivot.coverage(row=ids["building"], column=kinds["3B"])
    assert coverage.status is CoverageStatus.INCOMPLETE
    assert coverage.missing == records(ids, "u7")
    assert pivot.value(row=ids["building"]) is None
    assert magnitude(pivot, ids["building"], kinds["2B"]) == 850
    assert magnitude(pivot, ids["L1"], kinds["3B"]) == 400
    # Partition compares selected records, so a missing value does not change it.
    assert pivot.partition(
        row=ids["building"], column=kinds["3B"]
    ).uncovered == records(ids, "u3", "u7")


def test_means_use_raw_contributors_in_every_cell():
    model, rows, kinds, ids = project()
    pivot = price(Reducer.MEAN).pivot(rows, by=kinds["apartment"])
    prices = {code: amount for code, _, _, amount in UNITS}
    level_means = [magnitude(pivot, ids[level]) for level in ("L1", "L2")]
    assert magnitude(pivot, ids["building"]) == pytest.approx(fmean(prices.values()))
    assert magnitude(pivot, ids["building"]) != pytest.approx(fmean(level_means))
    assert magnitude(pivot, ids["building"], kinds["2B"]) == pytest.approx(
        fmean((100, 200, 300, 250))
    )
    assert magnitude(pivot, ids["building"], kinds["3B"]) == pytest.approx(450)


def test_only_narrows_every_column_including_a_different_taxonomy():
    model, rows, kinds, ids = project()
    same = price().pivot(rows, by=kinds["apartment"], only=kinds["2B"])
    assert magnitude(same, ids["building"]) == 850
    assert magnitude(same, ids["building"], kinds["2B"]) == 850
    assert (
        same.coverage(row=ids["building"], column=kinds["3B"]).status
        is CoverageStatus.EMPTY
    )
    assert same.partition(row=ids["building"]).complete
    # An Entity has one Classification, so no record is both 2B and north.
    other = price().pivot(rows, by=kinds["aspect"], only=kinds["2B"])
    assert [c.classification for c in other.columns] == [
        None,
        kinds["north"],
        kinds["south"],
    ]
    assert magnitude(other, ids["building"]) == 850
    assert other.value(row=ids["building"], column=kinds["north"]) is None
    assert other.coverage(row=ids["building"], column=kinds["north"]).selected == ()
    assert other.partition(row=ids["building"]).uncovered == records(
        ids, "u1", "u2", "u6", "u8"
    )
    # Without only, the north column holds the north record.
    aspect = price().pivot(rows, by=kinds["aspect"])
    assert magnitude(aspect, ids["building"], kinds["north"]) == 70


def test_count_pivot_counts_each_column():
    model, rows, kinds, ids = project()
    pivot = QuantityRollup(
        key="price",
        reducer=Reducer.COUNT,
        units=None,
        contributors=Contributor.LEAVES,
    ).pivot(rows, by=kinds["apartment"])
    assert pivot.value(row=ids["building"]) == Quantity(
        magnitude=9, units="dimensionless"
    )
    assert magnitude(pivot, ids["building"], kinds["2B"]) == 4
    assert magnitude(pivot, ids["L2"], kinds["3B"]) == 1


def test_table_and_display_show_rows_in_preorder():
    model, rows, kinds, ids = project(missing=("u7",))
    pivot = price().pivot(rows, by=kinds["apartment"])
    table = pivot.to_table()
    assert table.columns == ("name", "parent_id", "All", "2B", "3B")
    assert tuple(row.id for row in table.rows) == rows.preorder()
    assert table.row(ids["L1"]).values["2B"] == Quantity(magnitude=300.0, units="AUD")
    assert table.row(ids["L1"]).values["parent_id"] == ids["building"]
    assert table.row(ids["building"]).values["3B"] is None
    text = str(pivot.display(precision=0))
    assert "2B [AUD]" in text and "  L1" in text and "    u1" in text
    assert "?" in text and "—" in text
    assert "<table" in pivot.display()._repr_html_()


def test_pivot_validates_its_arguments_and_columns():
    model, rows, kinds, ids = project()
    reduction = price()
    with pytest.raises(MissingReferenceError):
        reduction.pivot(rows, by=uuid4())
    with pytest.raises(MissingReferenceError):
        reduction.pivot(rows, only=uuid4())
    with pytest.raises(RollupError):
        reduction.pivot(rows, by=kinds["unit"], depth=0)
    with pytest.raises(TypeError):
        reduction.pivot(rows, exclusive=None)
    with pytest.raises(TypeError):
        reduction.pivot(View(model))
    whole = reduction.execute(rows)
    with pytest.raises(RollupError):
        Pivot(rows=rows, columns=())
    with pytest.raises(RollupError):
        PivotColumn(classification=kinds["2B"], parent=None, depth=0, result=whole)
    with pytest.raises(RollupError):
        Pivot(
            rows=rows,
            columns=(
                PivotColumn(classification=None, parent=None, depth=0, result=whole),
                PivotColumn(
                    classification=kinds["2B+S"],
                    parent=kinds["2B"],
                    depth=2,
                    result=whole,
                ),
            ),
        )
    other = Hierarchy.from_membership(
        View(model, entities=(ids["L1"], *records(ids, "u1", "u2", "u3", "u4", "u5"))),
        root=ids["L1"],
    )
    with pytest.raises(RollupError):
        Pivot(
            rows=rows,
            columns=(
                PivotColumn(
                    classification=None,
                    parent=None,
                    depth=0,
                    result=reduction.execute(other),
                ),
            ),
        )
    pivot = reduction.pivot(rows, by=kinds["apartment"])
    with pytest.raises(MissingReferenceError) as error:
        pivot.value(row=ids["building"], column=kinds["retail"])
    assert (error.value.kind, error.value.requested) == ("PivotColumn", kinds["retail"])
