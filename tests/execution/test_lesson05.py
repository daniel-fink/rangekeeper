"""The rules of lessons 05 and 07, from the proposed cells (#300).

The cells come from ``examples/walkthrough/proposed/05_when_to_commit.md`` and
``07_policies_and_graph.md``, and run statement by statement, as written. A call
to ``helpers`` only draws, so the test evaluates its arguments and does not call
it. These differences wait on other issues:

- ``lesson_model`` and ``plan``: lesson 05 loads lesson 04's Model and base case
  (cells 2 and 3, ``rk.io.load``, #207). The test runs lesson 04's cells.
- ``parameters``: ``fixed.parameters(start_trigger=1.05)`` is #301. The test
  declares each trigger as a Model Value and fixes it, so the statement runs as
  ``fix``.
- ``WAITING``: the statements that solve (the next step of #300), and lesson 07's
  ``rk.io.load`` of lesson 05's strategy (#207).

Lesson 07's cell 18 calls ``alternatives`` (#244) and reads ``use_index["..."]``
(#284), so the test runs only its window and its rule on a Value of this Model.
"""

import ast
import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk
from rangekeeper.schema.enums import PeriodTiming
from tests.execution import test_lesson04 as lesson04

ROOT = Path(__file__).resolve().parents[2]
LESSON_05 = ROOT / "examples/walkthrough/proposed/05_when_to_commit.md"
LESSON_07 = ROOT / "examples/walkthrough/proposed/07_policies_and_graph.md"
TRIGGERS = ("start_trigger", "b_start_trigger")
# The statements of a cell that wait on the next step of #300.
WAITING = {
    "6": (
        "wait_outcome = rk.execution.solve(specification=wait.across(paths=stories))",
        'wait_outcome.table("start_date", "b_start", "equity_npv")',
    ),
}


def cells(path: Path) -> dict[str, str]:
    """Return the numbered cells of a lesson."""
    numbered: dict[str, str] = {}
    for block in re.findall(r"```python\n(.*?)```", path.read_text(), re.S):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    return numbered


def run(namespace: dict, source: str, *, waiting: tuple[str, ...] = ()) -> dict:
    """Run a cell as written, with ``parameters`` as ``fix`` until #301."""
    skipped = {ast.unparse(ast.parse(text)) for text in waiting}
    for code in lesson04.statements(source.replace(".parameters(", ".fix(")):
        if code not in skipped:
            exec(code, namespace)
    return namespace


def lesson_inputs() -> tuple[rk.Model, rk.Specification]:
    """Return lesson 04's Model and base case, with the triggers of #301 in the Model."""
    earlier = lesson04.lesson03_model()
    namespace: dict = {"rk": rk, "date": date, "model": earlier}
    for key in ("3", "3b"):
        exec(lesson04.cells()[key], namespace)
    draft = namespace["model"].edit()
    project = draft.entity(code="project")
    for key in TRIGGERS:
        project.value(key=key, units="ratio")
    model = draft.commit()
    return model, lesson04.base_case(earlier).free("rent_growth").on(model=model)


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run cells 6, 9, 10 and 11 of lesson 05, without their solves."""
    model, fixed = lesson_inputs()
    namespace: dict = {"rk": rk, "date": date, "model": model, "fixed": fixed}
    written = cells(LESSON_05)
    run(namespace, written["6"], waiting=WAITING["6"])
    for key in ("9", "10", "11"):
        run(namespace, written[key])
    return namespace


def test_cell_6_fixes_the_start_date_with_a_rule(lesson):
    wait = lesson["wait"]
    assert list(wait.rules) == ["start_date"]
    roles = dict(zip(wait.roles.column("key"), wait.roles.column("role"), strict=True))
    assert roles["start_date"] is rk.specification.Role.DECIDED
    assert wait.record.assignments is not None
    rule = wait.rules["start_date"]
    assert rule.condition == "rent_index >= start_trigger"
    assert rule.window.earliest == date(2027, 1, 1)
    assert rule.window.latest == date(2030, 1, 1)
    assert rule.otherwise is rk.duration.NEVER


def test_cell_8_rejects_a_look_ahead_at_fix(lesson):
    namespace = dict(lesson)
    written = cells(LESSON_05)["8"]
    printed: list[tuple] = []
    namespace["print"] = lambda *values: printed.append(values)
    exec(written, namespace)
    ((code, key, available_on, decision_date),) = printed
    assert code is rk.errors.Code.OBSERVATION_UNAVAILABLE
    assert key == "start_date"
    assert available_on is None and decision_date is None


def test_cell_9_adds_a_rule_with_an_expression_bound(lesson):
    start_b = lesson["start_b"]
    assert list(start_b.rules) == ["start_date", "b_start"]
    rule = start_b.rules["b_start"]
    assert rule.window.earliest == "shared_start + 1 year"
    assert rule.condition == (
        "rent_index >= b_start_trigger and equity_available + loan_available >= b_cost"
    )


def test_cell_11_reads_equality_with_two_equals_signs(lesson):
    strategy = lesson["strategy"]
    assert list(strategy.rules) == ["start_date", "b_start", "b_sale_date"]
    assert strategy.rules["b_sale_date"].condition == "b_start == NEVER"
    stored = strategy.record.declared_rules[-1]
    assert stored.earliest.date == stored.latest.date == date(2033, 1, 1)
    assert stored.otherwise.never is rk.duration.NEVER


def test_the_rules_survive_across_and_storage(lesson):
    strategy = lesson["strategy"]
    again = rk.Specification.from_data(strategy.to_data())
    assert again.record.declared_rules == strategy.record.declared_rules
    years = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    flow = rk.flow.Flow.from_periods(
        periods=years, magnitudes=[1.0] * len(years), units="ratio"
    )
    stories = rk.market.Paths.from_flows(flows={"one": {"rent_index": flow}})
    batch = strategy.across(paths=stories)
    case = batch.case(key="one")
    assert case.record.declared_rules == strategy.record.declared_rules


def test_lesson_07_reuses_the_rules_of_lesson_05(lesson):
    """Lesson 07's cells 7 and 8: each rule brings the triggers that it reads."""
    strategy = lesson["strategy"]
    fixed = lesson["fixed"].on(model=lesson["model"]).fix(b_land_share="40 %")
    timing = strategy.rules
    assert timing["start_date"].triggers["start_trigger"].number == pytest.approx(1.05)
    assert timing["b_start"].triggers["b_cost"] is not None
    namespace = {"fixed": fixed, "timing": timing, "switch": fixed}
    exec(cells(LESSON_07)["8"], namespace)
    timing_only = namespace["timing_only"]
    assert list(timing_only.rules) == ["start_date", "b_start", "b_sale_date"]
    assert timing_only.rules["b_start"].condition == strategy.rules["b_start"].condition
    table = timing_only.roles
    fixed_values = dict(zip(table.column("key"), table.column("quantity"), strict=True))
    assert fixed_values["start_trigger"].number == pytest.approx(1.05)
    assert fixed_values["b_start_trigger"].number == pytest.approx(1.10)


def test_lesson_07_cell_18_window_and_rule(lesson):
    """Lesson 07's cell 18, with a window bound on ``a_open`` and the Model's index."""
    source = cells(LESSON_07)["18"]
    window = source[: source.index("expansion_rule")]
    namespace: dict = {"rk": rk, "date": date}
    exec(window, namespace)
    rule = (
        namespace["expansion_window"]
        .where(condition="rent_index >= 1.25")
        .first(otherwise=rk.duration.NEVER)
    )
    spec = lesson["strategy"].fix(sale_date=rule)
    assert spec.rules["sale_date"].window.earliest == "a_open + 3 years"


def test_a_window_with_periods_keeps_its_calendar(lesson):
    years = rk.duration.Span(start=date(2030, 1, 1), end=date(2033, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    window = rk.specification.Window(periods=years, timing=PeriodTiming.LAST)
    rule = window.where(condition="rent_index >= 1").first(otherwise=date(2033, 1, 1))
    spec = lesson["wait"].fix(b_start=rule)
    stored = spec.record.declared_rules[-1]
    assert tuple(stored.periods) == tuple(years)
    assert stored.timing is PeriodTiming.LAST
    assert spec.rules["b_start"].window.periods == tuple(years)
