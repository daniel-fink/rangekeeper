import pytest

import rangekeeper as rk


def classification():
    return rk.graph.Taxonomy(
        code="project.relationship", name="Relationship Types"
    ).define(code="relationship.connected_to", name="Connected To")


def test_relationship_is_public_and_preserves_domain_fields():
    kind = classification()
    characteristics = rk.graph.Characteristics(features={"capacity": 10})
    provenance = rk.graph.Provenance(source="survey")

    relationship = rk.graph.Relationship(
        "source",
        "target",
        kind,
        relationship_id="relationship",
        characteristics=characteristics,
        provenance=provenance,
    )

    assert rk.graph.relationship.Relationship is rk.graph.Relationship
    assert relationship.relationship_id == "relationship"
    assert relationship.source_id == "source"
    assert relationship.target_id == "target"
    assert relationship.classification is kind
    assert relationship.characteristics is characteristics
    assert relationship.provenance is provenance


def test_relationship_id_and_structural_fields_are_immutable():
    relationship = rk.graph.Relationship("source", "target", classification())

    assert relationship.relationship_id
    for field, replacement in (
        ("relationship_id", "changed"),
        ("source_id", "changed"),
        ("target_id", "changed"),
        ("classification", classification()),
    ):
        with pytest.raises(AttributeError):
            setattr(relationship, field, replacement)


def test_relationship_identity_equality_hashing_and_unrelated_comparison():
    kind = classification()
    first = rk.graph.Relationship("a", "b", kind, relationship_id="same")
    reconstructed = rk.graph.Relationship(
        "different", "endpoints", kind, relationship_id="same"
    )

    assert first == reconstructed
    assert hash(first) == hash(reconstructed)
    assert first.__eq__(object()) is NotImplemented
    assert first != object()


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("source_id", ("", " ", 1)),
        ("target_id", ("", " ", 1)),
        ("relationship_id", ("", " ", 1)),
    ],
)
def test_relationship_ids_are_non_empty_strings(field, values):
    for value in values:
        arguments = {
            "source_id": "source",
            "target_id": "target",
            "classification": classification(),
            "relationship_id": "relationship",
        }
        arguments[field] = value
        with pytest.raises((TypeError, ValueError), match=field):
            rk.graph.Relationship(**arguments)


def test_relationship_classification_is_required_and_validated():
    with pytest.raises(TypeError, match="classification"):
        rk.graph.Relationship("source", "target", None)


def test_relationship_characteristics_and_provenance_are_validated():
    with pytest.raises(TypeError, match="characteristics"):
        rk.graph.Relationship("source", "target", classification(), characteristics={})
    with pytest.raises(TypeError, match="provenance"):
        rk.graph.Relationship("source", "target", classification(), provenance="source")


def test_relationship_characteristics_defaults_are_isolated():
    first = rk.graph.Relationship("a", "b", classification())
    second = rk.graph.Relationship("a", "b", classification())

    first.characteristics.features["capacity"] = 10

    assert second.characteristics.features == {}
