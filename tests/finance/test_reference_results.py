"""Account and cycle calculations checked against captured reference results.

The fixture is frozen, so a regression cannot change its own expected values.
Cycle residuals also check the defining equation independently of the fixture.
"""

import json
import math
from datetime import date
from pathlib import Path

import pytest

from rangekeeper.duration import Frequency, make_periods
from rangekeeper.finance.account import (
    Account,
    Balance,
    CurrentInterest,
    InterestTreatment,
)
from rangekeeper.finance.dynamics import calculate_cycle
from rangekeeper.flow import Flow
from rangekeeper.quantity import Quantity

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/account-reference.json").read_text()
)


@pytest.mark.parametrize(
    "case",
    REFERENCE["accounts"],
    ids=lambda c: f"{c['method']}-{c['timing']}-{c['starting']}",
)
def test_account_numeric_recurrence_matches_reference(case):

    movements = [10.0, -200.0, 80.0, 400.0, -50.0]
    actual = Account.calculate(
        Flow.from_periods(
            make_periods(date(2020, 1, 1), frequency=Frequency.MONTH, count=5),
            movements,
            units="meter",
        ),
        starting=Quantity(magnitude=case["starting"], units="meter"),
        rate=0.01,
        balance=(Balance.OPENING if case["timing"] == "arrears" else Balance.CLOSING),
        current_interest=(
            CurrentInterest.INCLUDED
            if case["method"] == "capitalized"
            else CurrentInterest.EXCLUDED
        ),
        treatment=(
            InterestTreatment.SEPARATE
            if case["method"] == "simple"
            else InterestTreatment.FINANCED
        ),
    )
    for flow, values in zip(
        (actual.opening, actual.closing, actual.overdraft_balance, actual.interest),
        case["outputs"],
        strict=True,
    ):
        assert [s.magnitude for s in flow.movements] == pytest.approx(
            list(values), abs=1e-10
        )


@pytest.mark.parametrize("case", REFERENCE["cycles"], ids=lambda c: str(c["asymmetry"]))
def test_bounded_cycle_matches_reference_and_equation(case):
    asymmetry = case["asymmetry"]
    actual = calculate_cycle(
        count=50, period=9, phase=2, amplitude=0.3, asymmetry=asymmetry
    )
    assert actual == pytest.approx(case["values"], abs=1e-9)
    for i, value in enumerate(actual):
        unit_value = value / 0.3
        assert unit_value == pytest.approx(
            math.sin((i - 2) * 2 * math.pi / 9 - asymmetry * unit_value), abs=1e-9
        )
