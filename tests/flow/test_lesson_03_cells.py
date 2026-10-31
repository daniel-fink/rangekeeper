"""Lesson 03 cells 16 and 17 run as written on solved Flows (#273, #205).

Cell 16 splits the net need through 2028 by hand: it reads the running total of
the net cash flow at a date, takes the equity's part with Python's ``min``, and
grosses the loan's part up for its own interest in that year. In the lesson,
``outcome`` is the base case's Outcome; here a Stream of the same Flow stands in
for it, because ``outcome[key]`` and ``stream[name]`` both give a Flow.
``levered_outcome`` stands in for the levered Outcome: ``case`` gives the values
and the Flows that the cells read by key. ``plan`` gives each Quantity of the
base plan by key, as ``helpers.load_base_plan`` does.
"""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import rangekeeper as rk

LESSON = (
    Path(__file__).resolve().parents[2]
    / "examples/walkthrough/proposed/03_cases_debt_equity.md"
)
YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def cell(number: str) -> str:
    """Return the code of one numbered cell of the proposed lesson."""
    for block in re.findall(r"```python\n(.*?)```", LESSON.read_text(), re.S):
        if re.match(rf"# cell {number}\b", block):
            return block
    raise AssertionError(f"lesson 03 has no cell {number}")


class Levered:
    """The levered Outcome that the cells read: one case, by key."""

    def __init__(self, **reference: object) -> None:
        self.reference = reference

    def case(self, *, key: str) -> dict[str, object]:
        assert key == "reference"
        return self.reference


def base_case(*, land_cost: str, shared_cost: str) -> rk.flow.Stream:
    """Return the net cash flow that the base case solves, by key."""
    land = rk.flow.Flow(
        amounts={period: 0 for period in YEARS} | {YEARS[0]: f"-{land_cost}"},
        units="AUD",
    )
    works = rk.flow.Flow(
        amounts={period: 0 for period in YEARS}
        | {YEARS[0]: f"-{shared_cost}", YEARS[1]: "-30e6 AUD", YEARS[2]: "-30e6 AUD"},
        units="AUD",
    )
    return rk.flow.Stream(flows={"net_cash_flow": land + works})


def run_cell_16(
    *, outcome: rk.flow.Stream, equity: str, levered_outcome: Levered
) -> dict[str, object]:
    plan = {"equity": rk.Quantity(text=equity)}
    namespace = {
        "rk": rk,
        "date": date,
        "outcome": outcome,
        "levered_outcome": levered_outcome,
        "plan": plan,
    }
    exec(cell("16"), namespace)
    return namespace


# At 20 % pa, each AUD of loan lends 0.8 AUD after its interest: an exact quotient.
LEVERED = Levered(loan_rate=rk.Quantity(text="20 % pa"))


@pytest.mark.parametrize(
    ("equity", "from_equity", "from_loan"),
    [
        ("50e6 AUD", "50e6 AUD", "43.75e6 AUD"),
        ("90e6 AUD", "85e6 AUD", "0 AUD"),
    ],
)
def test_cell_16_splits_the_need_through_2028_between_equity_and_the_loan(
    equity, from_equity, from_loan
):
    outcome = base_case(land_cost="40e6 AUD", shared_cost="15e6 AUD")
    namespace = run_cell_16(outcome=outcome, equity=equity, levered_outcome=LEVERED)
    assert namespace["need"] == rk.Quantity(text="85e6 AUD")
    assert namespace["from_equity"] == rk.Quantity(text=from_equity)
    assert namespace["from_loan"] == rk.Quantity(text=from_loan)


def test_cell_16_keeps_exact_currency_amounts():
    outcome = base_case(land_cost="40000000.01 AUD", shared_cost="15e6 AUD")
    namespace = run_cell_16(outcome=outcome, equity="50e6 AUD", levered_outcome=LEVERED)
    from_loan = namespace["from_loan"]
    assert isinstance(from_loan, rk.Quantity) and from_loan.units == "AUD"
    assert namespace["need"].magnitude == Decimal("85000000.01")
    assert from_loan.magnitude == Decimal("43750000.0125")


def test_cell_17_compares_the_loan_principal_with_the_split():
    """Cell 17 checks the Model's split against cell 16 with ``at`` and ``isclose``."""
    loan_principal = rk.flow.Flow(
        amounts={YEARS[0]: "0 AUD", YEARS[1]: "43.75e6 AUD"}, units="AUD"
    )
    levered_outcome = Levered(
        loan_rate=rk.Quantity(text="20 % pa"), loan_principal=loan_principal
    )
    namespace = run_cell_16(
        outcome=base_case(land_cost="40e6 AUD", shared_cost="15e6 AUD"),
        equity="50e6 AUD",
        levered_outcome=levered_outcome,
    )
    # The cell's last statement only draws the case's Stream.
    (check, _) = cell("17").split("reference_outcome.stream(")
    exec(check, namespace)
    assert namespace["principal_2028"] == rk.Quantity(text="43.75e6 AUD")
