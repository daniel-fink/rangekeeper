"""Independent account equations, signed recurrence and rate preparation regressions."""

from datetime import date
from fractions import Fraction
import math
import pytest

from rangekeeper.account import Balance, CurrentInterest, InterestTreatment
from rangekeeper.calculations.account import Account
from rangekeeper.model.flow import Flow
from rangekeeper.model.measure import Quantity


def amounts(flow):
    return [m.number for m in flow.movements]


def transactions(values):
    return Flow.from_events(
        [date(2026, 1, i + 1) for i in range(len(values))], values, units="AUD"
    )


@pytest.mark.parametrize(
    "balance,current,treatment,charges,closings",
    [
        (
            Balance.OPENING,
            CurrentInterest.EXCLUDED,
            InterestTreatment.SEPARATE,
            [10, 24],
            [120, 90],
        ),
        (
            Balance.CLOSING,
            CurrentInterest.EXCLUDED,
            InterestTreatment.SEPARATE,
            [12, 18],
            [120, 90],
        ),
        (
            Balance.OPENING,
            CurrentInterest.EXCLUDED,
            InterestTreatment.FINANCED,
            [10, 26],
            [130, 126],
        ),
        (
            Balance.CLOSING,
            CurrentInterest.EXCLUDED,
            InterestTreatment.FINANCED,
            [12, 20.4],
            [132, 122.4],
        ),
        (
            Balance.OPENING,
            CurrentInterest.INCLUDED,
            InterestTreatment.FINANCED,
            [Fraction(100, 9), Fraction(295, 9)],
            [Fraction(1180, 9), Fraction(1205, 9)],
        ),
        (
            Balance.CLOSING,
            CurrentInterest.INCLUDED,
            InterestTreatment.FINANCED,
            [Fraction(40, 3), Fraction(155, 6)],
            [Fraction(400, 3), Fraction(775, 6)],
        ),
    ],
)
def test_six_conventions_against_independent_equations(
    balance, current, treatment, charges, closings
):
    tx = transactions([20, -30])
    rates = transactions([10, 20]).replace(units="percent")
    before = tx.to_data()
    result = Account.calculate(
        tx,
        starting=Quantity(magnitude=100, units="AUD"),
        rate=rates,
        balance=balance,
        current_interest=current,
        treatment=treatment,
    )
    assert amounts(result.interest) == pytest.approx([float(x) for x in charges])
    assert amounts(result.closing) == pytest.approx([float(x) for x in closings])
    assert tx.to_data() == before
    assert [m.coordinate for m in result.closing.movements] == [
        m.coordinate for m in tx.movements
    ]
    assert set(m.id for m in result.closing.movements).isdisjoint(
        m.id for m in tx.movements
    )


@pytest.mark.parametrize("balance", list(Balance))
def test_including_interest_requires_financing_even_when_empty(balance):
    with pytest.raises(ValueError, match="requires financed"):
        Account.calculate(
            transactions([]),
            starting=Quantity(magnitude=0, units="AUD"),
            balance=balance,
            current_interest=CurrentInterest.INCLUDED,
        )


@pytest.mark.parametrize("rate", [True, math.nan, math.inf, -math.inf, -1, -2])
def test_empty_input_does_not_bypass_scalar_rate_validation(rate):
    with pytest.raises(ValueError, match="interest rate"):
        Account.calculate(
            transactions([]), starting=Quantity(magnitude=0, units="AUD"), rate=rate
        )


def test_included_upper_bound_and_typed_options():
    with pytest.raises(ValueError, match="interest rate"):
        Account.calculate(
            transactions([]),
            starting=Quantity(magnitude=0, units="AUD"),
            rate=1,
            current_interest=CurrentInterest.INCLUDED,
            treatment=InterestTreatment.FINANCED,
        )
    with pytest.raises(TypeError, match="Balance"):
        Account.calculate(
            transactions([]),
            starting=Quantity(magnitude=0, units="AUD"),
            balance="opening",
        )


def test_same_day_coordinate_order_keeps_rates_with_transactions():
    tx = Flow.from_events(
        [date(2026, 1, 1)] * 2, [100, 100], units="AUD", keys=["z", "a"]
    )
    rates = Flow.from_events(
        [date(2026, 1, 1)] * 2, [0.1, 0.2], units="dimensionless", keys=["z", "a"]
    )
    result = Account.calculate(
        tx,
        starting=Quantity(magnitude=0, units="AUD"),
        rate=rates,
        treatment=InterestTreatment.FINANCED,
    )
    assert amounts(result.interest) == pytest.approx([10, 42])
    assert amounts(result.closing) == pytest.approx([110, 252])
    with pytest.raises(ValueError, match="coordinate"):
        Account.calculate(
            tx,
            starting=Quantity(magnitude=0, units="AUD"),
            rate=rates.replace(movements=rates.movements[::-1]),
        )
    with pytest.raises(ValueError, match="coordinate"):
        Account.calculate(
            tx,
            starting=Quantity(magnitude=0, units="AUD"),
            rate=rates.replace(movements=rates.movements[:1]),
        )


def test_signed_recurrence_deficits_negative_rates_and_default():
    tx = transactions([0, 200, -200])
    result = Account.calculate(
        tx,
        starting=Quantity(magnitude=-50, units="AUD"),
        rate=-0.1,
        treatment=InterestTreatment.FINANCED,
    )
    assert amounts(result.opening) == [0, 0, 135]
    assert amounts(result.interest) == [0, -15, 0]
    assert amounts(result.closing) == [0, 135, 0]
    assert amounts(result.overdraft_balance) == [-50, 0, -65]
    assert amounts(result.overdraft) == [-50, 50, -65]
    assert amounts(result.difference()) == [0, 135, -135]
    result = Account.calculate(
        transactions([20]), starting=Quantity(magnitude=100, units="AUD"), rate=0.1
    )
    assert amounts(result.interest) == [12]
    assert amounts(result.closing) == [120]


def test_rate_shapes_resolution_and_empty_results():
    tx = transactions([1, 1])
    rates = transactions([None, 1]).replace(units="dimensionless")
    with pytest.raises(ValueError, match="unresolved"):
        Account.calculate(tx, starting=Quantity(magnitude=0, units="AUD"), rate=rates)
    with pytest.raises(ValueError, match="incompatible"):
        Account.calculate(tx, starting=Quantity(magnitude=0, units="AUD"), rate=tx)
    result = Account.calculate(
        transactions([]), starting=Quantity(magnitude=1, units="AUD")
    )
    assert result.closing.movements == result.interest.movements == ()
    with pytest.raises(ValueError, match="nonfinite"):
        Account.calculate(
            transactions([1e308]), starting=Quantity(magnitude=1e308, units="AUD")
        )


def test_interest_treatment_on_an_unchanged_principal_has_independent_period_results():
    for current, treatment, charges, balances in (
        (CurrentInterest.EXCLUDED, InterestTreatment.SEPARATE, [10, 10], [100, 100]),
        (CurrentInterest.EXCLUDED, InterestTreatment.FINANCED, [10, 11], [110, 121]),
        (
            CurrentInterest.INCLUDED,
            InterestTreatment.FINANCED,
            [Fraction(100, 9), Fraction(1000, 81)],
            [Fraction(1000, 9), Fraction(10000, 81)],
        ),
    ):
        result = Account.calculate(
            transactions([0, 0]),
            starting=Quantity(magnitude=100, units="AUD"),
            rate=0.1,
            current_interest=current,
            treatment=treatment,
        )
        assert amounts(result.interest) == pytest.approx([float(x) for x in charges])
        assert amounts(result.closing) == pytest.approx([float(x) for x in balances])


def test_synthetic_construction_conventions_distinguish_funded_interest():
    # One unconstrained RLV step: principal includes this period's non-interest cost.
    rlv = Account.calculate(
        transactions([166_360.516150]),
        starting=Quantity(magnitude=412_477.357445, units="AUD"),
        rate=0.085 / 12,
        current_interest=CurrentInterest.INCLUDED,
        treatment=InterestTreatment.FINANCED,
    )
    assert amounts(rlv.interest) == pytest.approx([4_129.351175], abs=1e-6)
    assert amounts(rlv.closing) == pytest.approx([582_967.224770], abs=1e-6)
    # Opening-based construction interest is reported separately. A later explicit
    # funding draw includes that charge once; the account must not add it again.
    operating = Account.calculate(
        transactions([50, 10]),
        starting=Quantity(magnitude=100, units="AUD"),
        rate=0.1,
        balance=Balance.OPENING,
        treatment=InterestTreatment.SEPARATE,
    )
    assert amounts(operating.interest) == [10, 15]
    assert amounts(operating.closing) == [150, 160]
