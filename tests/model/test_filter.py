"""Declarative Filters: label sub-types, unit-aware comparisons and presence (#121)."""

from uuid import uuid4

import pytest

from rangekeeper.model import (
    Characteristics,
    Classification,
    Criterion,
    Definitions,
    Entity,
    Filter,
    Label,
    Measure,
    Metadata,
    Model,
    Relationship,
    System,
    Taxonomy,
    Value,
    ValueKind,
    ValueRelation,
    ValueTest,
)
from rangekeeper.model.content import encode
from rangekeeper.model.system import Match, View
from rangekeeper.model.system.errors import SelectionError
from rangekeeper.model.system.matching import _prepare
from rangekeeper.quantity import Quantity, UnitError
from rangekeeper.shared.errors import MissingReferenceError, ValidationError


def classes(*codes, parents=None):
    made = {}
    for code in codes:
        parent = (parents or {}).get(code)
        made[code] = Classification(
            id=uuid4(),
            code=code,
            name=code,
            parent=None if parent is None else made[parent].id,
        )
    return made


KINDS = classes(
    "kind",
    "space",
    "floor",
    "podium",
    "building",
    "contains",
    parents={
        "space": "kind",
        "floor": "space",
        "podium": "floor",
        "building": "kind",
        "contains": "kind",
    },
)
USES = classes(
    "use",
    "residential",
    "hotel",
    "retail",
    "suite",
    parents={
        "residential": "use",
        "hotel": "use",
        "retail": "use",
        "suite": "hotel",
    },
)
AREA = Measure(id=uuid4(), code="area", name="Area", units="m^2")


def gfa(magnitude, units="m^2", *, key="gfa"):
    return Value(
        id=uuid4(),
        key=key,
        kind=ValueKind.MEASUREMENT,
        measure=AREA.id,
        quantity=None
        if magnitude is None
        else Quantity(magnitude=magnitude, units=units),
    )


def entity(code, kind, *values, uses=None):
    labels = (
        ()
        if uses is None
        else (
            Label(
                id=uuid4(),
                key="use",
                classifications=tuple(USES[use].id for use in uses),
            ),
        )
    )
    return Entity(
        id=uuid4(),
        code=code,
        classification=None if kind is None else KINDS[kind].id,
        characteristics=Characteristics(values=values, labels=labels),
    )


ENTITIES = (
    entity("b", "building", gfa(9000)),
    entity("f1", "floor", gfa(1500), uses=("residential",)),
    entity("f2", "floor", gfa(16000, "ft^2"), uses=("hotel",)),  # 1486.45 m^2
    entity("f3", "podium", gfa(2000), uses=("suite",)),
    entity("f4", "floor", gfa(None), uses=("retail",)),  # unresolved
    entity("f5", "floor", uses=("residential", "retail")),  # no gfa
    entity("f6", "floor", gfa(1200)),  # no use label
    entity(
        "p1",
        "floor",
        Value(id=uuid4(), key="gfa", kind=ValueKind.PROPERTY, content=encode("big")),
        uses=("retail",),
    ),
    entity("x", None, gfa(5000)),
)


def build():
    by_code = {item.code: item for item in ENTITIES}
    edges = tuple(
        Relationship(
            id=uuid4(),
            source=by_code["b"].id,
            target=by_code[code].id,
            classification=KINDS["contains"].id,
        )
        for code in ("f1", "f2", "f3")
    )
    return Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        definitions=Definitions(
            measures=(AREA,),
            taxonomies=(
                Taxonomy(
                    id=uuid4(),
                    code="kinds",
                    name="Kinds",
                    classifications=tuple(KINDS.values()),
                ),
                Taxonomy(
                    id=uuid4(),
                    code="uses",
                    name="Uses",
                    classifications=tuple(USES.values()),
                ),
            ),
        ),
        system=System(entities=ENTITIES, relationships=edges),
    )


MODEL = build()
VIEW = View(MODEL, entities=[item.id for item in ENTITIES if item.code != "p1"])


def codes(ids):
    return tuple(MODEL.entity(id).code for id in ids)


def value_test(relation, quantity=None, *, minimum=None, maximum=None, key="gfa"):
    def parse(text):
        return None if text is None else Quantity(text=text)

    return ValueTest(
        key=key,
        relation=relation,
        **{
            name: parse(item)
            for name, item in (
                ("quantity", quantity),
                ("minimum", minimum),
                ("maximum", maximum),
            )
            if item is not None
        },
    )


def test_an_empty_filter_passes_every_entity():
    result = VIEW.match(condition=Filter())
    assert result == Match(
        passed=tuple(item.id for item in VIEW.entities), failed=(), undecided=()
    )
    assert result.complete


def test_classification_includes_sub_types_unless_exclusive():
    floors = Filter(classification=KINDS["floor"].id)
    assert codes(VIEW.match(condition=floors).passed) == (
        "f1",
        "f2",
        "f3",
        "f4",
        "f5",
        "f6",
    )
    exact = Filter(classification=KINDS["floor"].id, exclusive=True)
    assert "f3" not in codes(VIEW.match(condition=exact).passed)
    # An Entity without a classification fails; it is not undecided.
    assert "x" in codes(VIEW.match(condition=floors).failed)


def test_labels_include_sub_types_and_a_missing_label_is_undecided():
    hotel = Filter(labels=(Criterion(key="use", classification=USES["hotel"].id),))
    result = VIEW.match(condition=hotel)
    assert codes(result.passed) == ("f2", "f3")
    assert codes(result.undecided) == ("b", "f6", "x")
    exact = Filter(
        labels=(Criterion(key="use", classification=USES["hotel"].id, exclusive=True),)
    )
    assert codes(VIEW.match(condition=exact).passed) == ("f2",)


def test_a_label_with_several_classifications_matches_any_of_them():
    retail = Filter(labels=(Criterion(key="use", classification=USES["retail"].id),))
    assert codes(VIEW.match(condition=retail).passed) == ("f4", "f5")


@pytest.mark.parametrize(
    ("relation", "quantity", "passed"),
    [
        (ValueRelation.EQUAL, "1500 m^2", ("f1",)),
        (ValueRelation.EQUAL, "16000 ft^2", ("f2",)),
        (ValueRelation.NOT_EQUAL, "1500 m^2", ("b", "f2", "f3", "f6", "x")),
        (ValueRelation.LESS_THAN, "1500 m^2", ("f2", "f6")),
        (ValueRelation.LESS_THAN_OR_EQUAL, "1500 m^2", ("f1", "f2", "f6")),
        (ValueRelation.GREATER_THAN, "1500 m^2", ("b", "f3", "x")),
        (ValueRelation.GREATER_THAN_OR_EQUAL, "0.15 ha", ("b", "f1", "f3", "x")),
    ],
)
def test_comparisons_convert_units(relation, quantity, passed):
    result = VIEW.match(condition=Filter(tests=(value_test(relation, quantity),)))
    assert codes(result.passed) == passed
    # The unresolved and the absent Values are missing, never zero.
    assert codes(result.undecided) == ("f4", "f5")
    assert set(result.failed) == {item.id for item in VIEW.entities} - set(
        result.passed
    ) - set(result.undecided)


def test_between_includes_both_bounds_in_their_own_units():
    condition = Filter(
        tests=(
            value_test(
                ValueRelation.BETWEEN,
                minimum="16000 ft^2",
                maximum="0.2 ha",
            ),
        )
    )
    result = VIEW.match(condition=condition)
    assert codes(result.passed) == ("f1", "f2", "f3")
    assert codes(result.undecided) == ("f4", "f5")


def test_a_less_than_zero_test_does_not_pass_a_missing_value():
    result = VIEW.match(
        condition=Filter(tests=(value_test(ValueRelation.LESS_THAN_OR_EQUAL, "0 m^2"),))
    )
    assert result.passed == ()
    assert codes(result.undecided) == ("f4", "f5")
    assert not result.complete


def test_presence_tests_decide_every_entity():
    present = VIEW.match(condition=Filter(tests=(value_test(ValueRelation.PRESENT),)))
    missing = VIEW.match(condition=Filter(tests=(value_test(ValueRelation.MISSING),)))
    assert codes(missing.passed) == ("f4", "f5")
    assert present.passed == missing.failed
    assert present.complete and missing.complete
    # Presence also tests property content.
    view = View(MODEL)
    assert "p1" in codes(
        view.match(condition=Filter(tests=(value_test(ValueRelation.PRESENT),))).passed
    )


def test_a_failed_test_wins_over_a_missing_value():
    condition = Filter(
        classification=KINDS["building"].id,
        tests=(value_test(ValueRelation.GREATER_THAN, "1 m^2"),),
    )
    result = VIEW.match(condition=condition)
    assert codes(result.passed) == ("b",)
    assert result.undecided == ()


def test_all_tests_must_hold():
    condition = Filter(
        classification=KINDS["floor"].id,
        labels=(Criterion(key="use", classification=USES["residential"].id),),
        tests=(value_test(ValueRelation.GREATER_THAN_OR_EQUAL, "1500 m^2"),),
    )
    result = VIEW.match(condition=condition)
    assert codes(result.passed) == ("f1",)
    # f5 is residential with no gfa. f6 has no use label, but its gfa fails.
    assert codes(result.undecided) == ("f5",)
    assert "f6" in codes(result.failed)


def test_where_keeps_passing_entities_and_their_edges():
    floors = VIEW.where(condition=Filter(classification=KINDS["floor"].id))
    assert floors.relationships == ()
    big = VIEW.where(
        condition=Filter(tests=(value_test(ValueRelation.GREATER_THAN, "1400 m^2"),))
    )
    assert codes(item.id for item in big.entities) == ("b", "f1", "f2", "f3", "x")
    assert len(big.relationships) == 3


def test_comparisons_need_a_measurement_value():
    with pytest.raises(SelectionError, match="measurement"):
        View(MODEL).match(
            condition=Filter(tests=(value_test(ValueRelation.EQUAL, "1 m^2"),))
        )


def test_incompatible_and_unknown_units_raise():
    with pytest.raises(UnitError):
        VIEW.match(
            condition=Filter(tests=(value_test(ValueRelation.LESS_THAN, "1 AUD"),))
        )
    with pytest.raises(UnitError):
        _prepare(
            MODEL,
            Filter(
                tests=(
                    ValueTest(
                        key="gfa",
                        relation=ValueRelation.LESS_THAN,
                        quantity=Quantity(magnitude=1, units="no_such_unit"),
                    ),
                )
            ),
        )


def test_unknown_classifications_raise():
    with pytest.raises(MissingReferenceError):
        VIEW.match(condition=Filter(classification=uuid4()))
    with pytest.raises(MissingReferenceError):
        VIEW.match(
            condition=Filter(labels=(Criterion(key="use", classification=uuid4()),))
        )


def test_the_record_checks_its_operands():
    with pytest.raises(ValidationError):
        ValueTest(key="gfa", relation=ValueRelation.LESS_THAN)
    with pytest.raises(ValidationError):
        ValueTest(
            key="gfa",
            relation=ValueRelation.BETWEEN,
            quantity=Quantity(text="1 m^2"),
        )
    with pytest.raises(ValidationError):
        ValueTest(
            key="gfa",
            relation=ValueRelation.PRESENT,
            quantity=Quantity(text="1 m^2"),
        )


def test_exclusive_is_true_or_absent_and_needs_a_classification() -> None:
    # One meaning has one encoding: absent matches sub-types (#386).
    floor = KINDS["floor"].id
    for value in (False, None):
        with pytest.raises(ValidationError):
            Filter(classification=floor, exclusive=value)
        with pytest.raises(ValidationError):
            Criterion(key="use", classification=floor, exclusive=value)
    with pytest.raises(ValidationError):
        Filter(exclusive=True)
    with pytest.raises(ValidationError):
        Filter.from_data({"classification": str(floor), "exclusive": False})
    assert Filter(classification=floor).to_data() == {"classification": str(floor)}


def test_value_relations_use_the_operator_words() -> None:
    assert [relation.value for relation in ValueRelation][2:6] == [
        "less_than",
        "less_than_or_equal",
        "greater_than",
        "greater_than_or_equal",
    ]


def test_a_filter_round_trips_as_data():
    condition = Filter(
        classification=KINDS["floor"].id,
        exclusive=True,
        labels=(Criterion(key="use", classification=USES["hotel"].id),),
        tests=(
            value_test(ValueRelation.BETWEEN, minimum="1 m^2", maximum="2 m^2"),
            value_test(ValueRelation.MISSING, key="nla"),
        ),
    )
    assert Filter.from_data(condition.to_data()) == condition
    assert condition.to_data()["tests"][1] == {"key": "nla", "relation": "missing"}


def test_wrong_inputs_raise_type_errors():
    with pytest.raises(TypeError):
        VIEW.match(condition={"classification": KINDS["floor"].id})
    with pytest.raises(TypeError):
        _prepare(MODEL, Filter(), unit_system="m")
