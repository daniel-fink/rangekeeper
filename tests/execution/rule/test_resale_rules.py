"""The investment example's resale rule, run through the public solve and stored Run.

The expected sale periods are worked by hand: a factor is known on the last day of its
period, the threshold is strict, and the first period that the rule checks is the one
that the minimum holding gives.
"""

from datetime import date
from uuid import uuid4

import pytest

from rangekeeper.duration import Frequency, Periods
from rangekeeper.execution import DecisionResult, execute
from rangekeeper.flow import Flow
from rangekeeper.io import MemoryStore
from rangekeeper.model import Metadata
from rangekeeper.run import Run, validate
from rangekeeper.schema.enums import SolutionStatus
from rangekeeper.shared.errors import ValidationError
from rangekeeper.specification import Specification, SpecificationRecord
from rangekeeper_examples import investment

pytest.importorskip("pyomo")
pytest.importorskip("highspy")


def priced(factors: list[float]):
    """Return an investment Model that holds ``factors``, one for each sale period."""
    periods = Periods(
        start=date(2027, 1, 1), frequency=Frequency.YEAR, count=len(factors) + 1
    )
    flow = Flow.from_periods(
        periods=periods, magnitudes=[*factors, 1.0], units="dimensionless"
    )
    return investment.formulate(
        investment.author(
            dict(num_periods=len(factors), start_date=date(2026, 1, 1)), factors=flow
        )
    )


def solved(model, rule):
    store = MemoryStore()
    store.put(model)
    specification = investment.specify(model, rule=rule)
    run = execute(specification=specification, store=store).run
    assert run.report.status.solution is SolutionStatus.FEASIBLE, run.report.to_data()
    validate(run=run, resolver=store).raise_if_invalid()
    return store, run


@pytest.mark.parametrize(
    "factors,minimum,sale",
    [
        ([1.2, 1.2, 1.2], 1, 3),
        ([2, 2, 2], 2, 2),
        ([1, 1.3, 2], 1, 2),
        ([1, 1, 1.3], 1, 3),
        ([1, 1, 1], 1, 3),
    ],
)
def test_resale_dates_strict_threshold_and_holding(factors, minimum, sale):
    model = priced(factors)
    rule = investment.stop_gain_resale_rule(
        model, threshold=1.2, minimum_holding_periods=minimum
    )
    store, run = solved(model, rule)
    report = investment.report(store.load_model(run.record.outputs[0]))
    assert report.sale_date == date(2026 + sale, 12, 31)
    output = investment.values(report.model)
    assert [m.number for m in output["sale"].flow.movements] == [
        int(i + 1 == sale) for i in range(len(factors))
    ]
    assert [m.number for m in output["holding"].flow.movements] == [
        int(i < sale) for i in range(len(factors))
    ]


def test_a_rule_that_never_meets_its_condition_sells_at_the_end():
    model = priced([1, 1, 1])
    _, run = solved(model, investment.stop_gain_resale_rule(model))
    (decided,) = run.rule_evidence.decided
    assert decided.value.date == date(2029, 12, 31)
    assert decided.decision_date == date(2029, 12, 31)
    assert [check.result for check in run.rule_evidence.checks] == [
        DecisionResult.DECIDED
    ]


def test_a_later_factor_does_not_change_an_earlier_decision():
    rule = dict(threshold=1.2, minimum_holding_periods=1)
    before = priced([1, 1.3, 1])
    after = priced([1, 1.3, 99])
    decided = [
        solved(model, investment.stop_gain_resale_rule(model, **rule))[1]
        .rule_evidence.decided[0]
        .value.date
        for model in (before, after)
    ]
    assert decided == [date(2028, 12, 31)] * 2


def test_a_changed_stored_trace_fails_validation():
    model = priced([1, 1.3, 2])
    rule = investment.stop_gain_resale_rule(model, minimum_holding_periods=1)
    store, run = solved(model, rule)
    data = run.to_data()
    data["metadata"]["id"] = str(uuid4())
    data["report"]["rule_evidence"]["checks"][0]["observations"][0]["available_on"] = (
        "2000-01-01"
    )
    assert not validate(run=Run.from_data(data), resolver=store).valid


def test_a_sale_rule_and_a_fixed_sale_date_cannot_both_come_from_contributors():
    model = priced([1, 1.3, 2])
    rule = investment.stop_gain_resale_rule(model, minimum_holding_periods=1)
    ruled = investment.specify(model, rule=rule)
    fixed = investment.specify(model, sale_period=2)
    store = MemoryStore()
    for document in (model, ruled, fixed):
        store.put(document)
    joined = Specification(
        record=SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            includes=(ruled.id, fixed.id),
        )
    )
    with pytest.raises(ValidationError):
        joined.compose(resolver=store)


def test_a_rule_with_a_fixed_sale_period_is_refused():
    model = priced([1, 1])
    rule = investment.stop_gain_resale_rule(model, minimum_holding_periods=1)
    with pytest.raises(ValueError, match="choose a rule"):
        investment.specify(model, rule=rule, sale_period=1)
    with pytest.raises(ValueError, match="minimum holding"):
        investment.stop_gain_resale_rule(model, minimum_holding_periods=3)
