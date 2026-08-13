import pytest

import rangekeeper as rk
from rangekeeper.graph.kind import Kind


def make_apartment_kinds():
    apartment = Kind(code="apartment", name="Apartment")
    three_bed = apartment.define(
        code="apartment.3bed",
        name="3-bed Apartment",
    )
    corner = three_bed.define(
        code="apartment.3bed.corner",
        name="3-bed Corner Apartment",
    )
    return apartment, three_bed, corner


def test_kind_module_is_public():
    assert rk.graph.kind.Kind is Kind
    assert rk.graph.Kind is Kind


def test_constructor_parenting_and_define_keep_both_sides_consistent():
    apartment = Kind(code="apartment", name="Apartment")
    two_bed = Kind(
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
    office = Kind(code="office", name="Office")
    retail = Kind(code="retail", name="Retail")
    building = Kind(
        code="building",
        name="Building",
        children=[office, retail],
    )

    assert building.children == (office, retail)
    assert office.parent is building
    assert retail.parent is building


def test_reparenting_and_removal_keep_both_sides_consistent():
    residential = Kind(code="residential", name="Residential")
    commercial = Kind(code="commercial", name="Commercial")
    mixed_use = Kind(code="mixed-use", name="Mixed Use")

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
    parent = Kind(code="parent", name="Parent")
    child = Kind(code="child", name="Child")

    parent.add_child(child)
    parent.add_child(child)

    assert parent.children == (child,)


def test_add_and_remove_children():
    parent = Kind(code="parent", name="Parent")
    children = (
        Kind(code="child-1", name="Child 1"),
        Kind(code="child-2", name="Child 2"),
    )

    parent.add_children(children)
    assert parent.children == children

    parent.remove_children(children)
    assert parent.children == ()
    assert all(child.parent is None for child in children)


def test_self_parenting_and_cycles_are_rejected():
    apartment, three_bed, corner = make_apartment_kinds()

    with pytest.raises(ValueError, match="own parent"):
        apartment.set_parent(apartment)

    with pytest.raises(ValueError, match="cycle"):
        apartment.set_parent(corner)

    assert apartment.parent is None
    assert three_bed.parent is apartment
    assert corner.parent is three_bed


def test_duplicate_codes_are_rejected_within_a_connected_hierarchy():
    apartment, _, _ = make_apartment_kinds()
    duplicate = Kind(code="apartment.3bed", name="Duplicate")

    with pytest.raises(ValueError, match="apartment.3bed"):
        apartment.add_child(duplicate)

    assert duplicate.parent is None
    assert duplicate not in apartment.children


def test_reparenting_within_a_hierarchy_does_not_conflict_with_own_subtree():
    apartment, three_bed, corner = make_apartment_kinds()

    apartment.add_child(corner)

    assert corner.parent is apartment
    assert three_bed.children == ()
    assert apartment.children == (three_bed, corner)


def test_traversal_order_lineage_and_kind_checks():
    apartment, three_bed, corner = make_apartment_kinds()
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
    parent = Kind(code="parent", name="Parent")

    with pytest.raises(AttributeError):
        parent.code = "renamed"

    with pytest.raises(AttributeError):
        parent.children = ()


def test_classification_provenance_is_inherited_and_read_only():
    classification = Kind(
        code="abs.fcb",
        name="Functional Classification of Buildings",
        scheme="ABS FCB",
        edition="2021",
        publisher="Australian Bureau of Statistics",
        uri="https://www.abs.gov.au/statistics/classifications/functional-classification-buildings/latest-release",
    )
    commercial = classification.define(code="2", name="Commercial Buildings")
    office = commercial.define(code="231", name="Offices")

    assert office.scheme == "ABS FCB"
    assert office.edition == "2021"
    assert office.publisher == "Australian Bureau of Statistics"
    assert office.uri == classification.uri

    with pytest.raises(AttributeError):
        office.scheme = "Changed"


def test_classification_provenance_belongs_only_to_a_root():
    classification = Kind(
        code="abs.fcb",
        name="Functional Classification of Buildings",
        scheme="ABS FCB",
    )
    other = Kind(code="other", name="Other")

    with pytest.raises(ValueError, match="remain a root"):
        classification.set_parent(other)
    with pytest.raises(ValueError, match="remain a root"):
        Kind(
            code="231",
            name="Offices",
            scheme="ABS FCB",
            parent=classification,
        )
    with pytest.raises(ValueError, match="scheme is required"):
        Kind(code="fcb", name="FCB", edition="2021")


def test_flat_record_serialization_and_reconstruction():
    apartment, three_bed, corner = make_apartment_kinds()
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

    (restored,) = Kind.from_records(records)
    restored_three_bed = restored.find(three_bed.code)
    restored_corner = restored.find(corner.code)

    assert restored_three_bed is not None
    assert restored_corner is not None
    assert restored_corner.parent is restored_three_bed
    assert restored_corner.is_a(restored)
    assert restored.to_records() == records


def test_classification_provenance_serialization_and_reconstruction():
    classification = Kind(
        code="abs.fcb",
        name="Functional Classification of Buildings",
        scheme="ABS FCB",
        edition="2021",
        publisher="Australian Bureau of Statistics",
        uri="https://www.abs.gov.au/statistics/classifications/functional-classification-buildings/latest-release",
    )
    office = classification.define(code="231", name="Offices")

    records = office.to_records()

    assert records[0] == {
        "code": "abs.fcb",
        "name": "Functional Classification of Buildings",
        "definition": None,
        "parent_code": None,
        "scheme": "ABS FCB",
        "edition": "2021",
        "publisher": "Australian Bureau of Statistics",
        "uri": "https://www.abs.gov.au/statistics/classifications/functional-classification-buildings/latest-release",
    }
    assert "scheme" not in records[1]

    (restored,) = Kind.from_records(records)
    restored_office = restored.find("231")

    assert restored_office is not None
    assert restored_office.scheme == "ABS FCB"
    assert restored_office.edition == "2021"
    assert restored_office.publisher == "Australian Bureau of Statistics"
    assert restored_office.uri == classification.uri
    assert restored.to_records() == records


def test_reconstruction_validates_duplicate_and_unknown_codes():
    duplicate_records = [
        {"code": "type", "name": "Type", "parent_code": None},
        {"code": "type", "name": "Duplicate", "parent_code": None},
    ]
    with pytest.raises(ValueError, match="duplicate"):
        Kind.from_records(duplicate_records)

    unknown_parent_records = [
        {"code": "child", "name": "Child", "parent_code": "missing"},
    ]
    with pytest.raises(ValueError, match="unknown parent"):
        Kind.from_records(unknown_parent_records)
