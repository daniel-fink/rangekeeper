"""The public API matches its reviewed snapshot (ADR-017)."""

import difflib
import importlib

import pytest

from tests.contracts import api


def test_public_api_matches_the_snapshot():
    expected = api.SNAPSHOT.read_text()
    actual = api.render(api.snapshot())
    difference = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            "api.json",
            "current",
            n=1,
        )
    )
    assert not difference, (
        "The public API changed. Review the difference, then run "
        "`uv run python -m tests.contracts.api --write`.\n" + difference[:4000]
    )


@pytest.mark.parametrize("name", api.PACKAGES)
def test_each_public_package_declares_its_names(name):
    module = importlib.import_module(name)
    if hasattr(module, "__path__"):
        assert isinstance(module.__all__, list), name
    for public in getattr(module, "__all__", ()):
        assert hasattr(module, public), (name, public)


def test_internal_packages_are_not_public():
    import rangekeeper

    assert {"schema", "shared"}.isdisjoint(rangekeeper.__all__)
    assert rangekeeper.schema.__name__ == "rangekeeper.schema"
