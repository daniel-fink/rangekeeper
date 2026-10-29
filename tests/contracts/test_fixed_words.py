"""Each fixed list of words that rangekeeper defines is an enum (D26, #307)."""

import importlib
from datetime import date
from enum import Enum
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.specification.rule import RuleEvidence
from tests.contracts import api

# The enum and its one public path. Words that the data or the user defines,
# such as classifications, labels and units, stay strings.
FIXED_WORDS = (
    ("rangekeeper.duration", "Frequency"),
    ("rangekeeper.specification", "Role"),
    ("rangekeeper.execution", "DecisionResult"),
    ("rangekeeper.execution", "Status"),
    ("rangekeeper.model", "Direction"),
    ("rangekeeper.errors", "Code"),
)


@pytest.mark.parametrize(("package", "name"), FIXED_WORDS)
def test_each_fixed_word_list_is_an_enum_with_one_public_path(package, name):
    owner = importlib.import_module(package)
    enum = getattr(owner, name)
    assert issubclass(enum, Enum)
    others = []
    for other in api.PACKAGES:
        module = importlib.import_module(other)
        if other != package and any(
            getattr(module, public, None) is enum
            for public in getattr(module, "__all__", ())
        ):
            others.append(other)
    assert others == []


def test_decision_result_values_are_the_recorded_words():
    assert [member.value for member in rk.execution.DecisionResult] == [
        "decided",
        "not_met",
        "skipped",
        "otherwise",
    ]
    assert rk.execution.DecisionResult("decided") is rk.execution.DecisionResult.DECIDED


def test_decision_result_of_recorded_evidence():
    def evidence(rule):
        return RuleEvidence(
            decision=uuid4(),
            at=date(2027, 1, 1),
            rule=rule,
            observations=(),
            assignments=(),
            terminated=False,
        )

    result = rk.execution.DecisionResult
    assert result.of(evidence(uuid4())) is result.DECIDED
    assert result.of(evidence(None)) is result.OTHERWISE
    with pytest.raises(TypeError):
        result.of("decided")


def test_direction_reads_both_ways_of_a_relationship():
    assert {member.value for member in rk.model.Direction} == {"outgoing", "incoming"}


def test_role_and_status_name_their_words():
    assert {member.name for member in rk.specification.Role} >= {
        "FIXED",
        "FREE",
        "DECIDED",
    }
    assert rk.execution.Status("infeasible") is rk.execution.Status.INFEASIBLE
