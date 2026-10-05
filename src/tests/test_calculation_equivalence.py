"""Bounded legacy comparisons. Only verification code imports the superseded APIs."""

from datetime import date
import pytest
from rangekeeper.model.flow import from_periods
from rangekeeper.model.measure import Quantity
from rangekeeper.temporal import make_periods
from rangekeeper.calculations.account import calculate_account
from rangekeeper.calculations.dynamics.cyclicality import calculate_cycle


@pytest.mark.parametrize("method", ["simple", "compound", "capitalized"])
@pytest.mark.parametrize("timing", ["advance", "arrears"])
@pytest.mark.parametrize("starting", [-20.0, 0.0, 100.0])
def test_account_numeric_recurrence_matches_legacy(method, timing, starting):
    from rangekeeper.formula.financial import Account

    movements = [10.0, -200.0, 80.0, 400.0, -50.0]
    rates = [0.01] * 5
    expected = Account._calculate(
        starting, movements, rates, method, timing == "arrears"
    )
    actual = calculate_account(
        from_periods(
            make_periods(date(2020, 1, 1), frequency="month", count=5),
            movements,
            units="meter",
        ),
        starting=Quantity(magnitude=starting, units="meter"),
        rate=0.01,
        method=method,
        timing=timing,
    )
    for flow, values in zip(
        (actual.opening, actual.closing, actual.overdraft_balance, actual.interest),
        expected,
    ):
        assert [s.magnitude for s in flow.movements] == pytest.approx(
            list(values), abs=1e-10
        )


@pytest.mark.parametrize("asymmetry", [0, 0.2, 0.8])
def test_bounded_cycle_matches_legacy_root(asymmetry):
    from rangekeeper.dynamics.cyclicality import Enumerate

    expected = Enumerate.asymmetric_sine(
        period=9,
        phase=2,
        amplitude=0.3,
        parameter=asymmetry,
        num_periods=50,
        precision=1e-11,
        bound=1,
    )
    actual = calculate_cycle(
        count=50, period=9, phase=2, amplitude=0.3, asymmetry=asymmetry
    )
    assert actual == pytest.approx(expected, abs=1e-9)
