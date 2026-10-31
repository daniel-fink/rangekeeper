"""One ``rk.execution.compare`` call for two or more Outcomes (#297)."""

from datetime import date
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper import Specification
from rangekeeper.errors import Code, ContractError, MissingReferenceError
from rangekeeper.execution import (
    Distribution,
    Groups,
    Pair,
    Paired,
    SideBySide,
    compare,
    solve,
)
from rangekeeper.market import Paths
from tests.execution.lesson02 import MODEL, back, q, store
from tests.execution.test_outcome_cases import batch_outcome

SUMMARY = (
    "key",
    "count",
    "mean",
    "standard_deviation",
    "minimum",
    "quantile_05",
    "quantile_95",
    "maximum",
    "share_above_zero",
)

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


def test_the_differences_of_one_outcome_have_a_distribution(batches):
    reference, stronger = batches
    comparison = compare(
        outcomes={"Reference": reference, "Stronger": stronger},
        keys=["land_cost", "noi"],
        baseline="Reference",
    )
    found = comparison.distribution(outcome="Stronger", key="land_cost")
    assert isinstance(found, Distribution)
    assert found.values == comparison.difference(outcome="Stronger", key="land_cost")
    assert found.units == "AUD"
    # The case at a quantile is the Pair whose difference is there.
    lowest = found.case(quantile=0)
    assert isinstance(lowest, Pair)
    assert lowest.member["land_cost"] - lowest.baseline["land_cost"] == min(
        found.values
    )
    with pytest.raises(MissingReferenceError):
        comparison.distribution(outcome="Stronger", key="mortgage")
    with pytest.raises(MissingReferenceError):
        comparison.distribution(outcome="Reference", key="land_cost")


def test_the_summary_has_the_statistics_of_each_distribution(batches):
    reference, stronger = batches
    comparison = compare(
        outcomes={"Reference": reference, "Stronger": stronger},
        keys=["land_cost", "noi"],
        baseline="Reference",
    )
    summary = comparison.summary()
    assert summary.columns == ("outcome", *SUMMARY)
    for row in summary.rows:
        found = comparison.distribution(outcome="Stronger", key=row.values["key"])
        (statistics,) = found.summary().rows
        assert row.values["outcome"] == "Stronger"
        for column in statistics.values:
            assert row.values[column] == statistics.values[column]
        zero = q(f"0 {found.units}")
        assert row.values["share_above_zero"] == found.probability(above=zero)


def test_by_groups_the_pairs_by_a_value_of_the_member(batches):
    reference, stronger = batches
    comparison = compare(
        outcomes={"Reference": reference, "Stronger": stronger},
        keys=["land_cost"],
        baseline="Reference",
    )
    groups = comparison.by(key="leverage")
    assert isinstance(groups, Groups)
    assert (groups.column, groups.paired) == ("leverage", comparison)
    summary = groups.summary()
    assert summary.columns == ("outcome", "leverage", *SUMMARY)
    assert summary.column("leverage") == tuple(
        q(f"{text} %").to(units="ratio") for text in ("50", "60", "70")
    )
    assert summary.column("count") == (1, 1, 1)
    differences = comparison.difference(outcome="Stronger", key="land_cost")
    assert summary.column("mean") == differences
    # The back door's NOI does not depend on the leverage: one group.
    (row,) = comparison.by(key="noi").summary().rows
    assert row.values["count"] == 3
    assert row.values["noi"] == stronger.case(key="50")["noi"]
    assert "<table" in groups._repr_html_()
    assert repr(groups) == "Groups(column='leverage', groups=3)"


def test_a_flow_value_does_not_group_pairs():
    _, outcome = batch_outcome()
    comparison = compare(
        outcomes={"One": outcome, "Other": outcome}, keys=["pv"], baseline="One"
    )
    with pytest.raises(ContractError, match="scalar or a date") as raised:
        comparison.by(key="cash")
    assert raised.value.code is Code.COMPARISON_SCALAR


@pytest.fixture(scope="module")
def dated():
    """Return a batch whose cases start on dates, or never, and a leaf at no cost."""
    draft = rk.Model(name="Dates").edit()
    project = draft.add_entity(code="project", classification="project")
    project.date(key="start")
    project.value(key="cost", units="AUD")
    plan = draft.commit().specify(name="Dates")
    cases = {
        "late": {"start": date(2031, 1, 1), "cost": q("3 AUD")},
        "never": {"start": rk.duration.NEVER, "cost": q("1 AUD")},
        "early": {"start": date(2029, 1, 1), "cost": q("2 AUD")},
        "early again": {"start": date(2029, 1, 1), "cost": q("4 AUD")},
    }
    leaf = plan.fix(start=date(2029, 1, 1), cost=q("0 AUD"))
    return (
        solve(specification=plan.cases(cases=cases)).raise_for_status(),
        solve(specification=leaf).raise_for_status(),
    )


def test_by_a_date_puts_never_after_every_date(dated):
    batch, leaf = dated
    comparison = compare(
        outcomes={"Plan": leaf, "Cases": batch}, keys=["cost"], baseline="Plan"
    )
    summary = comparison.by(key="start").summary()
    assert summary.column("start") == (
        date(2029, 1, 1),
        date(2031, 1, 1),
        rk.duration.NEVER,
    )
    assert summary.column("count") == (2, 1, 1)
    assert summary.column("mean") == (q("3 AUD"), q("3 AUD"), q("1 AUD"))
    # The groups keep the pairs of equal values in case order.
    kept = comparison.where(start=date(2029, 1, 1))
    assert [pair.case for pair in kept.pairs(outcome="Cases")] == [
        "early",
        "early again",
    ]


def test_by_case_groups_the_pairs_of_each_case(batches):
    reference, stronger = batches
    comparison = compare(
        outcomes={"Reference": reference, "Stronger": stronger},
        keys=["land_cost"],
        baseline="Reference",
    )
    groups = comparison.by_case
    assert groups.column == "case"
    summary = groups.summary()
    assert summary.columns == ("outcome", "case", *SUMMARY)
    assert summary.column("case") == ("50", "60", "70")
    assert summary.column("mean") == comparison.difference(
        outcome="Stronger", key="land_cost"
    )
    # A leaf Outcome, or the Mean of a batch, is one group.
    leaf = solve(specification=back())
    one = compare(
        outcomes={"Batch": reference, "Leaf": leaf, "Mean": stronger.mean()},
        keys=["land_cost"],
        baseline="Batch",
    ).by_case.summary()
    assert one.column("outcome") == ("Leaf", "Mean")
    assert one.column("case") == (leaf.key, None)
    assert one.column("count") == (3, 3)


def test_by_case_groups_the_leaves_of_each_direct_case():
    weak_and_strong = back().cases(
        cases={"Weak": {"rent_factor": q("0.9 ratio")}, "Strong": {}}
    )
    two = {text: LEVERAGES[text] for text in ("50", "60")}
    batches = [
        weak_and_strong.case(key=key).cases(cases=two) for key in ("Weak", "Strong")
    ]
    leaves = [batch.case(key=key) for batch in batches for key in two]
    nested = batch_of(*batches)
    outcome = solve(
        specification=nested, resolver=store(*leaves, *batches, nested)
    ).raise_for_status()
    leaf = solve(specification=back()).raise_for_status()
    comparison = compare(
        outcomes={"Leaf": leaf, "Nested": outcome}, keys=["land_cost"], baseline="Leaf"
    )
    pairs = comparison.pairs(outcome="Nested")
    assert [pair.case for pair in pairs] == [
        "Weak/50",
        "Weak/60",
        "Strong/50",
        "Strong/60",
    ]
    summary = comparison.by_case.summary()
    assert summary.column("case") == ("Weak", "Strong")
    assert summary.column("count") == (2, 2)
    weak = comparison.difference(outcome="Nested", key="land_cost")[:2]
    assert summary.rows[0].values["minimum"] == min(weak)


YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def market(*, up: tuple[float, ...] = (1, 1.1, 1.2)) -> Paths:
    """Return two market paths of a rent index, ``up`` and ``down``."""

    def index(*magnitudes: float) -> rk.flow.Flow:
        return rk.flow.Flow.from_periods(
            periods=YEARS, magnitudes=magnitudes, units="ratio"
        )

    return Paths.from_flows(
        flows={
            "up": {"rent_index": index(*up)},
            "down": {"rent_index": index(1, 0.9, 0.8)},
        }
    )


@pytest.fixture(scope="module")
def priced() -> rk.Model:
    """Return a Model whose worth is a price times the total of a rent index."""
    draft = rk.Model(name="Priced").edit()
    project = draft.add_entity(code="project", classification="project")
    project.flow(key="rent_index", units="ratio", periods=YEARS)
    project.value(key="price", units="AUD")
    project.value(key="worth", units="AUD")
    project.equations("worth = price * rent_index.total()")
    return draft.commit()


def test_batches_across_the_same_paths_pair_by_path(priced):
    paths = market()
    low = solve(
        specification=priced.specify(name="Low")
        .fix(price="100 AUD")
        .across(paths=paths)
    ).raise_for_status()
    high = solve(
        specification=priced.specify(name="High")
        .fix(price="120 AUD")
        .across(paths=paths)
    ).raise_for_status()
    comparison = compare(
        outcomes={"Low": low, "High": high}, keys=["worth"], baseline="Low"
    )
    pairs = comparison.pairs(outcome="High")
    assert [pair.case for pair in pairs] == ["up", "down"]
    assert all(pair.member.run.paths == pair.baseline.run.paths for pair in pairs)
    assert comparison.difference(outcome="High", key="worth") == (
        q("66 AUD"),
        q("54 AUD"),
    )
    # Other Paths with the same path keys do not pair.
    other = solve(
        specification=priced.specify(name="Other")
        .fix(price="120 AUD")
        .across(paths=market(up=(1, 1.2, 1.4)))
    ).raise_for_status()
    with pytest.raises(ContractError, match="other Paths") as raised:
        compare(outcomes={"Low": low, "Other": other}, keys=["worth"], baseline="Low")
    assert raised.value.code is Code.COMPARISON_PATHS
    assert raised.value.values["paths"] != raised.value.values["baseline_paths"]


def test_cases_each_across_the_paths_pair_with_one_batch_by_path(priced):
    """A batch of cases, each across the same paths, pairs path by path."""
    paths = market()
    prices = priced.specify(name="Prices").cases(
        cases={"110": {"price": "110 AUD"}, "130": {"price": "130 AUD"}}
    )
    nested = prices.across(paths=paths)
    outcome = solve(specification=nested).raise_for_status()
    assert [case.key for case in outcome.cases] == ["110", "130"]
    assert {leaf.run.path_key for case in outcome.cases for leaf in case.cases} == {
        "up",
        "down",
    }
    assert outcome.run.path_key is None
    low = solve(
        specification=priced.specify(name="Low")
        .fix(price="100 AUD")
        .across(paths=paths)
    ).raise_for_status()
    comparison = compare(
        outcomes={"Prices": outcome, "Low": low}, keys=["worth"], baseline="Low"
    )
    pairs = comparison.pairs(outcome="Prices")
    assert [pair.case for pair in pairs] == ["110/up", "110/down", "130/up", "130/down"]
    assert [pair.baseline.key for pair in pairs] == ["up", "down", "up", "down"]
    assert comparison.difference(outcome="Prices", key="worth") == (
        q("33 AUD"),
        q("27 AUD"),
        q("99 AUD"),
        q("81 AUD"),
    )
    summary = comparison.by_case.summary()
    assert summary.column("case") == ("110", "130")
    assert summary.column("mean") == (q("30 AUD"), q("90 AUD"))
    # A batch on some of the paths, or with two cases on one path, does not
    # pair with a batch on all of them.
    batches = [nested.case(key=key) for key in ("110", "130")]
    leaves = [batch.case(key=key) for batch in batches for key in paths.keys]
    resolver = rk.io.MemoryStore()
    for document in (priced, paths, *leaves):
        resolver.put(document)
    for chosen, match in (
        ((leaves[0],), "different paths"),
        ((leaves[0], leaves[2]), "one case"),
    ):
        some = Specification.from_data(
            {
                "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
                "model": str(priced.id),
                "cases": [str(leaf.id) for leaf in chosen],
            }
        )
        resolver.put(some)
        found = solve(specification=some, resolver=resolver).raise_for_status()
        with pytest.raises(ContractError, match=match) as raised:
            compare(
                outcomes={"Some": found, "Low": low}, keys=["worth"], baseline="Some"
            )
        assert raised.value.code is Code.COMPARISON_CASES
    assert raised.value.values["repeated"] == ["up"]
