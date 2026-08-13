import pytest

import rangekeeper as rk
from rangekeeper.graph.kind import EntityType


def make_apartment_types():
    apartment = EntityType(code="apartment", name="Apartment")
    three_bed = apartment.define(
        code="apartment.3bed",
        name="3-bed Apartment",
    )
    corner = three_bed.define(
        code="apartment.3bed.corner",
        name="3-bed Corner Apartment",
    )
    return apartment, three_bed, corner


def test_entity_type_module_is_public():
    assert rk.graph.kind.EntityType is EntityType
    assert rk.graph.EntityType is EntityType


def test_constructor_parenting_and_define_keep_both_sides_consistent():
    apartment = EntityType(code="apartment", name="Apartment")
    two_bed = EntityType(
        code="apartment.2bed",
        name="2-bed Apartment",
        parent=apartment,
    )
    three_bed = apartment.define(
        code="apartment.3bed",
        name="3-bed Apartment",
    )

    assert apartment.children == (two_bed, three_bed)
    assert two_bed.parent is apartment
    assert three_bed.parent is apartment


def test_constructor_children_are_parented_in_order():
    office = EntityType(code="office", name="Office")
    retail = EntityType(code="retail", name="Retail")
    building = EntityType(
        code="building",
        name="Building",
        children=[office, retail],
    )

    assert building.children == (office, retail)
    assert office.parent is building
    assert retail.parent is building


def test_reparenting_and_removal_keep_both_sides_consistent():
    residential = EntityType(code="residential", name="Residential")
    commercial = EntityType(code="commercial", name="Commercial")
    mixed_use = EntityType(code="mixed-use", name="Mixed Use")

    residential.add_child(mixed_use)
    commercial.add_child(mixed_use)

    assert residential.children == ()
    assert commercial.children == (mixed_use,)
    assert mixed_use.parent is commercial

    commercial.remove_child(mixed_use)
    assert commercial.children == ()
    assert mixed_use.parent is None

    mixed_use.remove_parent()
    assert mixed_use.parent is None


def test_readding_a_child_does_not_duplicate_it():
    parent = EntityType(code="parent", name="Parent")
    child = EntityType(code="child", name="Child")

    parent.add_child(child)
    parent.add_child(child)

    assert parent.children == (child,)


def test_add_and_remove_children():
    parent = EntityType(code="parent", name="Parent")
    children = (
        EntityType(code="child-1", name="Child 1"),
        EntityType(code="child-2", name="Child 2"),
    )

    parent.add_children(children)
    assert parent.children == children

    parent.remove_children(children)
    assert parent.children == ()
    assert all(child.parent is None for child in children)


def test_self_parenting_and_cycles_are_rejected():
    apartment, three_bed, corner = make_apartment_types()

    with pytest.raises(ValueError, match="own parent"):
        apartment.set_parent(apartment)

    with pytest.raises(ValueError, match="cycle"):
        apartment.set_parent(corner)

    assert apartment.parent is None
    assert three_bed.parent is apartment
    assert corner.parent is three_bed


def test_duplicate_codes_are_rejected_within_a_connected_hierarchy():
    apartment, _, _ = make_apartment_types()
    duplicate = EntityType(code="apartment.3bed", name="Duplicate")

    with pytest.raises(ValueError, match="apartment.3bed"):
        apartment.add_child(duplicate)

    assert duplicate.parent is None
    assert duplicate not in apartment.children


def test_reparenting_within_a_hierarchy_does_not_conflict_with_own_subtree():
    apartment, three_bed, corner = make_apartment_types()

    apartment.add_child(corner)

    assert corner.parent is apartment
    assert three_bed.children == ()
    assert apartment.children == (three_bed, corner)


def test_traversal_order_lineage_and_type_checks():
    apartment, three_bed, corner = make_apartment_types()
    two_bed = apartment.define(
        code="apartment.2bed",
        name="2-bed Apartment",
    )

    assert corner.ancestors() == (apartment, three_bed)
    assert apartment.descendants() == (three_bed, corner, two_bed)
    assert corner.lineage() == (apartment, three_bed, corner)
    assert corner.root() is apartment
    assert corner.is_a(corner)
    assert corner.is_a(three_bed)
    assert corner.is_a(apartment)
    assert not two_bed.is_a(three_bed)
    assert corner.find("apartment.2bed") is two_bed
    assert corner.find("missing") is None


def test_code_is_immutable_and_children_are_read_only():
    parent = EntityType(code="parent", name="Parent")

    with pytest.raises(AttributeError):
        parent.code = "renamed"

    with pytest.raises(AttributeError):
        parent.children = ()


def test_flat_record_serialization_and_reconstruction():
    apartment, three_bed, corner = make_apartment_types()
    corner.definition = "An apartment on a building corner."

    records = corner.to_records()

    assert records == (
        {
            "code": "apartment",
            "name": "Apartment",
            "definition": None,
            "parent_code": None,
        },
        {
            "code": "apartment.3bed",
            "name": "3-bed Apartment",
            "definition": None,
            "parent_code": "apartment",
        },
        {
            "code": "apartment.3bed.corner",
            "name": "3-bed Corner Apartment",
            "definition": "An apartment on a building corner.",
            "parent_code": "apartment.3bed",
        },
    )

    (restored,) = EntityType.from_records(records)
    restored_three_bed = restored.find(three_bed.code)
    restored_corner = restored.find(corner.code)

    assert restored_three_bed is not None
    assert restored_corner is not None
    assert restored_corner.parent is restored_three_bed
    assert restored_corner.is_a(restored)
    assert restored.to_records() == records


def test_reconstruction_validates_duplicate_and_unknown_codes():
    duplicate_records = [
        {"code": "type", "name": "Type", "parent_code": None},
        {"code": "type", "name": "Duplicate", "parent_code": None},
    ]
    with pytest.raises(ValueError, match="duplicate"):
        EntityType.from_records(duplicate_records)

    unknown_parent_records = [
        {"code": "child", "name": "Child", "parent_code": "missing"},
    ]
    with pytest.raises(ValueError, match="unknown parent"):
        EntityType.from_records(unknown_parent_records)
