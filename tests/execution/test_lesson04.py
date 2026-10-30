"""Lesson 04's market paths, from the proposed cells (#298, #299).

The cells come from ``examples/walkthrough/proposed/04_market_futures.md``
and run statement by statement, as written. A call to ``helpers`` only draws,
so the test evaluates its arguments and does not call it. These differences
wait on other issues:

- ``lesson_model`` and ``base_case``: lesson 04 loads lesson 03's Model and
  base case (cells 2 and 4, ``rk.io.load``, #295) and edits the Model (cells
  3 and 3b, ``replace`` and ``remove``, #283). The test runs lesson 03's
  cells with lesson 04's changes, and fixes the base case from ``PLAN``.
- ``COUNT``: cell 8 is tagged "parameters", so the test runs it with fewer
  paths, as the lesson CI does.
"""

import ast
import math
import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk
from rangekeeper.execution import Status
from tests.execution.test_lesson03 import PLAN
from tests.walkthrough import test_proposed_lesson_03 as lesson03

LESSON = (
    Path(__file__).resolve().parents[2]
    / "examples/walkthrough/proposed/04_market_futures.md"
)
# Lesson 04's cells 3 and 3b, as changes to lesson 03's cells: one rent index
# carries the market, the rents are flat and the Model has no rent growth.
CHANGES = {
    "5b": (('project.value(key="rent_growth", units="% pa")\n', ""),),
    "5c": (
        (
            'project.flow(key="sale", units="AUD", periods=years)\n',
            'project.flow(key="sale", units="AUD", periods=years)\n'
            'project.flow(key="rent_index", units="ratio", periods=years)\n',
        ),
    ),
    "7": (
        (
            "rx.profile.compounding(initial=a_income, rate=rent_growth, start=a_open)",
            "rx.profile.constant(initial=a_income, start=a_open)",
        ),
        (
            "rx.profile.compounding(initial=b_income, rate=rent_growth, start=b_open)",
            "rx.profile.constant(initial=b_income, start=b_open)",
        ),
        ('"income = a_rent + b_rent"', '"income = rent_index * (a_rent + b_rent)"'),
    ),
}
LESSON_03_CELLS = ("3", "5", "5b", "5c", "6", "7", "7b", "8", "12", "12b", "18")
# The path count of cell 8 in this test.
COUNT = 4


def cells() -> dict[str, str]:
    """Return the numbered cells of the lesson."""
    numbered: dict[str, str] = {}
    for block in re.findall(r"```python\n(.*?)```", LESSON.read_text(), re.S):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    return numbered


def statements(source: str) -> list[str]:
    """Return the statements of a cell; a ``helpers`` call gives its arguments."""
    found = []
    for statement in ast.parse(source).body:
        call = getattr(statement, "value", None)
        if (
            isinstance(statement, ast.Expr)
            and isinstance(call, ast.Call)
            and ast.unparse(call.func).startswith("helpers.")
        ):
            found.extend(ast.unparse(keyword.value) for keyword in call.keywords)
        else:
            found.append(ast.unparse(statement))
    return found


def run(namespace: dict, *keys: str) -> dict:
    """Run cells of lesson 04 as written, statement by statement."""
    numbered = cells()
    for key in keys:
        source = numbered[key]
        if key == "8":
            source = source.replace("count = 500", f"count = {COUNT}")
        for code in statements(source):
            exec(code, namespace)
    return namespace


def lesson_model() -> rk.Model:
    """Return lesson 04's Model: lesson 03's Model with the rent index (cells 3, 3b)."""
    numbered = lesson03.cells()
    namespace: dict = {"rk": rk, "date": date, "plan": PLAN}
    for key in LESSON_03_CELLS:
        source = numbered[key]
        for old, new in CHANGES.get(key, ()):
            assert old in source, (key, old)
            source = source.replace(old, new)
        for code in statements(source):
            if not code.startswith("model.entity"):
                exec(code, namespace)
    return namespace["model"]


def years() -> rk.duration.Periods:
    """Return the Periods of lesson 04's cell 3."""
    return rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )


def base_case(model: rk.Model) -> rk.Specification:
    """Return lesson 03's base case without rent growth, on lesson 04's Model (cell 4)."""
    return (
        model.specify(name="Base case")
        .fix(base_date=PLAN["base_date"], sale_date=PLAN["sale_date"])
        .fix(start_date=PLAN["start_date"], b_start=PLAN["b_start"])
        .fix(land_cost=PLAN["land_cost"], shared_cost=PLAN["shared_cost"])
        .fix(a_cost=PLAN["a_cost"], b_cost=PLAN["b_cost"])
        .fix(a_income=PLAN["a_income"], b_income=PLAN["b_income"])
        .fix(a_opex=PLAN["a_opex"], b_opex=PLAN["b_opex"])
        .fix(a_renewal=PLAN["a_renewal"], b_renewal=PLAN["b_renewal"])
        .fix(exit_cap_rate="5 %", discount_rate="7 % pa", opex_growth="3.5 % pa")
        .fix(equity=PLAN["equity"], loan_limit=PLAN["loan_limit"])
        .fix(loan_rate="6 % pa", equity_rate="12 % pa")
    )


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run cells 5 to 8, 10, 17 and 18 of lesson 04, with their solves."""
    model = lesson_model()
    namespace: dict = {
        "rk": rk,
        "date": date,
        "model": model,
        "yearly": rk.duration.Frequency.YEAR,
        "years": years(),
        "base": base_case(model),
    }
    return run(namespace, "5", "6", "7", "8", "10", "17", "18")


def test_cells_5_to_7_add_one_component_at_a_time(lesson):
    count = len(lesson["years"])
    (key,) = lesson["one_path"].keys
    index = lesson["one_path"][key]["rent_index"]
    assert [m.number for m in index.movements] == pytest.approx(
        [1.02**i * (1 + 0.1 * math.sin(2 * math.pi * i / 10)) for i in range(count)]
    )
    five = lesson["five_paths"]
    assert len(five) == 5 and five.capture.seed == 1
    assert five.keys[0] != five.keys[1]
    assert five[five.keys[0]]["rent_index"] != five[five.keys[1]]["rent_index"]
    with pytest.raises(rk.errors.ContractError, match="needs a seed"):
        rk.market.generate(
            dynamics={"rent_index": lesson["dynamics"]},
            periods=lesson["years"],
            count=5,
        )


def test_cell_8_captures_the_paths(lesson):
    paths = lesson["paths"]
    assert len(paths) == COUNT
    capture = paths.capture
    assert (capture.generator, capture.seed, capture.count) == ("dynamics", 1, COUNT)
    assert paths.regenerate(seed=1) == paths


def test_cells_17_and_18_make_independent_series(lesson):
    use_paths = lesson["use_paths"]
    assert use_paths.names == (
        "market_index",
        "hotel_factor",
        "residential_factor",
        "retail_factor",
    )
    path = lesson["path"]
    assert path.key == use_paths.keys[0]
    hotel = path["market_index"] * path["hotel_factor"]
    assert rk.quantity.default_units.compatible(hotel.units, "ratio")
    assert len(hotel.movements) == len(lesson["years"])
    assert path["market_index"] != path["hotel_factor"]


def test_the_model_carries_the_market_in_one_rent_index():
    model = lesson_model()
    assert model.value(key="rent_index").flow is not None
    with pytest.raises(rk.errors.MissingReferenceError):
        model.value(key="rent_growth")


def test_cell_10_values_the_plan_on_the_mean_path(lesson):
    outcome = lesson["average_outcome"]
    assert outcome.status is Status.FEASIBLE
    mean = lesson["paths"].mean(name="rent_index")
    assert outcome["rent_index"] == mean
    cash = outcome["net_cash_flow"]
    assert rk.quantity.isclose(
        actual=outcome["unlevered_npv"],
        expected=rk.finance.npv(flow=cash, rate="7 % pa", on=date(2027, 1, 1)),
        relative=1e-9,
    )
