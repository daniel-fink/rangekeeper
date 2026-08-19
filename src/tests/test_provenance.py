import pytest

import rangekeeper as rk


def test_provenance_is_public_and_copies_identifiers():
    supplied = {"object_id": "abc123"}

    provenance = rk.graph.Provenance(source="speckle", identifiers=supplied)
    supplied.clear()

    assert rk.graph.provenance.Provenance is rk.graph.Provenance
    assert provenance.source == "speckle"
    assert provenance.identifiers == {"object_id": "abc123"}


def test_provenance_defaults_are_isolated():
    first = rk.graph.Provenance(source="first")
    second = rk.graph.Provenance(source="second")

    first.identifiers["id"] = "1"

    assert second.identifiers == {}


@pytest.mark.parametrize("source", ["", "   ", 1])
def test_source_must_be_a_non_empty_string(source):
    with pytest.raises((TypeError, ValueError), match="source"):
        rk.graph.Provenance(source=source)


@pytest.mark.parametrize(
    "identifiers",
    [
        {"": "value"},
        {"key": ""},
        {1: "value"},
        {"key": 1},
    ],
)
def test_identifier_keys_and_values_must_be_non_empty_strings(identifiers):
    with pytest.raises((TypeError, ValueError), match="identifier"):
        rk.graph.Provenance(source="source", identifiers=identifiers)
