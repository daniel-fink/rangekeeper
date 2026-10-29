"""The proposed cells of lesson 02 run as written, with equations in text.

The cells come from ``examples/walkthrough/proposed/02_front_door_back_door.md``.
The helper cells (1, 2, 2b, 7 and 14) and cell 3 are not run: they need the
walkthrough helpers and their data package. ``data`` holds the totals that
``helpers.load_property`` gives.
"""

import importlib.util
import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk
from rangekeeper.model.expression.text import render

LESSON = (
    Path(__file__).resolve().parents[2]
    / "examples/walkthrough/proposed/02_front_door_back_door.md"
)
# The cells that declare the Model and its equations.
MODEL_CELLS = ("4", "4b", "5", "6", "6b")
# The cells that investigate the Model; they need the execution extra.
SOLVE_CELLS = ("8", "9", "9b", "10", "10b", "11", "12", "13", "15", "16", "17")
OPTIONAL_CELLS = ("18", "19", "20", "21", "22")
EXECUTION = all(importlib.util.find_spec(name) for name in ("pyomo", "highspy"))


def q(text: str) -> rk.Quantity:
    return rk.Quantity(text=text)


DATA = {
    "works_cost": q("60e6 AUD"),
    "operating_cost": q("1.5e6 AUD pa"),
    "hotel_area": q("8000 sqm"),
    "hotel_rent": q("450 AUD per sqm pa"),
    "hotel_vacancy": q("0.25 ratio"),
    "residential_area": q("12000 sqm"),
    "residential_rent": q("520 AUD per sqm pa"),
    "residential_vacancy": q("0.04 ratio"),
    "retail_area": q("3000 sqm"),
    "retail_rent": q("700 AUD per sqm pa"),
    "retail_vacancy": q("0.08 ratio"),
}


def cells() -> tuple[dict[str, str], list[str]]:
    """Return the numbered cells of the lesson, and its exercise solutions."""
    numbered: dict[str, str] = {}
    solutions: list[str] = []
    for block in re.findall(r"```python\n(.*?)```", LESSON.read_text(), re.S):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
        elif block.startswith("# solution\n"):
            solutions.append(block)
    return numbered, solutions


def run(*keys: str) -> dict[str, object]:
    numbered, _ = cells()
    namespace: dict[str, object] = {"rk": rk, "date": date, "data": DATA}
    for key in keys:
        exec(numbered[key], namespace)
    return namespace


def test_the_model_cells_declare_the_equations_in_text():
    namespace = run(*MODEL_CELLS)
    model = namespace["model"]
    assert isinstance(model, rk.Model)
    project = model.entity(code="project")
    keys = {value.id: value.key for value in project.characteristics.values}
    (formulation,) = model.system.formulations
    assert formulation.code == "project"
    texts = [
        render(expression=expression, name=lambda target: keys[target.target])
        for expression in formulation.expressions
    ]
    assert texts == [
        "total_cost = land_cost + works_cost",
        "mortgage = leverage * total_cost",
        "debt_service = mortgage_constant * mortgage",
        "noi = coverage * debt_service",
        "effective_income = noi + operating_cost",
        "effective_income = rent_factor * reference_income",
        "reference_income = hotel_area * hotel_rent * (1 - hotel_vacancy)"
        " + residential_area * residential_rent * (1 - residential_vacancy)"
        " + retail_area * retail_rent * (1 - retail_vacancy)",
    ]
    assert len(formulation.constraints) == 7


@pytest.fixture(scope="module")
def investigated() -> dict[str, object]:
    """Return the names of the lesson after its solve and optional cells."""
    if not EXECUTION:
        pytest.skip("requires the optional execution extra")
    return run(*MODEL_CELLS, *SOLVE_CELLS, *OPTIONAL_CELLS)


def test_the_front_door_and_the_back_door_solve(investigated):
    # The same answers by hand, as in cell 3, with the mortgage constant of cell 9b.
    rate = investigated["constant"].to(units="1/year").number
    income = 8000 * 450 * 0.75 + 12000 * 520 * 0.96 + 3000 * 700 * 0.92
    front = (1.25 * rate * 0.65 * (20e6 + 60e6) + 1.5e6) / income
    back = (income - 1.5e6) / 1.25 / rate / 0.65 - 60e6
    lower = (income - 1.5e6) / 1.25 / rate / 0.50 - 60e6
    factor = investigated["front_outcome"]["rent_factor"]
    land = investigated["back_outcome"]["land_cost"]
    assert (factor.units, land.units) == ("ratio", "AUD")
    assert factor.number == pytest.approx(front, rel=1e-9)
    assert land.number == pytest.approx(back, rel=1e-9)
    lowered = investigated["lower_leverage_outcome"]["land_cost"]
    assert lowered.number == pytest.approx(lower, rel=1e-9)


def test_the_optional_cells_and_the_solutions_run(investigated):
    (diagnostic, *_) = investigated["both_free_outcome"].diagnostics
    assert diagnostic.values["equation"] == "noi = coverage * debt_service"
    _, solutions = cells()
    namespace = dict(investigated)
    for solution in solutions:
        exec(solution, namespace)
