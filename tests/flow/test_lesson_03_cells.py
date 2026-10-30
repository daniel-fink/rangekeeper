"""Lesson 03 cell 16 runs as written on solved Flows (#273).

Cell 16 splits the first year's payments by hand: it reads the land and works
Flows of the base case at a date, adds and negates the amounts, and takes the
equity's part with Python's ``min``. In the lesson, ``outcome`` is the base
case's Outcome; here a Stream of the same Flows stands in for it, because
``outcome[key]`` and ``stream[name]`` both give a Flow. ``plan`` gives each
Quantity of the base plan by key, as ``helpers.load_base_plan`` does.
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


def base_case(*, land_cost: str, shared_cost: str) -> rk.flow.Stream:
    """Return the land and works Flows that the base case solves, by key."""
    land = rk.flow.Flow(
        amounts={period: 0 for period in YEARS} | {YEARS[0]: f"-{land_cost}"},
        units="AUD",
    )
    works = rk.flow.Flow(
        amounts={period: 0 for period in YEARS}
        | {YEARS[0]: f"-{shared_cost}", YEARS[1]: "-30e6 AUD", YEARS[2]: "-30e6 AUD"},
        units="AUD",
    )
    return rk.flow.Stream(flows={"land": land, "works": works})


def run_cell_16(*, outcome: rk.flow.Stream, equity: str) -> dict[str, object]:
    plan = {"equity": rk.Quantity(text=equity)}
    namespace = {"rk": rk, "date": date, "outcome": outcome, "plan": plan}
    exec(cell("16"), namespace)
    return namespace


@pytest.mark.parametrize(
    ("equity", "from_equity", "from_loan"),
    [
        ("50e6 AUD", "50e6 AUD", "5e6 AUD"),
        ("80e6 AUD", "55e6 AUD", "0 AUD"),
    ],
)
def test_cell_16_splits_the_first_year_between_equity_and_the_loan(
    equity, from_equity, from_loan
):
    outcome = base_case(land_cost="40e6 AUD", shared_cost="15e6 AUD")
    namespace = run_cell_16(outcome=outcome, equity=equity)
    assert namespace["paid_2027"] == rk.Quantity(text="55e6 AUD")
    assert namespace["from_equity"] == rk.Quantity(text=from_equity)
    assert namespace["from_loan"] == rk.Quantity(text=from_loan)


def test_cell_16_keeps_exact_currency_amounts():
    outcome = base_case(land_cost="40000000.01 AUD", shared_cost="15e6 AUD")
    namespace = run_cell_16(outcome=outcome, equity="50e6 AUD")
    from_loan = namespace["from_loan"]
    assert isinstance(from_loan, rk.Quantity) and from_loan.units == "AUD"
    assert from_loan.magnitude == Decimal("5000000.01")


def test_cell_17_compares_the_loan_principal_with_the_split():
    """Cell 17 checks the Model's split against cell 16 with ``at`` and ``==``."""
    namespace = run_cell_16(
        outcome=base_case(land_cost="40e6 AUD", shared_cost="15e6 AUD"),
        equity="50e6 AUD",
    )
    loan_principal = rk.flow.Flow(
        amounts={YEARS[0]: "5e6 AUD", YEARS[1]: "35e6 AUD"}, units="AUD"
    )
    assert loan_principal.at(on=date(2027, 1, 1)) == namespace["from_loan"]
