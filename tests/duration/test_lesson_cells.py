"""The Span and Periods code of the proposed cells of lessons 03 to 07 runs (#272).

Each lesson makes its yearly Periods with ``Span(start=, end=).periods(frequency=)``
(cells 03·3, 04·3 and 05·10). The rest of cells 04·3 and 05·10 edits the Model
(#281), and the rule cells 05·6, 9, 11 and 07·7, 18 use ``Window``, which the
rule work owns (#300). These tests run the statements that make the Periods,
as the cells write them, and all of cell 03·3.
"""

import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk

PROPOSED = Path(__file__).resolve().parents[2] / "examples/walkthrough/proposed"
# The statement that makes the yearly Periods, from the Span to its closing bracket.
YEARS = re.compile(r"^years = rk\.duration\.Span\(.*?^\)$", re.S | re.M)


def cell(*, lesson: str, number: str) -> str:
    """Return the code of one numbered cell of a proposed lesson."""
    text = (PROPOSED / lesson).read_text()
    for block in re.findall(r"```python\n(.*?)```", text, re.S):
        if re.match(rf"# cell {number}\b", block):
            return block
    raise AssertionError(f"{lesson} has no cell {number}")


@pytest.mark.parametrize(
    ("lesson", "number"),
    [
        ("03_cases_debt_equity.md", "3"),
        ("04_market_futures.md", "3"),
        ("05_when_to_commit.md", "10"),
    ],
)
def test_the_cells_make_the_yearly_periods_of_the_plan(lesson, number):
    (statement,) = YEARS.findall(cell(lesson=lesson, number=number))
    namespace = {"rk": rk, "date": date, "yearly": rk.duration.Frequency.YEAR}
    exec(statement, namespace)
    years = namespace["years"]
    assert isinstance(years, rk.duration.Periods)
    assert len(years) == 11 and years.frequency is rk.duration.Frequency.YEAR
    assert years.span == rk.duration.Span(start=date(2027, 1, 1), length="11 years")
    assert years.containing(on=date(2031, 6, 30)) == years[4]
    assert years[-1] == rk.duration.Period(start=date(2037, 1, 1), end=date(2038, 1, 1))


def test_lesson_03_cell_3_runs_as_written_with_a_drawing_helper():
    """Cell 3 draws the plan's timeline with a helper, then makes the Periods."""
    drawn = []

    class Helpers:
        @staticmethod
        def show_timeline(*, of: object) -> None:
            drawn.append(of)

    plan = object()
    namespace = {"rk": rk, "date": date, "helpers": Helpers, "plan": plan}
    exec(cell(lesson="03_cases_debt_equity.md", number="3"), namespace)
    assert drawn == [plan]
    assert namespace["years"] == rk.duration.Periods(
        start=date(2027, 1, 1), frequency=rk.duration.Frequency.YEAR, count=11
    )
