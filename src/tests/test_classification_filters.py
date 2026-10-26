"""Classification filters and contributor rules include sub-types by default."""

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
    Quantity,
    System,
    Taxonomy,
    Value,
    ValueKind,
)
from rangekeeper.model.definitions import descendants
from rangekeeper.model.system import (
    Hierarchy,
    Reduction,
    View,
    classified,
    reducers,
)
from rangekeeper.model.system.selection import select_value
from rangekeeper.shared.errors import MissingReferenceError, ReferenceTypeError


def classes(*codes, parents):
    """Build Classifications in declaration order from code -> parent code."""
    made = {}
    for code in codes:
        parent = parents.get(code)
        made[code] = Classification(
            id=uuid4(),
            code=code,
            name=code,
            parent=None if parent is None else made[parent].id,
        )
    return made


def unit_model():
    kinds = classes(
        "unit",
        "apartment",
        "2B",
        "2B+S",
        "2B-C",
        "3B",
        "retail",
        parents={
            "apartment": "unit",
            "2B": "apartment",
            "2B+S": "2B",
            "2B-C": "2B",
            "3B": "apartment",
            "retail": "unit",
        },
    )
    measure = Measure(id=uuid4(), code="price", name="Price", units="AUD")

    def entity(code, kind, amount):
        return Entity(
            id=uuid4(),
            code=code,
            classification=None if kind is None else kinds[kind].id,
            characteristics=Characteristics(
                values=(
                    Value(
                        id=uuid4(),
                        key="price",
                        kind=ValueKind.MEASUREMENT,
                        measure=measure.id,
                        quantity=Quantity(magnitude=amount, units="AUD"),
                    ),
                )
            ),
        )

    entities = (
        entity("u1", "2B", 1),
        entity("u2", "2B+S", 10),
        entity("u3", "2B-C", 100),
        entity("u4", "3B", 1000),
        entity("u5", "retail", 10000),
        entity("u6", None, 100000),
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        definitions=Definitions(
            measures=(measure,),
            taxonomies=(
                Taxonomy(
                    id=uuid4(),
                    code="units",
                    name="Units",
                    classifications=tuple(kinds.values()),
                ),
            ),
        ),
        system=System(
            entities=entities,
            assemblies=(
                Assembly(
                    id=uuid4(),
                    code="building",
                    entities=tuple(item.id for item in entities),
                ),
            ),
        ),
    )
    return model, kinds, entities


def codes(view):
    return tuple(entity.code for entity in view.entities)


def test_descendants_follow_parents_in_declaration_order():
    model, kinds, _ = unit_model()
    expected = tuple(kinds[code] for code in ("2B", "2B+S", "2B-C", "3B"))
    assert descendants(model.definitions, kinds["apartment"].id) == expected
    assert model.descendants(kinds["apartment"].id) == expected
    assert model.descendants(kinds["2B"].id) == (kinds["2B+S"], kinds["2B-C"])
    assert model.descendants(kinds["2B+S"].id) == ()
    assert len(model.descendants(kinds["unit"].id)) == 6


def test_descendants_reject_unknown_and_wrong_kind_uuids():
    model, _, _ = unit_model()
    with pytest.raises(MissingReferenceError):
        model.descendants(uuid4())
    with pytest.raises(MissingReferenceError):
        descendants(model.definitions, uuid4())
    with pytest.raises(ReferenceTypeError):
        model.descendants(model.definitions.measures[0].id)


def test_view_filter_includes_sub_types_by_default():
    model, kinds, _ = unit_model()
    view = View(model)
    assert codes(view.filter(entity_classification=kinds["2B"].id)) == (
        "u1",
        "u2",
        "u3",
    )
    assert codes(view.filter(entity_classification=kinds["apartment"].id)) == (
        "u1",
        "u2",
        "u3",
        "u4",
    )
    assert codes(view.filter(entity_classification=kinds["unit"].id)) == (
        "u1",
        "u2",
        "u3",
        "u4",
        "u5",
    )


def test_exclusive_view_filter_matches_only_that_classification():
    model, kinds, _ = unit_model()
    view = View(model)
    assert codes(view.filter(entity_classification=kinds["2B"].id, exclusive=True)) == (
        "u1",
    )
    assert (
        codes(view.filter(entity_classification=kinds["apartment"].id, exclusive=True))
        == ()
    )
    with pytest.raises(TypeError):
        view.filter(entity_classification=kinds["2B"].id, exclusive=1)


def test_unknown_classification_is_rejected_by_filters_and_rules():
    model, _, _ = unit_model()
    with pytest.raises(MissingReferenceError):
        View(model).filter(entity_classification=uuid4())
    with pytest.raises(MissingReferenceError):
        View(model).filter(entity_classification=uuid4(), exclusive=True)
    with pytest.raises(MissingReferenceError):
        classified(model, uuid4())
    with pytest.raises(TypeError):
        classified(object(), uuid4())


def test_classified_contributor_rule_selects_sub_types_unless_exclusive():
    model, kinds, entities = unit_model()
    building = model.find_entities(code="building")[0]
    tree = Hierarchy.from_membership(View(model), root=building.id)

    def total(rule):
        reduction = Reduction(
            select=select_value("price"),
            reducer=reducers.sum,
            units="AUD",
            contributors=rule,
        )
        result = reduction.execute(tree)
        return result.root_value, result.coverage(building.id).selected

    two_bed = tuple(item.id for item in entities[:3])
    assert total(classified(model, kinds["2B"].id))[1] == two_bed
    assert total(classified(model, kinds["2B"].id))[0].magnitude == 111
    assert total(classified(model, kinds["2B"].id, exclusive=True))[0].magnitude == 1
    assert total(classified(model, kinds["apartment"].id))[0].magnitude == 1111
    assert total(classified(model, kinds["apartment"].id, exclusive=True)) == (
        None,
        (),
    )
    rule = classified(model, kinds["unit"].id)
    assert [rule(entity) for entity in entities] == [True] * 5 + [False]
    assert rule(building) is False


def test_deep_taxonomy_descendants_do_not_use_the_call_stack():
    depth = 3000
    chain = classes(
        *(f"c{i}" for i in range(depth)),
        parents={f"c{i}": f"c{i - 1}" for i in range(1, depth)},
    )
    leaf = Entity(id=uuid4(), code="leaf", classification=chain[f"c{depth - 1}"].id)
    other = Entity(id=uuid4(), code="other", classification=chain["c0"].id)
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        definitions=Definitions(
            taxonomies=(
                Taxonomy(
                    id=uuid4(),
                    code="deep",
                    name="Deep",
                    classifications=tuple(chain.values()),
                ),
            )
        ),
        system=System(entities=(leaf, other)),
    )
    assert len(model.descendants(chain["c0"].id)) == depth - 1
    assert codes(View(model).filter(entity_classification=chain["c0"].id)) == (
        "leaf",
        "other",
    )
    assert codes(View(model).filter(entity_classification=chain["c1"].id)) == ("leaf",)
    assert classified(model, chain["c1"].id)(model.entity(leaf.id))
