"""Lesson 03's solves, from the proposed cells (#276, #277, #280, #308, #294, #205).

The cells come from ``examples/walkthrough/proposed/03_cases_debt_equity.md``
and run statement by statement, as written; the value of a cell's last
expression is ``_``, as in IPython. The draft infers the results that the
cells do not declare, with the Periods of their Flows (#282). Cell 22 executes
into an empty ``runs/03`` folder, and cell 23 replays its Run in a namespace
that holds only ``rk``, as in a new kernel.

``base_plan()`` reads the data package's ``base_plan.json``, as
``helpers.load_base_plan()`` does: the helpers need the walkthrough environment,
so the statements that call ``helpers`` are skipped here. The lesson's own run,
with its helpers, is in ``examples/walkthrough/tests/test_lessons.py``.
"""

import ast
import json
import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk
from rangekeeper.execution import Status
from rangekeeper.quantity import isclose
from tests.walkthrough.test_proposed_lesson_03 import LESSON, cells

DATA = (
    Path(__file__).resolve().parents[2]
    / "examples/data/mixed_use_property/base_plan.json"
)


class Plan(dict):
    """The plan's values by key, with its areas and rates: as ``BasePlan`` gives them."""

    areas: dict[str, dict[str, rk.Quantity]]
    rates: dict[str, rk.Quantity]


def quantity(item: dict) -> rk.Quantity:
    return rk.Quantity(magnitude=item["magnitude"], units=item["units"])


def base_plan() -> Plan:
    """Return the base plan of the data package, without arithmetic."""
    content = json.loads(DATA.read_text(encoding="utf-8"))
    plan = Plan()
    for key, item in content["values"].items():
        plan[key] = (
            date.fromisoformat(item["date"]) if "date" in item else quantity(item)
        )
    plan.areas = {
        package: {use: quantity(item) for use, item in uses.items()}
        for package, uses in content["areas"].items()
    }
    plan.rates = {use: quantity(item) for use, item in content["rates"].items()}
    return plan


PLAN = base_plan()


def solutions() -> list[str]:
    """Return the solution cells of the exercises, in order."""
    blocks = re.findall(r"```python\n(.*?)```", LESSON.read_text(), re.S)
    return [block for block in blocks if block.startswith("# solution")]


def statements(source: str) -> list[str]:
    """Return the statements of a cell, without those that call ``helpers``."""
    found = []
    for statement in ast.parse(source).body:
        code = ast.unparse(statement)
        if "helpers" not in code:
            found.append(code)
    return found


def execute(namespace: dict, source: str) -> None:
    """Run one cell, statement by statement; an expression's value is ``_``."""
    for code in statements(source):
        if isinstance(ast.parse(code).body[0], ast.Expr):
            namespace["_"] = eval(code, namespace)
        else:
            exec(code, namespace)


def run(namespace: dict, *keys: str) -> dict:
    """Run numbered cells as written, from ``namespace``."""
    for key in keys:
        execute(namespace, cells()[key])
    return namespace


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run cells 3 to 19 and 21 of lesson 03, with their solves."""
    namespace: dict = {"rk": rk, "date": date, "plan": PLAN}
    return run(
        namespace,
        "3",
        "4",
        "5",
        "5b",
        "5c",
        "6",
        "7",
        "7b",
        "8",
        "9",
        "10",
        "11",
        "12",
        "12b",
        "13",
        "14",
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


def test_cells_16_and_17_split_the_need_through_2028_by_hand(lesson):
    """The running total passes the equity in 2028, so the loan's part is positive.

    Cell 17 asserts that the solved principal of 2028 is the split by hand.
    """
    assert lesson["from_equity"] == PLAN["equity"]
    assert lesson["from_loan"] > rk.Quantity(text="0 AUD")
    paid = -lesson["outcome"]["net_cash_flow"].cumulative()
    assert paid.at(on=date(2027, 1, 1)) < PLAN["equity"]
    assert lesson["year_interest"] == pytest.approx(0.06)


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


def test_the_plan_gives_the_reference_case_a_target_land_price(lesson):
    """The reference case earns the equity rate, and cell 15's land price is positive."""
    reference = lesson["levered_outcome"].case(key="reference")
    assert reference["equity_irr"] >= rk.Quantity(text="12 % pa")
    assert lesson["target_outcome"]["land_cost"] > rk.Quantity(text="0 AUD")


def test_cell_14_compares_the_equity_levels(lesson):
    table = rk.execution.solve(
        specification=lesson["levered"].cases(cases=lesson["levels"])
    ).table("equity_npv")
    npvs = table.column("equity_npv")
    assert npvs[0] < npvs[1] < npvs[2]  # less equity, higher equity NPV


@pytest.fixture(scope="module")
def exercises(lesson: dict) -> dict:
    """Run the three solutions of the exercises as written, in order."""
    for source in solutions():
        execute(lesson, source)
    return lesson


def test_try_it_1_stresses_the_funded_plan(exercises):
    stress = exercises["stress_outcome"].raise_for_status()
    reference = exercises["funded_outcome"].case(key="reference")
    assert stress["peak_shortfall"] > reference["peak_shortfall"]
    # The equity receives real cash at the sale, so its IRR is not rounding noise.
    assert stress["equity_cash_flow"].max() > rk.Quantity(text="1e6 AUD")
    assert stress["equity_irr"] > rk.Quantity(text="-50 % pa")


def test_try_it_2_finds_a_lower_land_price_in_the_weak_case(exercises):
    # The solution asserts the order; the land price of the weak case can be negative.
    assert exercises["weak_target_outcome"].status is Status.FEASIBLE


def test_try_it_3_finds_the_year_of_the_smallest_available_loan(exercises, capsys):
    source = solutions()[2]
    execute(exercises, source)
    shown = capsys.readouterr().out
    available = exercises["available"]
    smallest = available.min()
    assert str(smallest) in shown
    assert "2032" in shown
    assert available.at(on=date(2032, 1, 1)) == smallest


def test_cell_24_checks_the_lesson(exercises):
    """The check cell runs as written, after the cells that it reads."""
    run(exercises, "24")
    npvs = exercises["npvs"]
    assert list(npvs) == sorted(npvs)
