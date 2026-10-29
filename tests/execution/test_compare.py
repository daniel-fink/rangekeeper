"""One ``rk.execution.compare`` call for two or more Outcomes (#297)."""

from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper import Specification
from rangekeeper.errors import Code, ContractError, MissingReferenceError
from rangekeeper.execution import Paired, SideBySide, compare, solve
from tests.execution.lesson02 import MODEL, back, q, store

KEYS = ["land_cost", "rent_factor", "noi", "mortgage"]


@pytest.fixture(scope="module")
def outcomes():
    return {
        "Back door": solve(specification=back()),
        "Lower leverage": solve(specification=back().fix(leverage=q("50 %"))),
        "Stronger market": solve(specification=back().fix(rent_factor=q("1.1 ratio"))),
    }


def test_without_a_baseline_the_values_are_side_by_side(outcomes):
    two = {name: outcomes[name] for name in ("Back door", "Lower leverage")}
    comparison = rk.execution.compare(outcomes=two, keys=KEYS)
    assert isinstance(comparison, SideBySide)
    table = comparison.values
    assert table.columns == ("key", "Back door", "Lower leverage")
    assert table.column("key") == tuple(KEYS)
    assert table.rows[0].values["Back door"] == outcomes["Back door"]["land_cost"]
    text = str(comparison)
    assert "Lower leverage" in text and "rent_factor" in text
    assert "<table" in comparison._repr_html_()
    # Differences need a baseline: a side-by-side comparison has none.
    assert not hasattr(comparison, "summary")
    assert comparison.select("noi").keys == ("noi",)


def test_the_same_call_takes_more_outcomes_and_a_baseline(outcomes):
    comparison = compare(outcomes=outcomes, keys=KEYS, baseline="Back door")
    assert isinstance(comparison, Paired)
    assert comparison.compared == ("Lower leverage", "Stronger market")
    (difference,) = comparison.difference(outcome="Lower leverage", key="land_cost")
    assert difference == (
        outcomes["Lower leverage"]["land_cost"] - outcomes["Back door"]["land_cost"]
    )
    assert difference > q("0 AUD")
    differences = comparison.differences
    assert len(differences.rows) == 2 * len(KEYS)
    assert set(differences.column("case")) == {None}
    summary = comparison.summary()
    row = summary.rows[0].values
    assert (row["outcome"], row["key"], row["count"]) == (
        "Lower leverage",
        "land_cost",
        1,
    )
    assert row["mean"] == row["minimum"] == row["maximum"] == difference
    assert row["share_above_zero"] == 1.0
    assert "Lower leverage − Back door" in str(comparison)
    assert not hasattr(comparison, "values")
    selected = comparison.select("noi", "land_cost")
    assert selected.keys == ("noi", "land_cost")
    assert len(selected.summary().rows) == 4


def test_compare_checks_its_arguments(outcomes):
    one = {"Back door": outcomes["Back door"]}
    with pytest.raises(ContractError, match="two or more"):
        compare(outcomes=one, keys=KEYS)
    with pytest.raises(TypeError, match="list"):
        compare(outcomes=outcomes, keys="land_cost")
    with pytest.raises(MissingReferenceError) as missing:
        compare(outcomes=outcomes, keys=KEYS, baseline="Front door")
    assert (missing.value.kind, missing.value.by) == ("Outcome", "name")
    assert "Back door" in missing.value.candidates
    with pytest.raises(MissingReferenceError):
        compare(outcomes=outcomes, keys=["land_costs"])
    with pytest.raises(TypeError):
        compare(outcomes, keys=KEYS)  # type: ignore[misc]
    comparison = compare(outcomes=outcomes, keys=KEYS, baseline="Back door")
    with pytest.raises(MissingReferenceError) as missing:
        comparison.difference(outcome="Lower leverage", key="noi_x")
    assert missing.value.candidates == tuple(KEYS)
    with pytest.raises(MissingReferenceError):
        comparison.pairs(outcome="Back door")


def batch_of(*leaves):
    return Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(MODEL.id),
            "cases": [str(leaf.id) for leaf in leaves],
        }
    )


LEVERAGES = {text: {"leverage": q(f"{text} %")} for text in ("50", "60", "70")}


@pytest.fixture(scope="module")
def batches():
    stronger = back().fix(rent_factor=q("1.1 ratio"))
    return (
        solve(specification=back().cases(cases=LEVERAGES)),
        solve(specification=stronger.cases(cases=LEVERAGES)),
    )


def test_batches_pair_case_by_case(batches):
    reference, stronger = batches
    comparison = compare(
        outcomes={"Reference": reference, "Stronger": stronger},
        keys=["land_cost"],
        baseline="Reference",
    )
    pairs = comparison.pairs(outcome="Stronger")
    # The pairs carry the case keys, as Outcome.table names the cases.
    assert [pair.case for pair in pairs] == ["50", "60", "70"]
    for pair, case, base in zip(pairs, stronger.cases, reference.cases, strict=True):
        assert pair.member is case and pair.baseline is base
    found = comparison.difference(outcome="Stronger", key="land_cost")
    assert all(item > q("0 AUD") for item in found)
    row = comparison.summary().rows[0].values
    assert row["count"] == 3
    assert row["minimum"] <= row["mean"] <= row["maximum"]
    assert "share_above_zero" in str(comparison)
    with pytest.raises(ContractError, match="batch") as raised:
        compare(outcomes={"Reference": reference, "Stronger": stronger}, keys=KEYS)
    assert raised.value.code is Code.COMPARISON_BATCH


def test_a_leaf_pairs_with_each_case_of_a_batch(batches):
    reference, _ = batches
    comparison = compare(
        outcomes={"Leaf": solve(specification=back()), "Batch": reference},
        keys=["land_cost"],
        baseline="Leaf",
    )
    assert len(comparison.difference(outcome="Batch", key="land_cost")) == 3


def test_where_keeps_the_pairs_with_these_values(batches):
    reference, stronger = batches
    comparison = compare(
        outcomes={"Reference": reference, "Stronger": stronger},
        keys=["land_cost"],
        baseline="Reference",
    )
    kept = comparison.where(leverage=[q("50 %"), q("70 %")])
    assert [pair.case for pair in kept.pairs(outcome="Stronger")] == ["50", "70"]
    assert kept.summary().rows[0].values["count"] == 2
    with pytest.raises(ContractError, match="no case") as raised:
        comparison.where(leverage=q("90 %"))
    assert raised.value.code is Code.COMPARISON_EMPTY


def test_different_cases_do_not_pair(batches):
    reference, _ = batches
    two = {text: LEVERAGES[text] for text in ("50", "60")}
    with pytest.raises(ContractError, match="same case") as raised:
        compare(
            outcomes={
                "Reference": reference,
                "Two": solve(specification=back().cases(cases=two)),
            },
            keys=["land_cost"],
            baseline="Reference",
        )
    assert raised.value.code is Code.COMPARISON_CASES
    assert raised.value.values["missing"] == ["70"]


def test_cases_that_share_a_key_do_not_pair():
    # Two hand-made cases of one Specification have its name as their key.
    leaves = [back(), back()]
    two = batch_of(*leaves)
    outcome = solve(specification=two, resolver=store(*leaves, two))
    assert [case.key for case in outcome.cases] == [leaves[0].metadata.name] * 2
    with pytest.raises(ContractError, match="unique key") as raised:
        compare(
            outcomes={"One": outcome, "Other": outcome},
            keys=["land_cost"],
            baseline="One",
        )
    assert raised.value.code is Code.COMPARISON_CASES
    assert raised.value.values["repeated"] == [leaves[0].metadata.name]


def test_batches_pair_by_case_key_not_by_position():
    base = back()
    levers = {"low": {"leverage": q("50 %")}, "high": {"leverage": q("70 %")}}
    flipped = {"high": {"leverage": q("70 %")}, "low": {"leverage": q("50 %")}}
    reference = solve(specification=base.cases(cases=levers))
    reordered = solve(specification=base.cases(cases=flipped))
    comparison = compare(
        outcomes={"Reference": reference, "Reordered": reordered},
        keys=["land_cost"],
        baseline="Reference",
    )
    pairs = comparison.pairs(outcome="Reordered")
    assert [pair.case for pair in pairs] == ["high", "low"]
    assert all(pair.member.key == pair.baseline.key for pair in pairs)
    assert comparison.difference(outcome="Reordered", key="land_cost") == (
        q("0 AUD"),
        q("0 AUD"),
    )


def test_batches_of_equal_size_with_other_case_keys_do_not_pair():
    base = back()
    levers = {"low": {"leverage": q("50 %")}, "high": {"leverage": q("70 %")}}
    other = {"weak": {"leverage": q("50 %")}, "strong": {"leverage": q("70 %")}}
    with pytest.raises(ContractError) as raised:
        compare(
            outcomes={
                "Reference": solve(specification=base.cases(cases=levers)),
                "Other": solve(specification=base.cases(cases=other)),
            },
            keys=["land_cost"],
            baseline="Reference",
        )
    assert raised.value.code is Code.COMPARISON_CASES
    assert raised.value.values["missing"] == ["high", "low"]
    assert raised.value.values["extra"] == ["strong", "weak"]
