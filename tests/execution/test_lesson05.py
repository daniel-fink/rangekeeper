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
- ``stories``: cell 4 loads the three histories (#207). The test makes them on the
  Periods of lesson 04's ``rent_index``, from 2027, so the first check of cell 6 is on
  2028-01-01 and reads 2027. ADR-021's table reads a 2026 Period on 2027-01-01; #207
  settles this.
- Lesson 07's ``rk.io.load`` of lesson 05's strategy (#207).

Lesson 07's cell 18 calls ``alternatives`` (#244) and reads ``use_index["..."]``
(#284), so the test runs only its window and its rule on a Value of this Model.
"""

import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import rangekeeper as rk
from rangekeeper.schema.enums import PeriodTiming
from tests.execution import test_lesson04 as lesson04

ROOT = Path(__file__).resolve().parents[2]
LESSON_05 = ROOT / "examples/walkthrough/proposed/05_when_to_commit.md"
LESSON_07 = ROOT / "examples/walkthrough/proposed/07_policies_and_graph.md"
TRIGGERS = ("start_trigger", "b_start_trigger")
HISTORIES = {
    "early recovery": (
        1.06,
        1.12,
        1.15,
        1.16,
        1.16,
        1.16,
        1.16,
        1.16,
        1.16,
        1.16,
        1.16,
    ),
    "long downturn": (0.97, 0.95, 0.94, 0.93, 0.93, 0.93, 0.93, 0.93, 0.93, 0.93, 0.93),
    "short recovery": (0.97, 0.95, 1.06, 1.12, 1.04, 1.0, 0.98, 0.97, 0.96, 0.95, 0.95),
}


def cells(path: Path) -> dict[str, str]:
    """Return the numbered cells of a lesson."""
    numbered: dict[str, str] = {}
    for block in re.findall(r"```python\n(.*?)```", path.read_text(), re.S):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    return numbered


def run(namespace: dict, source: str) -> dict:
    """Run a cell as written, with ``parameters`` as ``fix`` until #301."""
    for code in lesson04.statements(source.replace(".parameters(", ".fix(")):
        exec(code, namespace)
    return namespace


def histories() -> rk.market.Paths:
    """Return three histories on the Periods of lesson 04's ``rent_index``."""
    years = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    return rk.market.Paths.from_flows(
        flows={
            key: {
                "rent_index": rk.flow.Flow.from_periods(
                    periods=years, magnitudes=list(index), units="ratio"
                )
            }
            for key, index in HISTORIES.items()
        }
    )


def lesson_inputs() -> tuple[rk.Model, rk.Specification]:
    """Return lesson 04's Model and base case, with the triggers of #301 in the Model."""
    helpers = SimpleNamespace(data_path=lambda *, name: lesson04.DATA / name)
    namespace: dict = {"rk": rk, "date": date, "helpers": helpers}
    lesson04.run(namespace, "2", "3", "3b")
    draft = namespace["model"].edit()
    project = draft.entity(code="project")
    for key in TRIGGERS:
        project.value(key=key, units="ratio")
    namespace["model"] = draft.commit()
    lesson04.run(namespace, "4")
    return namespace["model"], namespace["base"]


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run cells 6 to 12 of lesson 05 on three histories, without cell 8."""
    model, fixed = lesson_inputs()
    namespace: dict = {
        "rk": rk,
        "date": date,
        "model": model,
        "fixed": fixed,
        "stories": histories(),
    }
    written = cells(LESSON_05)
    for key in ("6", "7", "7b", "9", "10", "11", "11b", "12"):
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


def test_cell_6_solves_the_rule_on_each_history(lesson):
    outcome = lesson["wait_outcome"]
    table = outcome.table("start_date", "b_start", "equity_npv")
    assert table.column("start_date")[0] == date(2028, 1, 1)
    status = rk.execution.Status
    assert table.column("status") == (
        status.FEASIBLE,
        status.INFEASIBLE,
        status.INFEASIBLE,
    )


def test_cell_6_checks_when_each_index_is_known(lesson):
    """The histories start in 2027, so the first check is on 2028-01-01 (#207)."""
    trace = lesson["wait_outcome"].case(key="short recovery").trace
    assert [row.decision_date for row in trace] == [
        date(2028, 1, 1),
        date(2029, 1, 1),
        date(2030, 1, 1),
    ]
    assert [row.observed["rent_index"].number for row in trace] == [0.97, 0.95, 1.06]
    assert trace[-1].value == date(2030, 1, 1)


def test_cell_7_reads_the_trace_of_a_case_with_no_output(lesson):
    trace = lesson["downturn"].trace
    assert trace[-1].result is rk.execution.DecisionResult.OTHERWISE
    assert trace[-1].value is rk.duration.NEVER
    assert lesson["downturn"].run.rule_evidence.verified is False


def test_cell_7b_names_the_broken_constraint(lesson):
    status, diagnostics = lesson["downturn"].status, lesson["downturn"].diagnostics
    assert status is rk.execution.Status.INFEASIBLE
    broken = [item.values["equation"] for item in diagnostics if _breaks(item)]
    assert broken == ["b_start >= shared_start + 1 year"]


def _breaks(diagnostic) -> bool:
    return (
        diagnostic.severity == rk.run.Severity.ERROR
        and diagnostic.code == rk.errors.Code.CONSTRAINT_RESIDUAL.value
    )


def test_cell_11b_reads_the_decisions_of_each_history(lesson):
    outcome = lesson["stories_outcome"]
    keys = {row.case for row in outcome.decisions}
    assert keys == set(HISTORIES)
    downturn = outcome.case(key="long downturn")
    assert downturn.status is rk.execution.Status.FEASIBLE
    assert downturn["start_date"] is rk.duration.NEVER
    assert downturn["b_sale_date"] == date(2033, 1, 1)
    assert downturn.run.rule_evidence.verified is True


def test_cell_11b_solves_every_history(lesson):
    assert lesson["stories_outcome"].status is rk.execution.Status.FEASIBLE


@pytest.mark.parametrize(
    ("key", "start", "b_start", "sale"),
    [
        ("early recovery", date(2028, 1, 1), date(2029, 1, 1), rk.duration.NEVER),
        ("long downturn", rk.duration.NEVER, rk.duration.NEVER, date(2033, 1, 1)),
        ("short recovery", date(2030, 1, 1), date(2031, 1, 1), rk.duration.NEVER),
    ],
)
def test_cell_11b_decides_on_each_history(lesson, key, start, b_start, sale):
    case = lesson["stories_outcome"].case(key=key)
    assert (case["start_date"], case["b_start"], case["b_sale_date"]) == (
        start,
        b_start,
        sale,
    )
    assert case.run.rule_evidence.verified is True


def test_cell_10_has_a_site_sale_only_on_its_sale_date(lesson):
    """An unsold site has no sale; a sold site is 40 % of the land at the index of 2033."""
    outcome = lesson["stories_outcome"]
    for key in ("early recovery", "short recovery"):
        amounts = outcome.case(key=key)["b_site_sale"].movements
        assert not [movement for movement in amounts if movement.number]
    sold = outcome.case(key="long downturn")["b_site_sale"]
    ((period, amount),) = [
        (movement.period, movement.number)
        for movement in sold.movements
        if movement.number
    ]
    assert period.start == date(2033, 1, 1)
    assert amount == pytest.approx(0.4 * 20_000_000 * 0.93)


def test_cell_18_checks_the_strategy_on_the_lesson_model(lesson):
    """Cells 13 and 18, on the three histories of this test (#207)."""
    namespace = dict(lesson)
    namespace["paths"] = lesson["stories"]
    written = cells(LESSON_05)
    run(namespace, written["13"])
    exec(written["18"], namespace)


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


def test_lesson_07_cell_8b_solves_each_strategy(lesson):
    """Lesson 07's cell 8b, on the three histories; its switch waits on #244."""
    fixed = lesson["fixed"].on(model=lesson["model"]).fix(b_land_share="40 %")
    namespace = {
        "rk": rk,
        "fixed": fixed,
        "timing": lesson["strategy"].rules,
        "switch": fixed,
        "use_paths": lesson["stories"],
        "use_series": None,
    }
    written = cells(LESSON_07)
    exec(written["8"], namespace)
    exec(written["8b"], namespace)
    outcomes = namespace["strategy_outcomes"]
    assert list(outcomes) == ["fixed", "timing", "switch", "both"]
    assert {case.key for case in outcomes["timing"].cases} == set(HISTORIES)
    assert {row.key for row in outcomes["timing"].decisions} == set(
        lesson["strategy"].rules
    )
    assert outcomes["timing"].status is rk.execution.Status.FEASIBLE


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
