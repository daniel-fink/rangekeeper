import networkx as nx
import pytest

import rangekeeper as rk
from rangekeeper.graph.classification import Classification
from rangekeeper.graph.taxonomy import Taxonomy


def make_apartment_taxonomy():
    taxonomy = Taxonomy(code="project.apartment", name="Apartment Types")
    apartment = taxonomy.define(code="apartment", name="Apartment")
    three_bed = apartment.define(
        code="apartment.3bed",
        name="3-bed Apartment",
    )
    corner = three_bed.define(
        code="apartment.3bed.corner",
        name="3-bed Corner Apartment",
    )
    return taxonomy, apartment, three_bed, corner


def test_taxonomy_and_classification_modules_are_public():
    assert rk.graph.taxonomy.Taxonomy is Taxonomy
    assert rk.graph.Taxonomy is Taxonomy
    assert rk.graph.classification.Classification is Classification
    assert rk.graph.Classification is Classification
    assert not hasattr(rk.graph, "Kind")


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"code": "", "name": "Types"}, ValueError, "code"),
        ({"code": 1, "name": "Types"}, TypeError, "code"),
        ({"code": "types", "name": ""}, ValueError, "name"),
        ({"code": "types", "name": 1}, TypeError, "name"),
        (
            {"code": "types", "name": "Types", "definition": 1},
            TypeError,
            "definition",
        ),
    ],
)
def test_taxonomy_fields_are_validated(arguments, error, message):
    with pytest.raises(error, match=message):
        Taxonomy(**arguments)


def test_classifications_must_be_defined_by_a_taxonomy():
    with pytest.raises(TypeError, match="Taxonomy"):
        Classification(code="office", name="Office")


def test_taxonomy_defines_root_and_fluent_children_in_order():
    taxonomy = Taxonomy(code="project.use", name="Uses")
    use = taxonomy.define(code="use", name="Use")
    office = use.define(code="office", name="Office")
    retail = use.define(code="retail", name="Retail")

    assert taxonomy.root is use
    assert taxonomy.classifications() == (use, office, retail)
    assert use.children == (office, retail)
    assert office.parent is use
    assert retail.parent is use
    assert office.taxonomy is taxonomy


def test_taxonomy_rejects_a_second_root_and_duplicate_codes():
    taxonomy = Taxonomy(code="project.use", name="Uses")
    root = taxonomy.define(code="use", name="Use")

    with pytest.raises(ValueError, match="one root"):
        taxonomy.define(code="tenure", name="Tenure")
    with pytest.raises(ValueError, match="already contains"):
        taxonomy.define(code="use", name="Duplicate", parent=root)


def test_parent_must_belong_to_the_same_taxonomy():
    first = Taxonomy(code="first", name="First")
    second = Taxonomy(code="second", name="Second")
    first_root = first.define(code="root", name="Root")
    second.define(code="root", name="Root")

    with pytest.raises(ValueError, match="another Taxonomy"):
        second.define(code="child", name="Child", parent=first_root)


def test_traversal_lineage_and_classification_checks_delegate_to_taxonomy():
    taxonomy, apartment, three_bed, corner = make_apartment_taxonomy()
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
    assert taxonomy.classification(corner.code) is corner


def test_is_a_returns_false_across_taxonomies():
    _, first, *_ = make_apartment_taxonomy()
    second = Taxonomy(code="other", name="Other").define(
        code="apartment",
        name="Apartment",
    )

    assert not first.is_a(second)
    assert not second.is_a(first)


def test_taxonomy_and_classification_codes_are_immutable():
    taxonomy, apartment, *_ = make_apartment_taxonomy()

    with pytest.raises(AttributeError):
        taxonomy.code = "changed"
    with pytest.raises(AttributeError):
        apartment.code = "changed"
    with pytest.raises(AttributeError):
        apartment.taxonomy = Taxonomy(code="other", name="Other")


def test_taxonomy_code_scopes_classification_keys():
    taxonomy = Taxonomy(
        code="ABS FCB",
        name="Functional Classification of Buildings",
    )
    commercial = taxonomy.define(code="2", name="Commercial Buildings")
    office = commercial.define(code="231", name="Offices")

    assert office.taxonomy is taxonomy
    assert office.key == ("ABS FCB", "231")


def test_networkx_representation_is_a_frozen_arborescence():
    taxonomy, apartment, three_bed, corner = make_apartment_taxonomy()

    graph = taxonomy.to_networkx()

    assert nx.is_arborescence(graph)
    assert tuple(graph.edges()) == (
        (apartment.code, three_bed.code),
        (three_bed.code, corner.code),
    )
    with pytest.raises(nx.NetworkXError):
        graph.add_node("other")


def test_freezing_taxonomy_prevents_further_definitions():
    taxonomy, apartment, *_ = make_apartment_taxonomy()

    taxonomy.freeze()

    assert taxonomy.is_frozen
    with pytest.raises(ValueError, match="frozen"):
        apartment.define(code="other", name="Other")


def test_classification_repr_includes_taxonomy_and_code():
    _, apartment, *_ = make_apartment_taxonomy()

    assert "project.apartment" in repr(apartment)
    assert "apartment" in repr(apartment)
    assert str(apartment) == "Apartment"
