"""One ``rk.execution.compare`` call for two or more Outcomes (#297)."""

from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper import Specification
from rangekeeper.execution import Comparison, compare, solve
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
    assert isinstance(comparison, Comparison)
    table = comparison.values
    assert table.columns == ("key", "Back door", "Lower leverage")
    assert table.column("key") == tuple(KEYS)
    assert table.rows[0].values["Back door"] == outcomes["Back door"]["land_cost"]
    text = str(comparison)
    assert "Lower leverage" in text and "rent_factor" in text
    assert "<table" in comparison._repr_html_()
    with pytest.raises(TypeError, match="baseline"):
        comparison.summary()


def test_the_same_call_takes_more_outcomes_and_a_baseline(outcomes):
    comparison = compare(outcomes=outcomes, keys=KEYS, baseline="Back door")
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
    with pytest.raises(TypeError, match="differences"):
        _ = comparison.values
    selected = comparison.select("noi", "land_cost")
    assert selected.keys == ("noi", "land_cost")
    assert len(selected.summary().rows) == 4


def test_compare_checks_its_arguments(outcomes):
    one = {"Back door": outcomes["Back door"]}
    with pytest.raises(ValueError, match="two or more"):
        compare(outcomes=one, keys=KEYS)
    with pytest.raises(TypeError, match="list"):
        compare(outcomes=outcomes, keys="land_cost")
    with pytest.raises(KeyError, match="baseline"):
        compare(outcomes=outcomes, keys=KEYS, baseline="Front door")
    with pytest.raises(rk.errors.MissingReferenceError):
        compare(outcomes=outcomes, keys=["land_costs"])
    with pytest.raises(TypeError):
        compare(outcomes, keys=KEYS)  # type: ignore[misc]


def batch_of(*leaves):
    return Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(MODEL.id),
            "cases": [str(leaf.id) for leaf in leaves],
        }
    )


@pytest.fixture(scope="module")
def batches():
    leverages = [back().fix(leverage=q(text)) for text in ("50 %", "60 %", "70 %")]
    leverage_batch = batch_of(*leverages)
    stronger = [
        back().fix(leverage=q(text), rent_factor=q("1.1 ratio"))
        for text in ("50 %", "60 %", "70 %")
    ]
    stronger_batch = batch_of(*stronger)
    documents = store(*leverages, leverage_batch, *stronger, stronger_batch)
    return (
        solve(leverage_batch, documents),
        solve(stronger_batch, documents),
    )


def test_batches_pair_case_by_case(batches):
    reference, stronger = batches
    comparison = compare(
        outcomes={"Reference": reference, "Stronger": stronger},
        keys=["land_cost"],
        baseline="Reference",
    )
    pairs = comparison.pairs(outcome="Stronger")
    assert [pair.case for pair in pairs] == [0, 1, 2]
    for pair, case, base in zip(pairs, stronger.cases, reference.cases, strict=True):
        assert pair.member is case and pair.baseline is base
    found = comparison.difference(outcome="Stronger", key="land_cost")
    assert all(item > q("0 AUD") for item in found)
    row = comparison.summary().rows[0].values
    assert row["count"] == 3
    assert row["minimum"] <= row["mean"] <= row["maximum"]
    assert "share_above_zero" in str(comparison)
    with pytest.raises(TypeError, match="batch"):
        compare(outcomes={"Reference": reference, "Stronger": stronger}, keys=KEYS)


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
    assert [pair.case for pair in kept.pairs(outcome="Stronger")] == [0, 2]
    assert kept.summary().rows[0].values["count"] == 2
    with pytest.raises(ValueError, match="no case"):
        comparison.where(leverage=q("90 %"))


def test_different_cases_do_not_pair(batches):
    reference, _ = batches
    leaves = [back(), back()]
    two = batch_of(*leaves)
    documents = store(*leaves, two)
    with pytest.raises(ValueError, match="same cases"):
        compare(
            outcomes={"Reference": reference, "Two": solve(two, documents)},
            keys=["land_cost"],
            baseline="Reference",
        )
