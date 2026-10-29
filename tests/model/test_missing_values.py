"""Filters and rollups never treat a missing value as zero (ADR-016, #157)."""

from uuid import uuid4

import pytest

from rangekeeper.flow import MissingValueHandling
from rangekeeper.model import (
    Assembly,
    Characteristics,
    Classification,
    Definitions,
    Entity,
    Filter,
    Measure,
    Metadata,
    Model,
    System,
    Taxonomy,
    Value,
    ValueKind,
    ValueRelation,
    ValueTest,
)
from rangekeeper.model.system import (
    Contributor,
    Coverage,
    CoverageStatus,
    FlowRollup,
    Hierarchy,
    QuantityRollup,
    Reducer,
    RollupError,
    View,
)
from rangekeeper.quantity import Quantity, UnitSystem, default_units
from rangekeeper.shared.codes import Code

KIND = {
    code: Classification(id=uuid4(), code=code, name=code, parent=None)
    for code in ("space",)
}
FLOOR = Classification(id=uuid4(), code="floor", name="floor", parent=KIND["space"].id)
AREA = Measure(id=uuid4(), code="area", name="Area", units="m^2")
# code, classification, gfa, nla: None is an unresolved Quantity, ... is no Value.
FLOORS = (
    ("f1", FLOOR, 1000, 800),
    ("f2", FLOOR, 2000, 1500),
    ("f3", FLOOR, None, 700),  # gfa unresolved
    ("f4", FLOOR, ..., 600),  # no gfa Value
    ("f5", FLOOR, 1500, None),  # nla unresolved
    ("s1", KIND["space"], 50, 40),
)


def value(key, magnitude):
    return Value(
        id=uuid4(),
        key=key,
        kind=ValueKind.MEASUREMENT,
        measure=AREA.id,
        **(
            {}
            if magnitude is None
            else {"quantity": Quantity(magnitude=magnitude, units="m^2")}
        ),
    )


def project(units: UnitSystem = default_units):
    entities, ids = [], {}
    for code, kind, gfa, nla in FLOORS:
        values = tuple(
            value(key, magnitude)
            for key, magnitude in (("gfa", gfa), ("nla", nla))
            if magnitude is not ...
        )
        entity = Entity(
            id=uuid4(),
            code=code,
            name=code,
            classification=kind.id,
            characteristics=Characteristics(values=values),
        )
        entities.append(entity)
        ids[code] = entity.id
    building = Assembly(id=uuid4(), code="b", name="b", entities=tuple(ids.values()))
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        definitions=Definitions(
            measures=(AREA,),
            taxonomies=(
                Taxonomy(
                    id=uuid4(),
                    code="kinds",
                    name="kinds",
                    classifications=(KIND["space"], FLOOR),
                ),
            ),
        ),
        system=System(entities=tuple(entities), assemblies=(building,)),
        units=units,
    )
    ids["b"] = building.id
    return model, Hierarchy.from_membership(View(model), root=building.id), ids


def large(minimum="1200 m^2"):
    return Filter(
        classification=FLOOR.id,
        tests=(
            ValueTest(
                key="gfa",
                relation=ValueRelation.GREATER_THAN_OR_EQUAL,
                quantity=Quantity(text=minimum),
            ),
        ),
    )


def nla(**kw):
    return QuantityRollup(key="nla", units="m^2", **kw)


def test_a_filter_selects_contributors_and_counts_undecided_ones():
    model, rows, ids = project()
    result = nla(contributors=large()).execute(rows)
    coverage = result.coverage(ids["b"])
    # f2 and f5 pass; f3 and f4 have no gfa, so the filter cannot decide them.
    assert coverage.selected == (ids["f2"], ids["f5"])
    assert coverage.undecided == (ids["f3"], ids["f4"])
    assert coverage.missing == (ids["f5"],)
    assert coverage.status is CoverageStatus.INCOMPLETE and not coverage.complete
    assert result.value(ids["b"]) is None
    assert result.available_value(ids["b"]).number == 1500


def test_a_filter_tests_values_in_the_rollup_unit_system() -> None:
    # The Model reads a bay as 1000 m^2; the rollup reads it as 2000 m^2. The
    # rollup's unit system converts the Values and tests the Filter (#433).
    model, rows, ids = project(UnitSystem(definitions=("bay = 1000 m^2",)))
    bays = UnitSystem(definitions=("bay = 2000 m^2",))
    one_bay = Filter(
        classification=FLOOR.id,
        tests=(
            ValueTest(
                key="gfa",
                relation=ValueRelation.GREATER_THAN_OR_EQUAL,
                quantity=Quantity(magnitude=1, units="bay"),
            ),
        ),
    )
    result = nla(contributors=one_bay, unit_system=bays).execute(rows)
    assert result.coverage(ids["b"]).selected == (ids["f2"],)
    # Without its own unit system, the rollup tests with the Model's.
    selected = nla(contributors=one_bay).execute(rows).coverage(ids["b"]).selected
    assert selected == (ids["f1"], ids["f2"], ids["f5"])


def test_undecided_contributors_alone_make_coverage_incomplete():
    model, rows, ids = project()
    result = nla(contributors=large(), require_complete=False).execute(rows)
    f3 = result.coverage(ids["f3"])
    assert f3.selected == () and f3.undecided == (ids["f3"],)
    assert f3.status is CoverageStatus.INCOMPLETE
    assert result.value(ids["f3"]) is None
    # A failed filter is decided: the Entity is simply not a contributor.
    assert result.coverage(ids["f1"]).status is CoverageStatus.EMPTY
    assert result.coverage(ids["s1"]).status is CoverageStatus.EMPTY


def test_a_less_than_test_never_reads_a_missing_value_as_zero():
    model, rows, ids = project()
    small = Filter(
        classification=KIND["space"].id,
        tests=(
            ValueTest(
                key="gfa",
                relation=ValueRelation.LESS_THAN,
                quantity=Quantity(text="100 m^2"),
            ),
        ),
    )
    result = nla(contributors=small, require_complete=False).execute(rows)
    coverage = result.coverage(ids["b"])
    assert coverage.selected == (ids["s1"],)
    assert coverage.undecided == (ids["f3"], ids["f4"])
    assert result.value(ids["b"]).number == 40


def test_missing_values_are_not_zero_for_any_reducer():
    model, rows, ids = project()
    floors = Filter(classification=FLOOR.id)
    expected = {
        Reducer.SUM: 800 + 1500 + 700 + 600,
        Reducer.MEAN: (800 + 1500 + 700 + 600) / 4,
        Reducer.MIN: 600,
        Reducer.MAX: 1500,
    }
    for reducer, number in expected.items():
        result = nla(contributors=floors, reducer=reducer).execute(rows)
        assert result.value(ids["b"]) is None
        assert result.available_value(ids["b"]).number == pytest.approx(number)
        assert result.coverage(ids["b"]).missing == (ids["f5"],)
    count = QuantityRollup(key="nla", reducer=Reducer.COUNT, contributors=floors)
    assert count.execute(rows).available_value(ids["b"]).number == 4


def test_a_filter_with_only_decided_contributors_is_complete():
    model, rows, ids = project()
    result = QuantityRollup(
        key="gfa", units="m^2", contributors=Filter(classification=FLOOR.id)
    ).execute(rows)
    coverage = result.coverage(ids["b"])
    assert coverage.undecided == ()
    assert coverage.missing == (ids["f3"], ids["f4"])
    assert result.value(ids["b"]) is None


def test_a_pivot_keeps_undecided_contributors_in_every_column():
    model, rows, ids = project()
    pivot = nla(contributors=large()).pivot(rows, by=KIND["space"].id)
    for column in (None, FLOOR.id):
        assert pivot.coverage(row=ids["b"], column=column).undecided == (
            ids["f3"],
            ids["f4"],
        )
        assert pivot.value(row=ids["b"], column=column) is None


def test_rollup_errors_have_the_rollup_code() -> None:
    # Rollup is the word for totals over a hierarchy (D38, #388).
    model, rows, ids = project()
    with pytest.raises(RollupError) as raised:
        Coverage(
            selected=(ids["f1"],), measured=(), missing=()
        )  # measured and missing must cover selected
    assert raised.value.code is Code.ROLLUP
    assert Code.ROLLUP == "rollup"
    assert not hasattr(Code, "AGGREGATION")


def test_flow_rollups_refuse_to_read_missing_movements_as_zero():
    with pytest.raises(ValueError, match="zero"):
        FlowRollup(key="cash", missing=MissingValueHandling.ZERO)


def test_flow_rollups_take_a_filter_and_count_undecided_owners():
    model, rows, ids = project()
    result = FlowRollup(key="cash", contributors=large()).execute(rows)
    coverage = result.coverage(ids["b"])
    assert coverage.undecided == (ids["f3"], ids["f4"])
    # No owner has a cash Flow: every selected owner is missing, never zero.
    assert coverage.missing == (ids["f2"], ids["f5"])
    assert result.available_value(ids["b"]) is None


def test_coverage_keeps_undecided_owners_apart_from_selected_ones():
    a, b = uuid4(), uuid4()
    assert (
        Coverage(selected=(a,), measured=(a,), missing=(), undecided=(b,)).status
        is CoverageStatus.INCOMPLETE
    )
    assert (
        Coverage(selected=(), measured=(), missing=(), undecided=(b,)).status
        is CoverageStatus.INCOMPLETE
    )
    assert Coverage(selected=(), measured=(), missing=()).status is CoverageStatus.EMPTY
    with pytest.raises(RollupError):
        Coverage(selected=(a,), measured=(a,), missing=(), undecided=(a,))
    with pytest.raises(RollupError):
        Coverage(selected=(), measured=(), missing=(), undecided=(b, b))


def test_contributors_reject_other_types():
    with pytest.raises(TypeError):
        nla(contributors="floors")
    assert nla(contributors=Contributor.ALL).contributors is Contributor.ALL
