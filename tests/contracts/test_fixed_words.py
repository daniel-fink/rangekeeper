"""Each fixed list of words that rangekeeper defines is an enum (D26, #307, #390)."""

import importlib
from enum import Enum, StrEnum

import pytest

import rangekeeper as rk
from tests.contracts import api


def public_enums() -> dict[type[Enum], tuple[str, ...]]:
    """Return each public enum with the public packages that export it."""
    found: dict[type[Enum], tuple[str, ...]] = {}
    for package in api.PACKAGES:
        module = importlib.import_module(package)
        for name in getattr(module, "__all__", ()):
            value = getattr(module, name, None)
            if isinstance(value, type) and issubclass(value, Enum):
                found[value] = (*found.get(value, ()), package)
    return found


# Words that the data or the user defines, such as classifications, labels and
# units, stay strings. Each fixed word list is a public enum.
PUBLIC = public_enums()
FIXED_WORDS = (
    ("rangekeeper.duration", "Frequency"),
    ("rangekeeper.specification", "Role"),
    ("rangekeeper.execution", "DecisionResult"),
    ("rangekeeper.execution", "Status"),
    ("rangekeeper.model", "Direction"),
    ("rangekeeper.errors", "Code"),
)


@pytest.mark.parametrize(("package", "name"), FIXED_WORDS)
def test_the_fixed_word_lists_are_public_enums(package: str, name: str) -> None:
    enum = getattr(importlib.import_module(package), name)
    assert PUBLIC[enum] == (package,)


@pytest.mark.parametrize("enum", sorted(PUBLIC, key=lambda e: e.__name__), ids=str)
def test_each_public_enum_is_a_str_enum_with_one_public_path(
    enum: type[Enum],
) -> None:
    # A member is its word: it equals the word, and str() gives the word.
    assert issubclass(enum, StrEnum)
    assert all(member == member.value == str(member) for member in enum)
    assert len(PUBLIC[enum]) == 1, PUBLIC[enum]
    assert (enum.__doc__ or "").strip(), "the API reference shows a docstring"


def test_a_generated_enum_equals_its_word() -> None:
    assert rk.model.Direction.INCOMING == "incoming"
    assert rk.execution.Status.INFEASIBLE == "infeasible"
    assert rk.model.ValueRelation("less_than") is rk.model.ValueRelation.LESS_THAN


def test_decision_result_values_are_the_recorded_words():
    assert [member.value for member in rk.execution.DecisionResult] == [
        "decided",
        "not_met",
        "skipped",
        "otherwise",
    ]
    assert rk.execution.DecisionResult("decided") is rk.execution.DecisionResult.DECIDED


def test_direction_reads_both_ways_of_a_relationship():
    assert {member.value for member in rk.model.Direction} == {"outgoing", "incoming"}


def test_role_and_status_name_their_words():
    assert {member.name for member in rk.specification.Role} >= {
        "FIXED",
        "FREE",
        "DECIDED",
    }
    assert rk.execution.Status("infeasible") is rk.execution.Status.INFEASIBLE
