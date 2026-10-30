"""Distributions of a batch Outcome's values, and the mean of a batch (#296)."""

import math
import statistics
from datetime import date
from fractions import Fraction

import pytest

import rangekeeper as rk
from rangekeeper.errors import Code, ContractError, UnitError
from rangekeeper.execution import (
    DateDistribution,
    Distribution,
    Mean,
    OutcomeError,
    Paired,
    SideBySide,
    compare,
    solve,
)
from tests.execution.lesson02 import back, q
from tests.execution.test_outcome_cases import batch_outcome
from tests.execution.test_temporal_execution import investigate, oracle

pytest.importorskip("pyomo")
pytest.importorskip("highspy")

NEVER = rk.duration.NEVER
# Two cases have the same leverage, so their land costs are equal.
LEVERAGES = {
    "40": {"leverage": q("40 %")},
    "50": {"leverage": q("50 %")},
    "60": {"leverage": q("60 %")},
    "70": {"leverage": q("70 %")},
    "50 again": {"leverage": q("50 %")},
}
LEVELS = (0, 0.05, 0.2, 0.21, 0.4, 0.5, 0.6, 0.8, 0.95, 1)


@pytest.fixture(scope="module")
def batch():
    return solve(specification=back().cases(cases=LEVERAGES)).raise_for_status()


@pytest.fixture(scope="module")
def leaf():
    return solve(specification=back()).raise_for_status()


def land_costs(batch) -> list[rk.Quantity]:
    return list(batch.table("land_cost").column("land_cost"))


def test_a_distribution_holds_the_value_of_each_case(batch):
    npv = batch.distribution(key="land_cost")
    assert isinstance(npv, Distribution)
    assert (npv.key, npv.units) == ("land_cost", "AUD")
    assert list(npv.values) == land_costs(batch)
    assert repr(npv) == "Distribution(key='land_cost', units='AUD', count=5)"


def test_the_mean_and_the_standard_deviation_weigh_each_case_equally(batch):
    numbers = [value.number for value in land_costs(batch)]
    found = batch.distribution(key="land_cost")
    assert found.mean().units == "AUD"
    assert math.isclose(found.mean().number, statistics.fmean(numbers), rel_tol=1e-12)
    assert math.isclose(
        found.standard_deviation().number, statistics.pstdev(numbers), rel_tol=1e-12
    )


def test_a_quantile_is_the_value_of_one_case(batch):
    """The smallest value whose share of cases at or below it is at least the level."""
    found = batch.distribution(key="land_cost")
    ordered = sorted(land_costs(batch))
    for level in LEVELS:
        share = Fraction(str(level))
        expected = next(
            value
            for count, value in enumerate(ordered, start=1)
            if Fraction(count, len(ordered)) >= share
        )
        assert found.quantile(level=level) == expected
        assert found.case(quantile=level)["land_cost"] == expected
    assert found.quantile(level=0) == ordered[0]
    assert found.quantile(level=1) == ordered[-1]


def test_the_case_at_a_quantile_is_the_first_of_equal_values(batch):
    found = batch.distribution(key="land_cost")
    # In ascending order the land costs of "50" and "50 again" are the third
    # and fourth values: levels 0.6 and 0.8 both give "50".
    assert found.case(quantile=0.6) is batch.case(key="50")
    assert found.case(quantile=0.8) is batch.case(key="50")
    assert found.case(quantile=1) is batch.case(key="40")


def test_probability_is_the_share_of_cases_beyond_strict_bounds(batch):
    found = batch.distribution(key="land_cost")
    values = land_costs(batch)
    middle = sorted(values)[2]
    assert found.probability(below=middle) == 2 / 5
    assert found.probability(above=middle) == 1 / 5
    assert found.probability(below="1e12 AUD") == 1.0
    assert found.probability(above="1e12 AUD") == 0.0
    lowest, highest = min(values), max(values)
    assert found.probability(above=lowest, below=highest) == 3 / 5
    assert found.probability(above=highest, below=lowest) == 0.0
    # A bound converts to the units of the values.
    leverage = batch.distribution(key="leverage")
    assert leverage.probability(below="55 %") == 3 / 5
    assert leverage.probability(above=q("0.55 ratio")) == 2 / 5


def test_counts_give_each_distinct_value_in_order(batch):
    counts = batch.distribution(key="land_cost").counts()
    assert counts.columns == ("value", "count", "share")
    values = counts.column("value")
    assert list(values) == sorted(values)
    assert counts.column("count") == (1, 1, 2, 1)
    assert counts.column("share") == (0.2, 0.2, 0.4, 0.2)
    assert counts.rows[2].values["value"] == batch.case(key="50")["land_cost"]


def test_the_summary_is_one_row_of_statistics(batch):
    found = batch.distribution(key="land_cost")
    summary = found.summary()
    assert summary.columns == (
        "key",
        "count",
        "mean",
        "standard_deviation",
        "minimum",
        "quantile_05",
        "quantile_95",
        "maximum",
    )
    (row,) = summary.rows
    assert row.values["key"] == "land_cost"
    assert row.values["count"] == 5
    assert row.values["mean"] == found.mean()
    assert row.values["standard_deviation"] == found.standard_deviation()
    assert row.values["minimum"] == min(found.values)
    assert row.values["quantile_05"] == found.quantile(level=0.05)
    assert row.values["quantile_95"] == found.quantile(level=0.95)
    assert row.values["maximum"] == max(found.values)
    html = found._repr_html_()
    assert "<table" in html and "mean [AUD]" in html


def test_a_distribution_checks_its_arguments(batch):
    found = batch.distribution(key="land_cost")
    with pytest.raises(TypeError, match="below=, above="):
        found.probability()
    for level in (-0.1, 1.5, math.nan):
        with pytest.raises(ContractError) as raised:
            found.quantile(level=level)
        assert raised.value.code is Code.CONTRACT
    for level in (True, "5 %"):
        with pytest.raises(TypeError):
            found.case(quantile=level)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        found.probability(below=0)  # type: ignore[arg-type]
    with pytest.raises(UnitError):
        found.probability(below="1 sqm")


def test_a_leaf_outcome_has_no_distribution(leaf):
    for read in (lambda: leaf.distribution(key="land_cost"), leaf.mean):
        with pytest.raises(ContractError, match="cases of a batch") as raised:
            read()
        assert raised.value.code is Code.BATCH_REQUIRED
    with pytest.raises(ContractError) as raised:
        leaf.case(key="50")
    assert raised.value.code is Code.BATCH_REQUIRED


def test_a_flow_value_has_no_distribution():
    _, outcome = batch_outcome()
    assert isinstance(outcome.distribution(key="pv"), Distribution)
    with pytest.raises(ContractError, match="scalar or a date") as raised:
        outcome.distribution(key="cash")
    assert raised.value.code is Code.DISTRIBUTION_VALUE
    assert raised.value.values == {"key": "cash"}


def test_a_case_without_an_output_raises_its_error():
    model, ids = oracle()
    batch = investigate(model, ids).cases(
        cases={"fixed": {}, "conflict": {"pv": "1 AUD"}}
    )
    outcome = solve(specification=batch)
    with pytest.raises(OutcomeError):
        outcome.distribution(key="pv")


def test_the_mean_of_a_batch_compares_as_one_leaf(batch, leaf):
    mean = batch.mean()
    assert isinstance(mean, Mean)
    assert mean.outcome is batch
    assert mean["land_cost"] == batch.distribution(key="land_cost").mean()
    assert repr(mean) == f"Mean(outcome={batch.key!r})"
    paired = compare(
        outcomes={"Leaf": leaf, "Mean": mean},
        keys=["land_cost", "noi"],
        baseline="Leaf",
    )
    assert isinstance(paired, Paired)
    (pair,) = paired.pairs(outcome="Mean")
    assert pair.case is None and pair.member is mean
    (difference,) = paired.difference(outcome="Mean", key="land_cost")
    assert difference == mean["land_cost"] - leaf["land_cost"]
    assert "Mean − Leaf" in str(paired)
    side = compare(outcomes={"Leaf": leaf, "Mean": mean}, keys=["land_cost"])
    assert isinstance(side, SideBySide)
    assert side.values.rows[0].values["Mean"] == mean["land_cost"]
    # A Mean baseline pairs with each case of a batch.
    each = compare(
        outcomes={"Mean": mean, "Cases": batch}, keys=["land_cost"], baseline="Mean"
    )
    assert [pair.case for pair in each.pairs(outcome="Cases")] == list(LEVERAGES)
    with pytest.raises(TypeError, match="Mean of one"):
        compare(outcomes={"Leaf": leaf, "Other": 1}, keys=["land_cost"])  # type: ignore[dict-item]


@pytest.fixture(scope="module")
def dates():
    draft = rk.Model(name="Dates").edit()
    project = draft.add_entity(code="project", classification="project")
    project.date(key="b_start")
    project.date(key="b_open")
    project.equations("b_open = b_start + 1 year")
    specification = draft.commit().specify(name="Dates")
    cases = {
        "late": {"b_start": date(2031, 1, 1)},
        "never": {"b_start": NEVER},
        "early": {"b_start": date(2029, 1, 1)},
        "early again": {"b_start": date(2029, 1, 1)},
    }
    return solve(specification=specification.cases(cases=cases)).raise_for_status()


def test_a_date_value_has_counts_with_never_last(dates):
    found = dates.distribution(key="b_open")
    assert isinstance(found, DateDistribution)
    assert found.key == "b_open"
    assert found.values == (date(2032, 1, 1), NEVER, date(2030, 1, 1), date(2030, 1, 1))
    counts = found.counts()
    assert counts.column("value") == (date(2030, 1, 1), date(2032, 1, 1), NEVER)
    assert counts.column("count") == (2, 1, 1)
    assert counts.column("share") == (0.5, 0.25, 0.25)
    assert "<table" in found._repr_html_()
    assert repr(found) == "DateDistribution(key='b_open', count=4)"
    with pytest.raises(ContractError, match="no mean") as raised:
        dates.mean()["b_open"]
    assert raised.value.code is Code.DISTRIBUTION_VALUE
