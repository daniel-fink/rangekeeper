"""Lesson 04's market paths, from the proposed cells (#296, #298, #299, #306).

The cells come from ``examples/walkthrough/proposed/04_market_futures.md``
and run statement by statement, as written. A call to ``helpers`` only draws,
so the test evaluates its arguments and does not call it. These differences
wait on other issues:

- ``lesson03_model`` and ``base_case``: lesson 04 loads lesson 03's Model and
  base case (cells 2 and 4, ``rk.io.load``, #295). The test runs lesson 03's
  cells for the Model and fixes the base case from ``PLAN``; cells 3 and 3b
  then edit the Model, and cell 4 moves the base case, as written.
- ``COUNT``: cell 8 is tagged "parameters", so the test runs it with fewer
  paths, as the lesson CI does.
- ``WAITING``: cell 4's ``rk.io.load`` of the base case (#295).

One statement does not hold as written:

- ``HELD``: cell 19's check of the flaw of averages,
  ``npv.mean() != average_outcome["unlevered_npv"]``. The unlevered NPV is
  linear in the rent index, so the mean of the paths' NPVs is the NPV on the
  mean path (``test_the_unlevered_npv_has_no_flaw_of_averages``). The lesson
  must choose another check; the test runs the rest of the cell.
"""

import ast
import math
import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk
from rangekeeper.execution import Distribution, Paired, Status
from rangekeeper.shared.table import Table
from tests.execution.test_lesson03 import PLAN
from tests.walkthrough import test_proposed_lesson_03 as lesson03

LESSON = (
    Path(__file__).resolve().parents[2]
    / "examples/walkthrough/proposed/04_market_futures.md"
)
LESSON_03_CELLS = ("3", "5", "5b", "5c", "6", "7", "7b", "8", "12", "12b", "18")
# The path count of cell 8 in this test.
COUNT = 4
# The statements of a cell that wait on cells that this test does not run yet.
WAITING = {
    "4": (
        'base = rk.io.load(path=helpers.data_path(name="03_base_case.specification.json"))',
    ),
}
# The statements of a cell that do not hold as written.
HELD = {
    "19": ('assert npv.mean() != average_outcome["unlevered_npv"]',),
}


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
            skipped = WAITING.get(key, ()) + HELD.get(key, ())
            if code not in {ast.unparse(ast.parse(text)) for text in skipped}:
                exec(code, namespace)
    return namespace


def lesson03_model() -> rk.Model:
    """Return lesson 03's Model, from its cells (03_base_plan.model.json, cell 2)."""
    numbered = lesson03.cells()
    namespace: dict = {"rk": rk, "date": date, "plan": PLAN}
    for key in LESSON_03_CELLS:
        for code in statements(numbered[key]):
            if not code.startswith("model.entity"):
                exec(code, namespace)
    return namespace["model"]


def base_case(model: rk.Model) -> rk.Specification:
    """Return lesson 03's base case (03_base_case.specification.json, cell 4)."""
    return (
        model.specify(name="Base case")
        .fix(base_date=PLAN["base_date"], sale_date=PLAN["sale_date"])
        .fix(start_date=PLAN["start_date"], b_start=PLAN["b_start"])
        .fix(land_cost=PLAN["land_cost"], shared_cost=PLAN["shared_cost"])
        .fix(a_cost=PLAN["a_cost"], b_cost=PLAN["b_cost"])
        .fix(a_income=PLAN["a_income"], b_income=PLAN["b_income"])
        .fix(shared_opex=PLAN["shared_opex"], a_opex=PLAN["a_opex"])
        .fix(b_opex=PLAN["b_opex"], shared_renewal=PLAN["shared_renewal"])
        .fix(a_renewal=PLAN["a_renewal"], b_renewal=PLAN["b_renewal"])
        .fix(exit_cap_rate="5 %", discount_rate="7 % pa", opex_growth="3.5 % pa")
        .fix(equity=PLAN["equity"], loan_limit=PLAN["loan_limit"])
        .fix(loan_rate="6 % pa", equity_rate="12 % pa")
        .fix(rent_growth="3 % pa")
    )


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run cells 3 to 8 and 10 to 19 of lesson 04, with their solves."""
    model = lesson03_model()
    namespace: dict = {"rk": rk, "date": date, "model": model}
    namespace["base"] = base_case(model)
    cells = ("3", "3b", "4", "5", "6", "7", "8", "10", "11")
    return run(namespace, *cells, "12", "13", "14", "15", "16", "17", "18", "19")


def evaluate(lesson: dict, key: str) -> object:
    """Return the value of a cell's last statement, an expression, as written."""
    return eval(statements(cells()[key])[-1], lesson)


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


def test_cell_11_solves_the_plan_across_the_paths(lesson):
    outcome = lesson["paths_outcome"]
    paths = lesson["paths"]
    assert outcome.status is Status.FEASIBLE
    assert [case.key for case in outcome.cases] == list(paths.keys)
    assert outcome.run.paths == paths.id
    table = outcome.table("unlevered_npv", "equity_npv", "peak_shortfall")
    head = table.head()
    assert head.columns == table.columns and len(head.rows) == min(5, COUNT)
    npvs = {row.values["unlevered_npv"].number for row in table.rows}
    assert len(npvs) == COUNT  # each path gives its own result


def test_cell_19_checks_the_cases_and_the_pinned_paths(lesson):
    paths = lesson["paths"]
    first = lesson["first"]
    case = lesson["paths_outcome"].case(key=first)
    assert case.run.paths == paths.id
    assert case["rent_index"] == paths[first]["rent_index"]


def test_cell_12_summarises_the_npv_across_the_paths(lesson):
    npv = lesson["npv"]
    assert isinstance(npv, Distribution)
    table = lesson["paths_outcome"].table("unlevered_npv")
    assert list(npv.values) == list(table.column("unlevered_npv"))
    summary = evaluate(lesson, "12")
    assert isinstance(summary, Table)
    (row,) = summary.rows
    assert row.values["count"] == COUNT
    assert row.values["minimum"] <= row.values["quantile_05"]
    assert row.values["quantile_95"] <= row.values["maximum"]
    assert row.values["mean"] == npv.mean()


def test_cell_14_compares_the_mean_of_the_paths_with_the_average_path(lesson):
    comparison = evaluate(lesson, "14")
    assert isinstance(comparison, Paired)
    mean = lesson["paths_outcome"].mean()
    average = lesson["average_outcome"]
    for key in ("unlevered_npv", "equity_npv", "peak_shortfall"):
        (difference,) = comparison.difference(outcome="Mean of paths", key=key)
        assert difference == mean[key] - average[key]


def test_cell_15_reads_the_probability_of_a_loss_and_a_shortfall(lesson):
    loss, shortfall = evaluate(lesson, "15")
    table = lesson["paths_outcome"].table("unlevered_npv", "peak_shortfall")
    zero = rk.Quantity(text="0 AUD")
    npvs = table.column("unlevered_npv")
    shortfalls = table.column("peak_shortfall")
    assert loss == sum(1 for value in npvs if value < zero) / COUNT
    assert shortfall == sum(1 for value in shortfalls if value > zero) / COUNT


def test_cell_16_finds_the_path_at_the_5_percent_quantile(lesson):
    worst = lesson["worst"]
    npv = lesson["npv"]
    assert worst in lesson["paths_outcome"].cases
    assert worst["unlevered_npv"] == npv.quantile(level=0.05)
    # With four paths the 5 % quantile is the lowest NPV.
    assert worst["unlevered_npv"] == min(npv.values)
    # The helper draws these Flows. ``committed`` comes from lesson 03's
    # optional cell 21, which ``lesson_model`` does not run.
    for key in ("equity_available", "loan_available"):
        assert isinstance(worst[key], rk.flow.Flow)


def test_the_unlevered_npv_has_no_flaw_of_averages(lesson):
    """The unlevered NPV is linear in the rent index: cell 19's check is held."""
    assert rk.quantity.isclose(
        actual=lesson["npv"].mean(),
        expected=lesson["average_outcome"]["unlevered_npv"],
        relative=1e-12,
    )


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


def test_cells_3_to_4_carry_the_market_in_one_rent_index(lesson):
    model = lesson["model"]
    assert model.value(key="rent_index").flow is not None
    with pytest.raises(rk.errors.MissingReferenceError):
        model.value(key="rent_growth")
    (income,) = model.equations.where(key="income")
    assert income.text == "income = rent_index * (a_rent + b_rent)"
    base = lesson["base"]
    assert base.model_id == model.id
    keys = {row.values["key"] for row in base.roles.rows}
    assert "rent_growth" not in keys and "rent_index" in keys


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
