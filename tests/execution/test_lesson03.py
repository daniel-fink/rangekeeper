"""Lesson 03's solves, from the proposed cells (#276, #280, #308).

The cells come from ``examples/walkthrough/proposed/03_cases_debt_equity.md``
and run statement by statement, as written, with three differences, each
waiting on another issue:

- ``RESULTS``: the results that the cells leave for the draft to infer are
  declared first (#282), as ``tests/walkthrough/test_proposed_lesson_03.py``
  does, with the three Flows that cell 18 adds.
- ``ANNUAL``: the incomes and operating costs are declared in AUD, not
  ``AUD pa``. A growth profile of an amount in ``AUD pa`` gives a Flow in
  ``AUD pa``, and cell 5c declares the rent Flows in AUD; the convention that
  makes an annual amount an amount for each Period is not decided yet.
- ``PLAN``: the plan's inputs stand in for ``helpers.load_base_plan()`` (G07),
  and the statements that call ``helpers`` are skipped.
"""

import ast
from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.execution import Status
from rangekeeper.quantity import isclose
from tests.walkthrough.test_proposed_lesson_03 import RESULTS, cells

ANNUAL = ("a_income", "b_income", "a_opex", "b_opex")
FUNDING = ("equity_available", "loan_available", "shortfall")
PLAN = {
    "base_date": date(2027, 1, 1),
    "sale_date": date(2036, 12, 31),
    "start_date": date(2027, 1, 1),
    "b_start": date(2030, 1, 1),
    "land_cost": rk.Quantity(text="20e6 AUD"),
    "shared_cost": rk.Quantity(text="10e6 AUD"),
    "a_cost": rk.Quantity(text="60e6 AUD"),
    "b_cost": rk.Quantity(text="50e6 AUD"),
    "a_income": rk.Quantity(text="6e6 AUD"),
    "b_income": rk.Quantity(text="5e6 AUD"),
    "a_opex": rk.Quantity(text="1.5e6 AUD"),
    "b_opex": rk.Quantity(text="1.2e6 AUD"),
    "a_renewal": rk.Quantity(text="2e6 AUD"),
    "b_renewal": rk.Quantity(text="1.5e6 AUD"),
    "equity": rk.Quantity(text="50e6 AUD"),
    "loan_limit": rk.Quantity(text="80e6 AUD"),
}
YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)
# The statement of cell 8 that waits on #282: Entity.values (D44).
WAITING = "model.entity(code='project').values"


def statements(key: str) -> list[str]:
    """Return the statements of a cell, with the differences of this module."""
    found = []
    for statement in ast.parse(cells()[key]).body:
        code = ast.unparse(statement)
        if "helpers" in code or code == WAITING:
            continue
        for name in ANNUAL:
            code = code.replace(
                f"key='{name}', units='AUD pa'", f"key='{name}', units='AUD'"
            )
        found.append(code)
    return found


def declare(project, keys) -> None:
    for key in keys:
        kind, units = RESULTS.get(key, ("flow", "AUD"))
        if kind == "date":
            project.date(key=key)
        elif kind == "flow":
            project.flow(key=key, units=units, periods=YEARS)
        else:
            project.value(key=key, units=units)


def run(namespace: dict, *keys: str) -> dict:
    """Run cells as written, declaring the results of RESULTS and FUNDING first."""
    for key in keys:
        for code in statements(key):
            if "add_formulation" in code and "declared" not in namespace:
                declare(namespace["project"], RESULTS)
                namespace["declared"] = True
            if "formulation(name='Funding')" in code and key == "18":
                declare(namespace["project"], FUNDING)
            exec(code, namespace)
    return namespace


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run cells 3, 5 to 13 and 16 to 19 of lesson 03, with their solves."""
    namespace: dict = {"rk": rk, "date": date, "plan": PLAN}
    namespace["cases"] = None
    return run(
        namespace,
        "3",
        "5",
        "5b",
        "5c",
        "6",
        "7",
        "7b",
        "8",
        "9",
        "11",
        "12",
        "12b",
        "13",
        "16",
        "17",
        "18",
        "19",
    )


def test_cell_9_solves_the_base_case(lesson):
    outcome = lesson["outcome"].raise_for_status()
    assert outcome["a_open"] == date(2030, 1, 1)
    cash = outcome["net_cash_flow"]
    assert isclose(
        actual=outcome["unlevered_npv"],
        expected=rk.finance.npv(flow=cash, rate="7 % pa", on=date(2027, 1, 1)),
        relative=1e-9,
    )


def test_cell_11_solves_the_named_cases(lesson):
    table = lesson["cases_outcome"].raise_for_status().table("unlevered_npv")
    npvs = [row.values["unlevered_npv"] for row in table.rows]
    assert npvs[0] < npvs[1] < npvs[2]  # weak < reference < strong


def test_cell_13_funds_the_plan_equity_first(lesson):
    levered = lesson["levered_outcome"].raise_for_status()
    reference = levered.case(key="reference")
    principal = reference["loan_principal"]
    need = reference["funding_need"]
    equity = PLAN["equity"].number
    for loan, needed in zip(principal.movements, need.movements, strict=True):
        assert loan.number == pytest.approx(max(0.0, needed.number - equity), abs=1e-3)
    cash = reference["equity_cash_flow"]
    assert isclose(
        actual=reference["equity_irr"],
        expected=rk.finance.irr(flow=cash),
        relative=1e-9,
    )


def test_cells_16_and_17_split_the_first_year_by_hand(lesson):
    # Cell 17 asserts that the solved principal of 2027 is the split by hand.
    assert lesson["from_equity"] == min(lesson["paid_2027"], PLAN["equity"])


def test_cell_19_reports_the_peak_shortfall(lesson):
    funded = lesson["funded_outcome"]
    assert funded.status is Status.FEASIBLE
    reference = funded.case(key="reference")
    shortfall = reference["shortfall"]
    assert reference["peak_shortfall"] == shortfall.max()
