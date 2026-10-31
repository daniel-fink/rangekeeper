"""Lesson 04's market paths, from the proposed cells (#206, #296, #298, #299, #306).

The cells come from ``examples/walkthrough/proposed/04_market_futures.md``
and run statement by statement, as written. A call to ``helpers`` only draws,
so the test evaluates its arguments and does not call it. Cells 2 and 4 load the
real documents of the data package; ``helpers.data_path`` here gives their path.

``COUNT``: cell 8 reads the path count from ``RK_PATH_COUNT``. The lesson CI runs
4 paths. This test runs 40, which reaches ``path_37``, where the equity gets nothing
back. At 500 paths the lesson takes about 100 minutes (#523), so no test runs them.
"""

import ast
import math
import os
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import rangekeeper as rk
from rangekeeper.execution import Distribution, Paired, Status
from rangekeeper.shared.table import Table

ROOT = Path(__file__).resolve().parents[2]
LESSON = ROOT / "examples/walkthrough/proposed/04_market_futures.md"
DATA = ROOT / "examples/data/mixed_use_property"
# The path count of cell 8 in this test.
COUNT = 40
# The values that cell 14 compares.
COMPARED = ("unlevered_npv", "equity_npv", "peak_shortfall", "commitment_gap")


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
        for code in statements(numbered[key]):
            exec(code, namespace)
    return namespace


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run cells 2 to 8 and 10 to 19 of lesson 04, with their solves."""
    helpers = SimpleNamespace(data_path=lambda *, name: DATA / name)
    namespace: dict = {"rk": rk, "date": date, "os": os, "helpers": helpers}
    keys = ("2", "3", "3b", "4", "5", "6", "7", "8", "10", "11")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("RK_PATH_COUNT", str(COUNT))
        return run(namespace, *keys, "12", "13", "14", "15", "16", "17", "18", "19")


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


def test_cell_11_keeps_a_path_where_the_equity_gets_nothing_back(lesson):
    """``equity_irr`` left the Model in cell 3b, so this path does not fail the batch."""
    case = lesson["paths_outcome"].case(key="path_37")
    received = [
        movement
        for movement in case["equity_cash_flow"].movements
        if movement.number > 1
    ]
    assert received == []
    assert case["equity_npv"] == min(
        lesson["paths_outcome"].distribution(key="equity_npv").values
    )


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
    # The flaw of averages: no loss on the average path, but a loss on some paths.
    zero = rk.Quantity(text="0 AUD")
    assert lesson["average_outcome"]["unlevered_npv"] > zero
    assert 0 < lesson["npv"].probability(below="0 AUD") < 1


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
    for key in COMPARED:
        (difference,) = comparison.difference(outcome="Mean of paths", key=key)
        assert difference == mean[key] - average[key]


def test_cell_15_reads_the_shares_of_paths_with_a_loss_and_a_shortfall(lesson):
    loss, equity_loss, shortfall = evaluate(lesson, "15")
    table = lesson["paths_outcome"].table(
        "unlevered_npv", "equity_npv", "peak_shortfall"
    )
    zero = rk.Quantity(text="0 AUD")
    npvs = table.column("unlevered_npv")
    equities = table.column("equity_npv")
    shortfalls = table.column("peak_shortfall")
    assert loss == sum(1 for value in npvs if value < zero) / COUNT
    assert equity_loss == sum(1 for value in equities if value < zero) / COUNT
    assert shortfall == sum(1 for value in shortfalls if value > zero) / COUNT
    # The narrative: each path has a shortfall, and so does the average path, so this
    # share cannot show the flaw of averages.
    assert shortfall == 1
    assert lesson["average_outcome"]["peak_shortfall"] > zero


def test_cell_16_finds_the_path_at_the_5_percent_quantile(lesson):
    worst = lesson["worst"]
    npv = lesson["npv"]
    assert worst in lesson["paths_outcome"].cases
    assert worst["unlevered_npv"] == npv.quantile(level=0.05)
    # No more than 5 % of the paths have a lower NPV, and some do at this count.
    lower = [value for value in npv.values if value < worst["unlevered_npv"]]
    assert 0 < len(lower) / COUNT <= 0.05
    # The helper draws these Flows. ``committed`` comes from lesson 03's
    # optional cell 21, which the loaded Model has.
    for key in ("equity_available", "loan_available", "committed"):
        assert isinstance(worst[key], rk.flow.Flow)


def test_section_7_the_unlevered_npv_is_linear_in_the_rent_index(lesson):
    """The narrative: the mean of the NPVs is the NPV on the mean path."""
    assert rk.quantity.isclose(
        actual=lesson["npv"].mean(),
        expected=lesson["average_outcome"]["unlevered_npv"],
        relative=1e-12,
    )


def test_section_7_equity_and_funding_differ_only_slightly(lesson):
    """The narrative: each difference is small against the value on the average path."""
    mean = lesson["paths_outcome"].mean()
    average = lesson["average_outcome"]
    equity = mean["equity_npv"] - average["equity_npv"]
    # Leverage is not linear in the market, so at this count the equity NPV differs.
    assert equity.number != 0
    assert abs(equity.number) < 0.05 * abs(average["equity_npv"].number)
    for key in ("peak_shortfall", "commitment_gap"):
        difference = mean[key] - average[key]
        assert abs(difference.number) < 0.05 * average[key].number


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
    for removed in ("rent_growth", "equity_irr"):
        with pytest.raises(rk.errors.MissingReferenceError):
            model.value(key=removed)
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
