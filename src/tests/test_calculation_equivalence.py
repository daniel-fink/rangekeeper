"""Canonical calculations checked against captured, synthetic Turn 3 results.

The fixture was captured before retirement. These tests cannot call the removed
implementation, so a regression cannot silently change its own expected values.
Cycle residuals also check the defining equation independently of that fixture.
"""

from datetime import date
import json
import math
from pathlib import Path
import pytest
from rangekeeper.model.flow import from_periods
from rangekeeper.model.measure import Quantity
from rangekeeper.duration import make_periods
from rangekeeper.calculations.account import calculate_account
from rangekeeper.calculations.dynamics.cyclicality import calculate_cycle


REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/numerical/turn3-reference.json").read_text()
)


@pytest.mark.parametrize(
    "case",
    REFERENCE["accounts"],
    ids=lambda c: f"{c['method']}-{c['timing']}-{c['starting']}",
)
def test_account_numeric_recurrence_matches_reference(case):

    movements = [10.0, -200.0, 80.0, 400.0, -50.0]
    actual = calculate_account(
        from_periods(
            make_periods(date(2020, 1, 1), frequency="month", count=5),
            movements,
            units="meter",
        ),
        starting=Quantity(magnitude=case["starting"], units="meter"),
        rate=0.01,
        method=case["method"],
        timing=case["timing"],
    )
    for flow, values in zip(
        (actual.opening, actual.closing, actual.overdraft_balance, actual.interest),
        case["outputs"],
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
