"""Pivot columns by a label key: a Label's Taxonomy splits the columns (#159)."""

from uuid import uuid4

import pytest

from rangekeeper.model import (
    Assembly,
    Characteristics,
    Classification,
    Definitions,
    Entity,
    Label,
    Measure,
    Metadata,
    Model,
    System,
    Taxonomy,
    Value,
    ValueKind,
)
from rangekeeper.model.system import (
    CoverageStatus,
    Hierarchy,
    QuantityRollup,
    RollupError,
    View,
)
from rangekeeper.quantity import Quantity
from rangekeeper.shared.errors import MissingReferenceError


def taxonomy(code, *pairs):
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


USES, USE = taxonomy(
    "uses",
    ("use", None),
    ("residential", "use"),
    ("apartment", "residential"),
    ("hotel", "use"),
    ("retail", "use"),
)
ASPECTS, ASPECT = taxonomy("aspects", ("aspect", None), ("north", "aspect"))
AREA = Measure(id=uuid4(), code="area", name="Area", units="m^2")
FLOORS = (
    # code, building, uses, gfa
    ("a1", "A", ("residential",), 100),
    ("a2", "A", ("apartment",), 200),
    ("a3", "A", ("hotel", "retail"), 400),
    ("a4", "A", (), 800),
    ("b1", "B", ("hotel",), 1000),
    ("b2", "B", ("retail",), None),
    ("b3", "B", ("north",), 2000),
)


def project():
    entities, ids = [], {}
    for code, _, uses, gfa in FLOORS:
        kinds = {**USE, **ASPECT}
        labels = (
            (
                Label(
                    id=uuid4(), key="use", classifications=tuple(kinds[u] for u in uses)
                ),
            )
            if uses
            else ()
        )
        quantity = (
            {} if gfa is None else {"quantity": Quantity(magnitude=gfa, units="m^2")}
        )
        entity = Entity(
            id=uuid4(),
            code=code,
            name=code,
            characteristics=Characteristics(
                labels=labels,
                values=(
                    Value(
                        id=uuid4(),
                        key="gfa",
                        kind=ValueKind.MEASUREMENT,
                        measure=AREA.id,
                        **quantity,
                    ),
                ),
            ),
        )
        entities.append(entity)
        ids[code] = entity.id
    buildings = {
        name: Assembly(
            id=uuid4(),
            code=name,
            name=name,
            entities=tuple(ids[code] for code, at, _, _ in FLOORS if at == name),
        )
        for name in ("A", "B")
    }
    site = Assembly(
        id=uuid4(),
        code="site",
        name="site",
        entities=tuple(item.id for item in buildings.values()),
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        definitions=Definitions(measures=(AREA,), taxonomies=(USES, ASPECTS)),
        system=System(entities=tuple(entities), assemblies=(site, *buildings.values())),
    )
    ids.update({name: item.id for name, item in buildings.items()})
    ids["site"] = site.id
    return model, Hierarchy.from_membership(View(model), root=site.id), ids


GFA = QuantityRollup(key="gfa", units="m^2", require_complete=False)


def number(pivot, row, column=None):
    value = pivot.value(row=row, column=column)
    return None if value is None else value.number


def test_a_label_key_splits_the_columns_by_its_taxonomy():
    model, rows, ids = project()
    pivot = GFA.pivot(rows, label="use", by=USE["use"])
    assert pivot.label == "use"
    assert [(c.classification, c.parent, c.depth) for c in pivot.columns] == [
        (None, None, 0),
        (USE["residential"], None, 1),
        (USE["hotel"], None, 1),
        (USE["retail"], None, 1),
    ]
    # Sub-types count with their parent column: apartment is residential.
    assert number(pivot, ids["A"], USE["residential"]) == 300
    assert number(pivot, ids["site"], USE["hotel"]) == 1400
    assert number(pivot, ids["site"], USE["retail"]) == 400
    assert number(pivot, ids["site"]) == 4500
    assert pivot.to_table().columns == (
        "name",
        "parent_id",
        "All",
        "residential",
        "hotel",
        "retail",
    )


def test_by_chooses_the_column_parent_and_depth_goes_deeper():
    model, rows, ids = project()
    pivot = GFA.pivot(rows, label="use", by=USE["residential"])
    assert [c.classification for c in pivot.columns] == [None, USE["apartment"]]
    assert number(pivot, ids["site"], USE["apartment"]) == 200
    deep = GFA.pivot(rows, label="use", by=USE["use"], depth=2)
    assert (USE["apartment"], USE["residential"], 2) in [
        (c.classification, c.parent, c.depth) for c in deep.columns
    ]


def test_coverage_reports_overlap_uncovered_and_outside():
    model, rows, ids = project()
    pivot = GFA.pivot(rows, label="use", by=USE["use"])
    a = pivot.partition(row=ids["A"])
    # a3 is both hotel and retail; a4 has no use label.
    assert a.overlap == (ids["a3"],)
    assert a.uncovered == (ids["a4"],)
    assert a.outside == () and not a.complete
    b = pivot.partition(row=ids["B"])
    # b3's label is from another Taxonomy, so no use column holds it.
    assert b.uncovered == (ids["b3"],) and b.overlap == ()
    exact = GFA.pivot(rows, label="use", by=USE["use"], exclusive=True)
    # With exclusive columns, apartment is in no column.
    assert exact.partition(row=ids["A"]).uncovered == (ids["a2"], ids["a4"])


def test_missing_values_stay_visible_in_label_columns():
    model, rows, ids = project()
    pivot = QuantityRollup(key="gfa", units="m^2").pivot(
        rows, label="use", by=USE["use"]
    )
    coverage = pivot.coverage(row=ids["B"], column=USE["retail"])
    assert coverage.missing == (ids["b2"],)
    assert coverage.status is CoverageStatus.INCOMPLETE
    assert pivot.value(row=ids["B"], column=USE["retail"]) is None
    assert pivot.available_value(row=ids["B"], column=USE["retail"]) is None
    assert pivot.value(row=ids["B"], column=USE["hotel"]).number == 1000


def test_only_narrows_the_label_columns_by_entity_classification():
    model, rows, ids = project()
    pivot = GFA.pivot(rows, label="use", by=USE["use"], only=USE["hotel"])
    # No floor has the hotel Classification itself; only labels name it.
    assert pivot.coverage(row=ids["site"]).status is CoverageStatus.EMPTY


def test_a_label_without_any_values_gives_the_all_column_alone():
    model, rows, ids = project()
    pivot = GFA.pivot(rows, label="tenure")
    assert [c.classification for c in pivot.columns] == [None]
    assert pivot.column().result == GFA.execute(rows)


def test_without_by_the_columns_come_from_the_labels_taxonomy():
    model, _, ids = project()
    floors = [ids[code] for code, at, _, _ in FLOORS if at == "A"]
    rows = Hierarchy.from_membership(
        View(model, entities=(ids["A"], *floors), relationships=()), root=ids["A"]
    )
    pivot = GFA.pivot(rows, label="use")
    assert [c.classification for c in pivot.columns] == [
        None,
        USE["residential"],
        USE["hotel"],
        USE["retail"],
    ]


def test_without_by_the_labels_need_one_taxonomy():
    model, rows, ids = project()
    # b3's use label names a Classification of another Taxonomy.
    with pytest.raises(RollupError, match="by="):
        GFA.pivot(rows, label="use")


def test_label_arguments_are_checked():
    model, rows, ids = project()
    with pytest.raises(ValueError):
        GFA.pivot(rows, label=" ")
    with pytest.raises(MissingReferenceError):
        GFA.pivot(rows, label="use", by=uuid4())
