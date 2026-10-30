"""Lesson 04's distribution cells 12, 14, 15 and 16 on lesson 03's batch of cases (#296).

The cells come from ``examples/walkthrough/proposed/04_market_futures.md`` and
run statement by statement, as written. Lesson 04 makes ``paths_outcome`` with
``base.across(paths=paths)`` (#299, #306) and ``average_outcome`` from the
average path (cell 10). Until ``across`` exists, lesson 03's funded batch of
three named cases (cell 19) stands in for the paths, and the funded reference
case stands in for the average path: the cells read the batch's distributions
in the same way. The statements that call ``helpers`` only draw, and are
skipped.
"""

import ast
import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk
from rangekeeper.execution import Distribution, Outcome, Paired
from rangekeeper.shared.table import Table
from tests.execution.test_lesson03 import PLAN
from tests.execution.test_lesson03 import statements as lesson03

pytest.importorskip("pyomo")
pytest.importorskip("highspy")

LESSON = (
    Path(__file__).resolve().parents[2]
    / "examples/walkthrough/proposed/04_market_futures.md"
)
# Lesson 03's cells up to the funded batch of cell 19, without the solves
# that the stand-in does not read.
LESSON03 = ("3", "5", "5b", "5c", "6", "7", "7b", "8", "9", "11", "12", "12b", "13")


def cell(number: str) -> list[str]:
    """Return the statements of one cell of lesson 04, without the helper calls."""
    for block in re.findall(r"```python\n(.*?)```", LESSON.read_text(), re.S):
        if block.startswith(f"# cell {number}\n"):
            return [
                code
                for code in map(ast.unparse, ast.parse(block).body)
                if "helpers" not in code
            ]
    raise LookupError(number)


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run lesson 03 to its funded batch, then lesson 04 cells 12, 14, 15 and 16."""
    namespace: dict = {"rk": rk, "date": date, "plan": PLAN, "cases": None}
    for key in LESSON03:
        for code in lesson03(key):
            if "outcome" not in code:
                exec(code, namespace)
    for code in lesson03("18") + lesson03("19"):
        exec(code, namespace)
    namespace["paths_outcome"] = namespace["funded_outcome"].raise_for_status()
    namespace["average_outcome"] = rk.execution.solve(
        specification=namespace["funded"]
    ).raise_for_status()
    for number in ("12", "14", "15", "16"):
        namespace[f"cell {number}"] = run(namespace, number)
    return namespace


def run(namespace: dict, number: str) -> object:
    """Run one cell of lesson 04 as written; return its last expression's value."""
    shown = None
    for code in cell(number):
        if isinstance(ast.parse(code).body[0], ast.Expr):
            shown = eval(code, namespace)
        else:
            exec(code, namespace)
    return shown


def test_cell_12_summarises_the_npv(lesson):
    npv = lesson["npv"]
    assert isinstance(npv, Distribution)
    summary = lesson["cell 12"]
    assert isinstance(summary, Table)
    (row,) = summary.rows
    assert row.values["count"] == 3
    table = lesson["paths_outcome"].table("unlevered_npv")
    assert list(npv.values) == list(table.column("unlevered_npv"))
    assert row.values["minimum"] <= row.values["mean"] <= row.values["maximum"]


def test_cell_14_compares_the_mean_of_the_cases_with_one_solve(lesson):
    comparison = lesson["cell 14"]
    assert isinstance(comparison, Paired)
    mean = lesson["paths_outcome"].mean()
    average = lesson["average_outcome"]
    for key in ("unlevered_npv", "equity_npv", "peak_shortfall"):
        (difference,) = comparison.difference(outcome="Mean of paths", key=key)
        assert difference == mean[key] - average[key]


def test_cell_15_reads_the_probability_of_a_loss_and_a_shortfall(lesson):
    loss, shortfall = lesson["cell 15"]
    paths = lesson["paths_outcome"]
    npvs = paths.table("unlevered_npv").column("unlevered_npv")
    shortfalls = paths.table("peak_shortfall").column("peak_shortfall")
    zero = rk.Quantity(text="0 AUD")
    assert loss == sum(1 for value in npvs if value < zero) / 3
    assert shortfall == sum(1 for value in shortfalls if value > zero) / 3


def test_cell_16_finds_the_case_at_the_5_percent_quantile(lesson):
    worst = lesson["worst"]
    assert isinstance(worst, Outcome)
    # With three cases the 5 % quantile is the lowest NPV: the weak case.
    assert worst is lesson["paths_outcome"].case(key="weak")
    assert worst["unlevered_npv"] == lesson["npv"].quantile(level=0.05)
