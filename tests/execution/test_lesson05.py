"""The rules of lessons 05 and 07 and a lookup of lesson 06, from the proposed cells.

The cells come from ``examples/walkthrough/proposed/05_when_to_commit.md`` and
``07_policies_and_graph.md``, and run statement by statement, as written. Cells 2 to 4
load the real documents of the data package. A call to another ``helpers`` function
only draws, so the test evaluates its arguments and does not call it. These differences
wait on other issues:

- Lesson 07's ``rk.io.load`` of lesson 05's strategy (#244).

Lesson 07's cell 18 calls ``alternatives`` (#302) and reads ``use_index["..."]``
(#284), so the test runs only its window and its rule on a Value of this Model.
Lesson 07's cell 17 includes a fragment (#302) and makes a Filter with labels
(#288), and cell 17b declares rollups (#285), so the test runs the first two
statements of cell 17, declares ``x_income`` and ``x_cost`` as values, and runs
cell 17c.

Lesson 06's cell 16 reads ``model.entities`` (#288), so the test runs only cell 17,
on a small Model with two entities of one name.
"""

import json
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
LESSON_06 = ROOT / "examples/walkthrough/proposed/06_project_structure.md"
LESSON_07 = ROOT / "examples/walkthrough/proposed/07_policies_and_graph.md"
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
# The data package's loan limit, which lessons 03 and 04 use.
LESSON_04_LIMIT = 65_000_000
# A history that starts the project and never reaches Building B's trigger, so it sells
# B's share of the site. None of the three histories does this.
UNBUILT = {"no second trigger": (1.06,) + (1.07,) * 10}


def cells(path: Path) -> dict[str, str]:
    """Return the numbered cells of a lesson."""
    numbered: dict[str, str] = {}
    for block in re.findall(r"```python\n(.*?)```", path.read_text(), re.S):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    return numbered


def run(namespace: dict, source: str) -> dict:
    """Run a cell as written."""
    for code in lesson04.statements(source):
        exec(code, namespace)
    return namespace


def histories(indexes: dict[str, tuple[float, ...]] = HISTORIES) -> rk.market.Paths:
    """Return histories on the Periods of lesson 04's ``rent_index``."""
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
            for key, index in indexes.items()
        }
    )


def _load_paths(*, name: str) -> rk.market.Paths:
    return rk.io.load(path=lesson04.DATA / name)


def _base_plan() -> dict[str, rk.Quantity]:
    content = json.loads((lesson04.DATA / "base_plan.json").read_text(encoding="utf-8"))
    item = content["values"]["loan_limit"]
    return {"loan_limit": rk.Quantity(magnitude=item["magnitude"], units=item["units"])}


HELPERS = SimpleNamespace(
    data_path=lambda *, name: lesson04.DATA / name,
    load_paths=_load_paths,
    load_base_plan=_base_plan,
)


@pytest.fixture(scope="module")
def lesson() -> dict:
    """Run cells 2 to 12 of lesson 05 on three histories, without cell 8."""
    namespace: dict = {"rk": rk, "date": date, "helpers": HELPERS}
    written = cells(LESSON_05)
    for key in (
        "2",
        "3",
        "3b",
        "4",
        "6",
        "7",
        "7b",
        "8b",
        "9",
        "10",
        "11",
        "11b",
        "12",
    ):
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
    assert downturn["b_sale_date"] is rk.duration.NEVER
    assert downturn.run.rule_evidence.verified is True


def test_cell_11b_solves_every_history(lesson):
    assert lesson["stories_outcome"].status is rk.execution.Status.FEASIBLE


@pytest.mark.parametrize(
    ("key", "start", "b_start", "sale"),
    [
        ("early recovery", date(2028, 1, 1), date(2029, 1, 1), rk.duration.NEVER),
        ("long downturn", rk.duration.NEVER, rk.duration.NEVER, rk.duration.NEVER),
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


@pytest.fixture(scope="module")
def unbuilt(lesson) -> rk.execution.Outcome:
    """Return the strategy on a history that starts and never starts Building B."""
    specification = lesson["strategy"].across(paths=histories(UNBUILT))
    return rk.execution.solve(specification=specification).case(key="no second trigger")


def test_cell_10_has_a_site_sale_only_on_its_sale_date(lesson, unbuilt):
    """An unsold site has no sale; a sold site is 40 % of the land at the index of 2033."""
    outcome = lesson["stories_outcome"]
    for key in HISTORIES:
        amounts = outcome.case(key=key)["b_site_sale"].movements
        assert not [movement for movement in amounts if movement.number]
    ((period, amount),) = [
        (movement.period, movement.number)
        for movement in unbuilt["b_site_sale"].movements
        if movement.number
    ]
    assert period.start == date(2033, 1, 1)
    assert amount == pytest.approx(0.4 * 20_000_000 * 1.07)


def test_cell_11_sells_no_site_that_the_project_never_bought(lesson):
    """The sale rule reads the start date as well: no land, so no sale."""
    case = lesson["stories_outcome"].case(key="long downturn")
    for key in ("land", "b_site_sale"):
        assert not [item for item in case[key].movements if item.number]
    assert case["equity_npv"].number == pytest.approx(0)


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
        "rent_index >= b_start_trigger and equity_available + loan_available "
        ">= b_cost + still_due"
    )


def test_cell_3b_raises_the_limit_of_this_lesson_only(lesson):
    fixed = lesson["fixed"]
    table = fixed.roles
    limits = dict(zip(table.column("key"), table.column("quantity"), strict=True))
    assert limits["loan_limit"].number == pytest.approx(90_000_000)
    stored = rk.io.load(path=lesson04.DATA / "04_base_case.specification.json")
    table = stored.roles
    limits = dict(zip(table.column("key"), table.column("quantity"), strict=True))
    assert limits["loan_limit"].number == pytest.approx(LESSON_04_LIMIT)


def test_cell_8b_counts_what_is_still_due(lesson):
    case = lesson["stories_outcome"].case(key="early recovery")
    due = {item.period.start.year: item.number for item in case["still_due"].movements}
    assert due[2027] == pytest.approx(0)
    # The project starts in 2028 and pays for the shared works in that year, so all of
    # Building A's budget is due at its end; Building A pays half in each of two years.
    a_budget = -case["a_works"].total().number
    assert due[2028] == pytest.approx(a_budget)
    assert due[2029] == pytest.approx(a_budget / 2)
    assert due[2030] == pytest.approx(0)


def test_cell_9_reads_the_funding_on_each_decision(lesson):
    decided = rk.execution.DecisionResult.DECIDED
    rows = lesson["stories_outcome"].decisions.where(key="b_start", result=decided)
    for row in rows:
        available = row.observed["equity_available"] + row.observed["loan_available"]
        assert (
            available.number
            >= (row.observed["b_cost"] + row.observed["still_due"]).number
        )
    assert len(list(rows)) == 2


def test_cell_11_reads_equality_with_two_equals_signs(lesson):
    strategy = lesson["strategy"]
    assert list(strategy.rules) == ["start_date", "b_start", "b_sale_date"]
    assert strategy.rules["b_sale_date"].condition == (
        "start_date != NEVER and b_start == NEVER"
    )
    stored = strategy.record.rules[-1]
    assert stored.earliest.date == stored.latest.date == date(2033, 1, 1)
    assert stored.otherwise.never is rk.duration.NEVER


def test_the_rules_survive_across_and_storage(lesson):
    strategy = lesson["strategy"]
    again = rk.Specification.from_data(strategy.to_data())
    assert again.record.rules == strategy.record.rules
    years = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    flow = rk.flow.Flow.from_periods(
        periods=years, magnitudes=[1.0] * len(years), units="ratio"
    )
    stories = rk.market.Paths.from_flows(flows={"one": {"rent_index": flow}})
    batch = strategy.across(paths=stories)
    case = batch.case(key="one")
    assert case.record.rules == strategy.record.rules


def test_lesson_07_reuses_the_rules_of_lesson_05(lesson):
    """Lesson 07's cells 7 and 8: each rule brings the triggers that it reads."""
    strategy = lesson["strategy"]
    fixed = lesson["fixed"].on(model=lesson["model"]).fix(b_land_share="40 %")
    timing = strategy.rules
    assert timing["start_date"].triggers["start_trigger"].number == pytest.approx(1.05)
    assert set(timing["b_start"].triggers) == {"b_start_trigger"}
    assert timing["b_sale_date"].triggers == {}
    namespace = {"fixed": fixed, "timing": timing, "switch": fixed}
    exec(cells(LESSON_07)["8"], namespace)
    timing_only = namespace["timing_only"]
    assert list(timing_only.rules) == ["start_date", "b_start", "b_sale_date"]
    assert timing_only.rules["b_start"].condition == strategy.rules["b_start"].condition
    table = timing_only.roles
    fixed_values = dict(zip(table.column("key"), table.column("quantity"), strict=True))
    assert fixed_values["start_trigger"].number == pytest.approx(1.05)
    assert fixed_values["b_start_trigger"].number == pytest.approx(1.10)


def test_lesson_05_cell_17_tests_several_triggers_on_every_path(lesson):
    """Cells 13, 17 and 17b: each trigger runs on every path, as a pair of keys."""
    namespace = dict(lesson)
    namespace["paths"] = lesson["stories"]
    written = cells(LESSON_05)
    for key in ("13", "17", "17b"):
        run(namespace, written[key])
    outcome = namespace["trigger_outcome"]
    triggers = list(namespace["start_triggers"])
    assert [case.key for case in outcome.cases] == triggers
    assert outcome.table("equity_npv").column("case") == tuple(
        f"{trigger}/{path}" for trigger in triggers for path in HISTORIES
    )
    # A trigger changes the decision on a path: the early recovery reads 1.06 on
    # 2028-01-01 and 1.12 on 2029-01-01.
    low, high = (
        outcome.case(key=trigger).case(key="early recovery")
        for trigger in ("1.05", "1.08")
    )
    assert (low["start_date"], high["start_date"]) == (
        date(2028, 1, 1),
        date(2029, 1, 1),
    )
    assert low.run.path_key == "early recovery"
    summary = namespace["trigger_difference"].by_case.summary()
    assert summary.column("case") == tuple(triggers)
    assert set(summary.column("count")) == {len(HISTORIES)}


def test_lesson_07_cell_8b_solves_each_strategy(lesson):
    """Lesson 07's cell 8b, on the three histories; its switch waits on #302."""
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
    stored = spec.record.rules[-1]
    assert tuple(stored.periods) == tuple(years)
    assert stored.timing is PeriodTiming.LAST
    assert spec.rules["b_start"].window.periods == tuple(years)


def test_cell_7b_raises_with_the_broken_constraint(lesson):
    with pytest.raises(rk.execution.OutcomeError) as error:
        lesson["downturn"].raise_for_status()
    assert error.value.status is rk.execution.Status.INFEASIBLE
    assert error.value.code is rk.errors.Code.CONSTRAINT_RESIDUAL
    assert error.value.equation == "b_start >= shared_start + 1 year"
    assert "b_start >= shared_start + 1 year" in str(error.value)


@pytest.fixture(scope="module")
def compared(lesson) -> dict:
    """Run cells 13, 14 and 16 on the three histories of this test (#207)."""
    namespace = {**lesson, "paths": lesson["stories"]}
    written = cells(LESSON_05)
    for key in ("13", "14", "14b", "14c", "14d", "14e", "16", "16b"):
        run(namespace, written[key])
    return namespace


def test_cell_13_fixes_a_date_and_never(compared):
    plan = compared["fixed_plan"]
    stored = plan.record.assignments
    assert [item.never for item in stored if item.never] == [rk.duration.NEVER]
    assert rk.Specification.from_data(plan.to_data()).record.assignments == stored
    for case in compared["fixed_outcome"].cases:
        assert case["start_date"] == date(2027, 1, 1)
        assert case["b_sale_date"] is rk.duration.NEVER
        assert not [item for item in case["b_site_sale"].movements if item.number]


def test_cell_14_pairs_the_strategy_with_the_fixed_plan_on_each_path(compared):
    summary = compared["difference"].summary()
    assert summary.column("key") == ("equity_npv", "peak_shortfall")
    assert summary.column("count") == (len(HISTORIES), len(HISTORIES))
    strategy, plan = compared["strategy_outcome"], compared["fixed_outcome"]
    paired = [
        strategy.case(key=key)["equity_npv"].number
        - plan.case(key=key)["equity_npv"].number
        for key in HISTORIES
    ]
    assert summary.column("mean")[0].number == pytest.approx(sum(paired) / len(paired))


def test_cell_16_reads_the_realised_dates(compared):
    dates = (date(2028, 1, 1), date(2030, 1, 1), rk.duration.NEVER)
    counts = compared["strategy_outcome"].distribution(key="start_date").counts()
    assert counts.column("value") == dates
    assert counts.column("count") == (1, 1, 1)
    summary = compared["difference"].by(key="start_date").summary()
    assert summary.column("start_date") == tuple(day for day in dates for _ in "ab")


def test_the_exercises_run_on_the_histories(compared):
    namespace = dict(compared)
    text = LESSON_05.read_text()
    for block in re.findall(r"```python\n(# solution.*?)```", text, re.S):
        run(namespace, block)
    assert namespace["early_outcome"].status is rk.execution.Status.FEASIBLE
    # Try it 2: at lesson 04's limit, each history that starts B has a commitment gap.
    assert namespace["reckless_outcome"].case(key="early recovery")[
        "loan_limit"
    ].number == pytest.approx(LESSON_04_LIMIT)
    assert namespace["gaps"].probability(above="0 AUD") == pytest.approx(2 / 3)
    unbuilt = namespace["cheap_difference"].where(b_start=rk.duration.NEVER).summary()
    assert unbuilt.column("count") == (1,)
    assert unbuilt.column("mean")[0].number == pytest.approx(
        namespace["cheap_site_outcome"].case(key="long downturn")["equity_npv"].number
        - compared["fixed_outcome"].case(key="long downturn")["equity_npv"].number
    )


def test_a_run_and_its_output_model_keep_the_decided_dates(lesson, unbuilt):
    case = lesson["stories_outcome"].case(key="long downturn")
    output = rk.Model.from_data(data=case.model.to_data())
    assert output.value(key="start_date").never is rk.duration.NEVER
    assert output.value(key="start_date").date is None
    sold = rk.Model.from_data(data=unbuilt.model.to_data())
    assert sold.value(key="b_sale_date").date == date(2033, 1, 1)
    again = rk.run.Run.from_data(case.run.to_data())
    assert again.to_data() == case.run.to_data()


@pytest.mark.parametrize("then", [date(2031, 1, 1), rk.duration.NEVER])
def test_a_rule_takes_a_date_or_never_as_its_values(lesson, then):
    window = rk.specification.Window(earliest=date(2028, 1, 1), latest=date(2030, 1, 1))
    rule = window.where(condition="rent_index >= 1.05").first(
        otherwise=date(2032, 1, 1), then=then
    )
    spec = lesson["strategy"].fix(b_sale_date=rule)
    stored = rk.Specification.from_data(spec.to_data())
    assert stored.record.rules == spec.record.rules
    outcome = rk.execution.solve(specification=spec.across(paths=lesson["stories"]))
    assert outcome.table("b_sale_date").column("b_sale_date") == (
        then,
        date(2032, 1, 1),
        then,
    )


def test_lesson_07_cell_7_loads_the_rules_of_lesson_05(lesson, tmp_path):
    path = tmp_path / "05_strategy.specification.json"
    rk.io.save(document=lesson["strategy"], path=path)
    helpers = SimpleNamespace(data_path=lambda *, name: tmp_path / name)
    namespace = run({"rk": rk, "helpers": helpers}, cells(LESSON_07)["7"])
    timing = namespace["timing"]
    assert list(timing) == ["start_date", "b_start", "b_sale_date"]
    assert timing["start_date"].triggers["start_trigger"].number == pytest.approx(1.05)
    assert timing["b_start"].window.earliest == "shared_start + 1 year"
    assert timing["b_sale_date"].otherwise is rk.duration.NEVER


@pytest.fixture(scope="module")
def expansion(lesson) -> rk.Specification:
    """Run lesson 07's cell 17c on lesson 05's Model and return the strategy on it."""
    written = cells(LESSON_07)
    namespace = {"rk": rk, "date": date, "residential": lesson["model"]}
    for code in lesson04.statements(written["17"])[:2]:
        exec(code, namespace)
    namespace["project"].value(key="x_income", units="AUD pa")
    namespace["project"].value(key="x_cost", units="AUD")
    run(namespace, written["17c"])
    return (
        lesson["strategy"]
        .on(model=namespace["expanded"])
        .fix(x_income="1e6 AUD pa", x_cost="5e6 AUD")
    )


def _early_recovery(spec, stories):
    outcome = rk.execution.solve(specification=spec.across(paths=stories))
    return outcome.case(key="early recovery")


def _changed(left: rk.flow.Flow, right: rk.flow.Flow) -> dict[int, float]:
    """Return the difference of two Flows in each year where they differ."""
    pairs = zip(left.movements, right.movements, strict=True)
    differences = {
        one.period.start.year: one.number - other.number for one, other in pairs
    }
    return {year: amount for year, amount in differences.items() if abs(amount) > 1e-6}


def test_lesson_07_cell_17c_solves_its_profiles_from_a_date(lesson, expansion):
    """Lesson 07's profiles start on a fixed date; on NEVER, they have no amounts."""
    stories = lesson["stories"]
    built = _early_recovery(expansion.fix(expansion_date=date(2032, 1, 1)), stories)
    unbuilt = _early_recovery(expansion.fix(expansion_date=rk.duration.NEVER), stories)
    assert built["x_open"] == date(2033, 1, 1)
    assert unbuilt["x_open"] is rk.duration.NEVER
    assert _changed(built["works"], unbuilt["works"]) == {2032: pytest.approx(-5e6)}
    assert _changed(built["income"], unbuilt["income"]) == {
        year: pytest.approx(1e6) for year in range(2033, 2038)
    }


def test_lesson_07_cell_17c_solves_its_profiles_from_a_rule(lesson, expansion):
    """Cell 18's window, on the index of this Model: a_open is 2031, so 2034 is first."""
    source = cells(LESSON_07)["18"]
    namespace: dict = {"rk": rk, "date": date}
    exec(source[: source.index("expansion_rule")], namespace)
    rule = (
        namespace["expansion_window"]
        .where(condition="rent_index >= expansion_trigger")
        .first(otherwise=rk.duration.NEVER)
    )
    spec = expansion.parameters(expansion_trigger=1.0).fix(expansion_date=rule)
    case = _early_recovery(spec, lesson["stories"])
    assert case["expansion_date"] == date(2034, 1, 1)
    assert case["x_open"] == date(2035, 1, 1)
    assert case.run.rule_evidence.verified is True


def test_lesson_06_cell_17_names_the_codes_of_a_lookup(capsys):
    draft = rk.Model(name="Project structure").edit()
    draft.add_entity(code="building_a", classification="building")
    for code in ("a_retail", "a_retail_2"):
        draft.add_entity(code=code, classification="floor", name="buildingAretail")
    run({"rk": rk, "model": draft.commit()}, cells(LESSON_06)["17"])
    assert capsys.readouterr().out == (
        "buildingAretail ('a_retail', 'a_retail_2')\nbuilding_c ('building_a',)\n"
    )
