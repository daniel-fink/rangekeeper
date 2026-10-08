from uuid import uuid4

import pytest

from rangekeeper.shared import arguments


def test_is_text_accepts_strings_and_optionally_rejects_empty_text():
    assert arguments.is_text("Apartment 27.05")
    assert arguments.is_text("")
    assert arguments.is_text("   ")
    assert not arguments.is_text("", empty=False)
    assert not arguments.is_text("   ", empty=False)


def test_is_text_rejects_non_strings_without_restricting_characters():
    assert not arguments.is_text(None)
    assert not arguments.is_text(27)
    assert arguments.is_text("area.nsa.internal", empty=False)
    assert arguments.is_text("A302:L302", empty=False)


def test_require_uuid_returns_uuids_and_reports_the_field():
    identifier = uuid4()

    assert arguments.require_uuid(identifier, "Taxonomy.id") is identifier
    with pytest.raises(TypeError, match="Taxonomy.id must be a UUID"):
        arguments.require_uuid("not-a-uuid", "Taxonomy.id")


def test_require_text_rejects_non_strings_and_empty_text():
    assert arguments.require_text("Apartment", "Classification.name") == "Apartment"
    with pytest.raises(TypeError, match="Classification.name must be a string"):
        arguments.require_text(None, "Classification.name")
    with pytest.raises(ValueError, match="Classification.name must not be empty"):
        arguments.require_text("  ", "Classification.name")


def test_optional_text_supports_none_and_an_explicit_empty_policy():
    assert arguments.optional_text(None, "definition") is None
    assert arguments.optional_text("", "definition") == ""
    assert arguments.optional_text("Notes", "definition") == "Notes"
    with pytest.raises(TypeError, match="definition must be a string or None"):
        arguments.optional_text(42, "definition")
    with pytest.raises(ValueError, match="Method.version must not be empty"):
        arguments.optional_text(" ", "Method.version", empty=False)
