"""Lesson 03's solves, from the proposed cells (#276, #277, #280, #308, #294).

The cells come from ``examples/walkthrough/proposed/03_cases_debt_equity.md``
and run statement by statement, as written; the value of a cell's last
expression is ``_``, as in IPython. The draft infers the results that the
cells do not declare, with the Periods of their Flows (#282). Cell 22 executes
into an empty ``runs/03`` folder, and cell 23 replays its Run in a namespace
that holds only ``rk``, as in a new kernel. One difference waits on another
issue:

- ``PLAN``: the plan's inputs stand in for ``helpers.load_base_plan()`` (G07),
  and the statements that call ``helpers`` are skipped.
"""

import ast
from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.execution import Status
from rangekeeper.quantity import isclose
from tests.walkthrough.test_proposed_lesson_03 import cells

PLAN = {
    "base_date": date(2027, 1, 1),
    "sale_date": date(2036, 12, 31),
    "start_date": date(2027, 1, 1),
    "b_start": date(2030, 1, 1),
    "land_cost": rk.Quantity(text="20e6 AUD"),
    "shared_cost": rk.Quantity(text="10e6 AUD"),
    "a_cost": rk.Quantity(text="60e6 AUD"),
    "b_cost": rk.Quantity(text="50e6 AUD"),
    "a_income": rk.Quantity(text="6e6 AUD pa"),
    "b_income": rk.Quantity(text="5e6 AUD pa"),
    "a_opex": rk.Quantity(text="1.5e6 AUD pa"),
    "b_opex": rk.Quantity(text="1.2e6 AUD pa"),
    "a_renewal": rk.Quantity(text="2e6 AUD"),
    "b_renewal": rk.Quantity(text="1.5e6 AUD"),
    "equity": rk.Quantity(text="50e6 AUD"),
    "loan_limit": rk.Quantity(text="80e6 AUD"),
}


def statements(key: str) -> list[str]:
    """Return the statements of a cell, with the differences of this module."""
    found = []
    for statement in ast.parse(cells()[key]).body:
        code = ast.unparse(statement)
        if "helpers" in code:
            continue
        found.append(code)
    return found


def run(namespace: dict, *keys: str) -> dict:
    """Run cells as written, statement by statement, from ``namespace``.

    The value of each expression statement is ``_``, as in IPython.
    """
    for key in keys:
        for code in statements(key):
            if isinstance(ast.parse(code).body[0], ast.Expr):
                namespace["_"] = eval(code, namespace)
            else:
                exec(code, namespace)
    return namespace


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run cells 3, 5 to 19 and 21 of lesson 03, with their solves."""
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
        "15",
        "16",
        "17",
        "18",
        "19",
        "21",
    )


@pytest.fixture(scope="module")
def kernel(lesson: dict, tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Run cell 22 in an empty folder, then cell 23 as in a new kernel."""
    folder = tmp_path_factory.mktemp("lesson03")
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(folder)
        run(lesson, "22")
        return run({"rk": rk}, "23")


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


def test_cell_15_finds_the_land_cost_of_a_target_irr(lesson):
    target = lesson["target_outcome"].raise_for_status()
    cash = target["equity_cash_flow"]
    assert isclose(
        actual=rk.finance.irr(flow=cash),
        expected=rk.Quantity(text="15 % pa"),
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


def test_cell_21_reports_the_commitment_gap(lesson):
    """Cell 21 finds the Funding Formulation of cell 12 and adds commitments (#305)."""
    committed = lesson["committed_outcome"]
    assert committed.status is Status.FEASIBLE
    model = lesson["model"]
    funding = model.edit().entity(code="project").formulation(name="Funding")
    assert funding.name == "Funding"
    for key in ("weak", "reference", "strong"):
        case = committed.case(key=key)
        gap = case["commitment_gap"]
        assert gap.units == "AUD" and gap.number >= 0
        assert (
            case["peak_shortfall"]
            == lesson["funded_outcome"].case(key=key)["peak_shortfall"]
        )


def test_cell_22_executes_the_funded_cases_into_an_empty_store(lesson, kernel):
    """``execute`` publishes the Model, the cases, the outputs and the Runs (#294)."""
    executed = lesson["executed"].raise_for_status()
    assert lesson["_"] == executed.run.id
    store = lesson["store"]
    assert store.root.parts[-2:] == ("runs", "03")
    assert store.load_model(lesson["funded"].model.id).id == lesson["funded"].model.id
    for case in executed.cases:
        assert store.load_run(case.run.id).id == case.run.id
        assert store.load_model(case.outputs[0].id).id == case.outputs[0].id


def test_cell_23_replays_the_stored_run_in_a_new_kernel(lesson, kernel):
    """``find_runs`` finds the batch Run by name; ``replay`` gives its result."""
    assert kernel["run"].id == lesson["executed"].run.id
    replayed = kernel["_"]
    assert isinstance(replayed, rk.execution.Replay)
    assert replayed.diagnostics == ()
    assert replayed.outcome.status is Status.FEASIBLE
    assert [case.key for case in replayed.outcome.cases] == [
        "weak",
        "reference",
        "strong",
    ]
    reference = replayed.outcome.case(key="reference")
    assert (
        reference["peak_shortfall"]
        == (lesson["funded_outcome"].case(key="reference")["peak_shortfall"])
    )
