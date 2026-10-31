"""Specification parameters and cases across paths (ADR-021, ADR-014, #301).

The Model is small, and lesson 07's cells 13 to 15 run as written on it. Their
Model needs ``alternatives`` (#302) and keyed values (#284), so here the rule of
``both`` reads ``rent_index`` and decides a date. Lesson 05's cell 17 runs on the
lesson Model in ``tests/execution/test_lesson05.py``.
"""

import re
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.duration import NEVER, Frequency, Span
from rangekeeper.errors import AvailabilityError, Code
from rangekeeper.execution import ExecutionConfig, solve
from rangekeeper.shared.errors import (
    ContractError,
    EquationError,
    UnitError,
    ValidationError,
)
from rangekeeper.specification import Specification, Window
from rangekeeper.specification.rule._query import parameter_id
from tests.execution.test_lesson04 import statements
from tests.execution.test_parallel import comparable, started  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]
LESSON_07 = ROOT / "examples/walkthrough/proposed/07_policies_and_graph.md"
YEARS = Span(start=date(2027, 1, 1), end=date(2033, 1, 1)).periods(
    frequency=Frequency.YEAR
)
WINDOW = Window(earliest=date(2028, 1, 1), latest=date(2032, 1, 1))
INDEX = {
    "up": (1.02, 1.08, 1.12, 1.16, 1.2, 1.24),
    "late": (0.95, 0.98, 1.0, 1.04, 1.12, 1.2),
    "flat": (1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
}


def small_model() -> rk.Model:
    draft = rk.Model(name="Parameters").edit()
    project = draft.add_entity(code="project", classification="project")
    project.flow(key="rent_index", units="ratio", periods=YEARS)
    project.date(key="start")
    project.date(key="second")
    project.value(key="provision", units="AUD")
    project.value(key="income", units="AUD")
    project.value(key="free_input", units="ratio")
    project.value(key="equity_npv", units="AUD")
    project.equations("equity_npv = income - provision")
    return draft.commit()


def market(*, keys: tuple[str, ...] = tuple(INDEX)) -> rk.market.Paths:
    return rk.market.Paths.from_flows(
        flows={
            key: {
                "rent_index": rk.flow.Flow.from_periods(
                    periods=YEARS, magnitudes=list(INDEX[key]), units="ratio"
                )
            }
            for key in keys
        }
    )


def waiting(condition: str = "rent_index >= trigger"):
    return WINDOW.where(condition=condition).first(otherwise=NEVER)


def base() -> Specification:
    return (
        small_model()
        .specify(name="Base")
        .fix(provision="0 AUD", income="100 AUD", second=date(2033, 1, 1))
    )


def strategy() -> Specification:
    return base().parameters(trigger=1.05).fix(start=waiting())


def stored(spec: Specification) -> dict[str, float]:
    return {item.key: item.quantity.number for item in spec.record.parameters or ()}


# Declaring and changing


def test_parameters_declare_values_that_a_rule_reads_by_key():
    spec = strategy()
    assert stored(spec) == {"trigger": pytest.approx(1.05)}
    assert spec.rules["start"].condition == "rent_index >= trigger"
    assert spec.rules["start"].triggers["trigger"].number == pytest.approx(1.05)
    reference = spec.record.rules[0].condition.operands[1].target.target
    assert reference == parameter_id("trigger")


def test_each_call_returns_a_new_specification():
    first = base()
    second = first.parameters(trigger=1.05)
    assert not first.record.parameters
    assert second.id != first.id
    assert second.metadata.previous == first.id


def test_a_parameter_takes_a_quantity_text_or_a_number():
    spec = base().parameters(
        ratio=1.05, text="2 AUD", quantity=rk.Quantity(text="3 AUD")
    )
    units = {item.key: item.quantity.units for item in spec.record.parameters}
    assert units == {"ratio": "ratio", "text": "AUD", "quantity": "AUD"}
    with pytest.raises(TypeError):
        base().parameters(when=date(2030, 1, 1))
    with pytest.raises(TypeError, match="at least one"):
        base().parameters()


def test_fix_and_parameters_change_a_parameter_in_its_position():
    spec = base().parameters(one=1.0, two=2.0)
    for changed in (spec.fix(one=1.5), spec.parameters(one=1.5)):
        assert list(stored(changed)) == ["one", "two"]
        assert stored(changed)["one"] == pytest.approx(1.5)
    assert spec.fix(one=1.0) is spec


def test_a_changed_parameter_keeps_units_that_convert():
    spec = base().parameters(level="2 AUD")
    with pytest.raises(UnitError):
        spec.fix(level=1.5)
    with pytest.raises(UnitError):
        spec.parameters(level="2 m")


def test_a_parameter_cannot_have_the_key_of_a_model_value():
    with pytest.raises(ContractError) as raised:
        base().parameters(free_input=1.0)
    assert raised.value.code is Code.UNIQUE
    assert raised.value.values["keys"] == ["free_input"]


def test_on_keeps_the_parameters_and_refuses_a_key_of_the_new_model():
    spec = strategy()
    draft = spec.model.edit()
    draft.entity(code="project").value(key="other", units="ratio")
    moved = spec.on(model=draft.commit())
    assert stored(moved) == stored(spec)
    assert moved.rules["start"].condition == "rent_index >= trigger"
    draft = spec.model.edit()
    draft.entity(code="project").value(key="trigger", units="ratio")
    with pytest.raises(ContractError) as raised:
        spec.on(model=draft.commit())
    assert raised.value.code is Code.UNIQUE


def test_the_roles_show_a_parameter_as_fixed():
    table = strategy().roles
    row = next(row for row in table.rows if row.values["key"] == "trigger")
    assert row.values["role"] is rk.specification.Role.FIXED
    assert row.values["quantity"].number == pytest.approx(1.05)
    assert row.id == parameter_id("trigger")


def test_a_path_case_and_a_batch_refuse_parameters():
    batch = strategy().across(paths=market())
    with pytest.raises(ContractError) as raised:
        batch.parameters(trigger=1.0)
    assert raised.value.code is Code.BATCH_UNSUPPORTED
    with pytest.raises(ContractError, match="across"):
        batch.case(key="up").parameters(trigger=1.0)


def test_parameters_survive_storage():
    spec = strategy()
    again = Specification.from_data(spec.to_data())
    assert again.record.parameters == spec.record.parameters
    assert spec.to_data()["parameters"] == [
        {
            "key": "trigger",
            "quantity": spec.record.parameters[0].quantity.to_data(),
        }
    ]


def test_a_rule_reuses_its_parameters_in_another_specification():
    rule = strategy().rules["start"]
    other = base().fix(start=rule)
    assert stored(other) == {"trigger": pytest.approx(1.05)}
    # A parameter that the other Specification declares stays.
    mine = base().parameters(trigger=2.0).fix(start=rule)
    assert stored(mine) == {"trigger": pytest.approx(2.0)}
    # A value in the same call as the rule is the value of the parameter.
    given = base().fix(trigger=1.5, start=rule)
    assert stored(given) == {"trigger": pytest.approx(1.5)}


def test_a_window_bound_reads_a_parameter():
    spec = base().parameters(lag="1 year")
    rule = (
        Window(earliest="second - lag", latest=date(2033, 1, 1))
        .where(condition="rent_index >= 1")
        .first(otherwise=NEVER)
    )
    made = spec.fix(start=rule)
    assert made.rules["start"].window.earliest == "second - lag"
    assert set(made.rules["start"].triggers) == {"lag"}


def test_includes_compose_parameters_and_own_them():
    shared = base().parameters(trigger=1.05)
    store = rk.io.MemoryStore()
    store.put(shared.model)
    store.put(shared)
    data = {
        "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
        "model": str(shared.model.id),
        "includes": [str(shared.id)],
    }
    child = Specification(
        record=rk.specification.SpecificationRecord.from_data(data),
        model=shared.model,
        resolver=store,
    )
    assert stored_composed(child) == {"trigger": pytest.approx(1.05)}
    with pytest.raises(ContractError, match="included"):
        child.fix(trigger=1.0)
    with pytest.raises(ContractError, match="included"):
        child.parameters(trigger=1.0)


def stored_composed(spec: Specification) -> dict[str, float]:
    requirements = spec.compose(resolver=spec.resolver).requirements
    return {item.key: item.quantity.number for item in requirements.parameters or ()}


def test_two_contributors_cannot_declare_one_parameter():
    one, two = (base().parameters(trigger=value) for value in (1.0, 2.0))
    store = rk.io.MemoryStore()
    store.put(one.model)
    data = {
        "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
        "model": str(one.model.id),
        "includes": [str(one.id), str(two.id)],
    }
    store.put(one)
    store.put(two)
    root = Specification.from_data(data)
    with pytest.raises(ValidationError, match=r"parameters\.trigger"):
        root.compose(resolver=store)


# fix raises for a condition on a parameter (ADR-021, acceptance item 2)


def test_a_look_ahead_on_a_parameter_raises_availability_error():
    rule = waiting("rent_index.shift(by=-1) >= trigger")
    with pytest.raises(AvailabilityError) as raised:
        base().parameters(trigger=1.05).fix(start=rule)
    assert raised.value.key == "start"
    assert raised.value.code is Code.OBSERVATION_UNAVAILABLE


def test_a_condition_on_a_parameter_and_a_later_rule_raises_rule_order():
    rule = waiting("rent_index >= trigger and second == NEVER")
    spec = base().parameters(trigger=1.05).fix(start=rule)
    with pytest.raises(ValidationError) as raised:
        # ``second`` is then decided after ``start``, which reads it.
        spec.fix(second=waiting())
    assert raised.value.report.issues[0].code is Code.RULE_ORDER


def test_a_condition_on_a_parameter_and_a_free_input_raises_rule_reads_unknown():
    rule = waiting("rent_index >= trigger and free_input >= 1")
    with pytest.raises(ValidationError) as raised:
        base().parameters(trigger=1.05).fix(start=rule)
    assert raised.value.report.issues[0].code is Code.RULE_READS_UNKNOWN


def test_a_condition_on_a_name_that_nothing_declares_raises_equation_error():
    with pytest.raises(EquationError, match="trigger"):
        base().fix(start=waiting())


def test_freeing_a_parameter_that_a_rule_reads_raises_rule_reads_unknown():
    with pytest.raises(ValidationError) as raised:
        strategy().free("trigger")
    assert raised.value.report.issues[0].code is Code.RULE_READS_UNKNOWN
    unread = base().parameters(unused=1.0, other=2.0).free("unused")
    assert list(stored(unread)) == ["other"]


def test_a_stored_rule_that_reads_a_missing_parameter_fails_validation():
    spec = strategy()
    data = spec.to_data()
    del data["parameters"]
    data["metadata"]["id"] = str(uuid4())
    del data["metadata"]["previous"]
    broken = Specification.from_data(data)
    store = rk.io.MemoryStore()
    store.put(spec.model)
    report = broken.validate(resolver=store)
    assert "does not declare" in report.issues[0].message
    assert report.issues[0].code is Code.RULE_READS_UNKNOWN


# The solve reads parameters, in every process


def decisions(outcome: rk.execution.Outcome) -> list[tuple]:
    """Return the rule, the case, the date, the result and the value of each check."""
    return [
        (row.case, row.key, row.decision_date, row.result, row.value)
        for row in outcome.decisions
    ]


def test_a_case_varies_a_trigger_without_a_model_revision():
    cases = strategy().cases(
        cases={"low": {"trigger": 1.05}, "high": {"trigger": 1.15}}
    )
    outcome = solve(specification=cases.across(paths=market())).raise_for_status()
    revisions = {leaf.run.record.specification for leaf in outcome._leaves()}
    assert len(revisions) == 6
    assert {
        document.record.model
        for document in (cases.case(key="low"), cases.case(key="high"))
    } == {cases.record.model}
    assert (
        outcome.case(key="low").case(key="up")["start"],
        outcome.case(key="high").case(key="up")["start"],
    ) == (date(2029, 1, 1), date(2031, 1, 1))
    assert outcome.case(key="high").case(key="flat")["start"] is NEVER


def test_the_trace_observes_the_parameter_and_the_stored_trace_holds():
    outcome = solve(specification=strategy().across(paths=market())).raise_for_status()
    case = outcome.case(key="up")
    assert case.trace[0].observed["trigger"].number == pytest.approx(1.05)
    assert case.run.rule_evidence.verified is True
    store = rk.io.MemoryStore()
    stored_outcome = rk.execution.execute(
        specification=strategy().across(paths=market()), store=store
    )
    run = store.load_run(stored_outcome.run.id)
    assert rk.run.validate(run=run, resolver=store).valid


def test_a_changed_parameter_fails_the_stored_trace_check():
    outcome = solve(specification=strategy().across(paths=market()))
    leaf = outcome.case(key="up")
    other = strategy().fix(trigger=1.5)
    from rangekeeper.run._rule.stored import check_stored
    from rangekeeper.shared.errors import DecisionError

    paths = market()
    case = other.across(paths=paths).case(key="up")
    requirements = case.compose(resolver=rk.io.MemoryStore()).requirements
    with pytest.raises(DecisionError) as raised:
        check_stored(
            leaf.run.rule_evidence,
            requirements=requirements,
            candidate=leaf.model,
            paths=paths,
            units=leaf.model.unit_system,
        )
    assert raised.value.code is Code.RULE_TRACE


@pytest.mark.parametrize("workers", [2, 3])
def test_worker_processes_give_equal_decisions_and_traces(started, workers):  # noqa: F811
    keys = {str(index): (1.0 + index / 20) for index in range(4)}
    batch = (
        strategy()
        .cases(cases={key: {"trigger": value} for key, value in keys.items()})
        .across(paths=market())
    )
    alone = solve(specification=batch, config=ExecutionConfig(workers=1))
    assert started == []
    together = solve(specification=batch, config=ExecutionConfig(workers=workers))
    assert started
    assert decisions(together) == decisions(alone)
    assert decisions(alone)
    for one, other in zip(alone._leaves(), together._leaves(), strict=True):
        assert one.run.rule_evidence == other.run.rule_evidence
        assert one.run.path_key == other.run.path_key
    assert comparable(together) == comparable(alone)


# Cases across paths


def trigger_cases() -> Specification:
    return strategy().cases(
        cases={"1.05": {"trigger": 1.05}, "1.15": {"trigger": 1.15}}
    )


def test_across_a_batch_makes_one_case_for_each_pair():
    paths = market()
    batch = trigger_cases().across(paths=paths)
    assert [batch.case(key=key).metadata.name for key in ("1.05", "1.15")] == [
        "1.05",
        "1.15",
    ]
    leaf = batch.case(key="1.15").case(key="late")
    assert leaf.record.path.key == "late"
    assert leaf.record.path.paths == paths.id
    assert stored(leaf)["trigger"] == pytest.approx(1.15)


def test_a_batch_keeps_its_name_and_its_model_across_paths():
    batch = trigger_cases()
    across = batch.across(paths=market())
    assert across.metadata.name == batch.metadata.name
    assert across.record.model == batch.record.model
    assert across.metadata.previous == batch.id


def test_a_batch_across_paths_cannot_go_across_again():
    twice = trigger_cases().across(paths=market())
    with pytest.raises(ContractError) as raised:
        twice.across(paths=market())
    assert raised.value.code is Code.BATCH_UNSUPPORTED


def test_series_reach_each_case():
    market_index = rk.market.Paths.from_flows(
        flows={
            "up": {
                "market_index": rk.flow.Flow.from_periods(
                    periods=YEARS, magnitudes=list(INDEX["up"]), units="ratio"
                )
            }
        }
    )
    batch = trigger_cases().across(
        paths=market_index, series={"rent_index": "market_index"}
    )
    outcome = solve(specification=batch).raise_for_status()
    assert outcome.case(key="1.05").case(key="up")["start"] == date(2029, 1, 1)


def test_runs_record_the_path_key_of_each_case():
    paths = market()
    outcome = solve(specification=trigger_cases().across(paths=paths))
    assert outcome.run.path_key is None
    assert outcome.run.paths == paths.id
    for case in outcome.cases:
        assert case.run.path_key is None
        assert case.run.paths == paths.id
        assert [leaf.run.path_key for leaf in case.cases] == list(paths.keys)
        assert [leaf.key for leaf in case.cases] == list(paths.keys)


def test_a_case_without_a_path_records_no_path_key():
    outcome = solve(specification=base().fix(start=date(2030, 1, 1)))
    assert outcome.run.path_key is None and outcome.run.paths is None


def test_execute_stores_the_pairs_and_validates_the_path_key():
    store = rk.io.MemoryStore()
    outcome = rk.execution.execute(
        specification=trigger_cases().across(paths=market()), store=store
    )
    leaf = outcome.case(key="1.15").case(key="up")
    run = store.load_run(leaf.run.id)
    assert run.path_key == "up"
    assert rk.run.validate(run=run, resolver=store).valid
    data = run.to_data()
    data["path_key"] = "late"
    data["metadata"]["id"] = str(uuid4())
    other = rk.Run.from_data(data)
    report = rk.run.validate(run=other, resolver=store)
    assert not report.valid


def test_pairs_read_the_path_key_from_the_run():
    """A case named otherwise pairs by its path, because the Run records the path."""
    paths = market()
    timing = solve(specification=strategy().across(paths=paths))
    found = solve(specification=trigger_cases().across(paths=paths))
    pairs = rk.execution.compare(
        outcomes={"Triggers": found, "Timing": timing},
        keys=["equity_npv"],
        baseline="Timing",
    ).pairs(outcome="Triggers")
    assert [pair.case for pair in pairs] == [
        f"{case}/{path}" for case in ("1.05", "1.15") for path in paths.keys
    ]
    assert [pair.baseline.run.path_key for pair in pairs] == [
        pair.member.run.path_key for pair in pairs
    ]


# Lesson 07's cells 13 to 15, as written


def cells() -> dict[str, str]:
    numbered: dict[str, str] = {}
    for block in re.findall(r"```python\n(.*?)```", LESSON_07.read_text(), re.S):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    return numbered


def run(namespace: dict, source: str) -> None:
    for code in statements(source):
        exec(code, namespace)


@pytest.fixture(scope="module")
def lesson_07() -> dict:
    """Run lesson 07's cells 8b's outcomes on the small Model, then cells 13 to 15."""
    timing = base().parameters(trigger=1.05).fix(start=waiting())
    both = (
        base()
        .fix(provision="2.5e6 AUD")
        .parameters(switch_trigger=1.10)
        .fix(start=waiting("rent_index >= switch_trigger"))
    )
    use_paths = market()
    namespace: dict = {
        "rk": rk,
        "strategies": {"timing": timing, "both": both},
        "strategy_outcomes": {
            "timing": solve(specification=timing.across(paths=use_paths))
        },
        "use_paths": use_paths,
        "use_series": None,
    }
    written = cells()
    for key in ("13", "13b", "14", "14b", "15", "15b"):
        run(namespace, written[key])
    # Cell 15c's first statement. Its last line reads ``order_by`` of a by-case
    # table, which waits on #310.
    source = written["15c"]
    run(namespace, source[: source.index("by_trigger = ")])
    return namespace


def test_cell_14_finds_the_largest_premium_from_two_runs(lesson_07):
    """The provision lowers the NPV dollar for dollar: the premium is the mean gain."""
    premium = lesson_07["largest_premium"]
    mean = lesson_07["gain_at_zero"].mean()
    assert premium.number == pytest.approx(mean.number)
    assert premium.units == "AUD"


def test_cell_14b_checks_the_premium(lesson_07):
    check = lesson_07["check"].distribution(outcome="At largest", key="equity_npv")
    assert check.mean().number == pytest.approx(0, abs=1e-6)


def test_cell_15b_makes_one_case_for_each_trigger(lesson_07):
    cases = lesson_07["trigger_cases"]
    keys = list(lesson_07["switch_triggers"])
    assert [cases.case(key=key).metadata.name for key in keys] == keys


def test_cell_15c_runs_each_trigger_on_every_path(lesson_07):
    outcome = lesson_07["train_outcome"]
    assert outcome.status is rk.execution.Status.FEASIBLE
    assert [case.key for case in outcome.cases] == list(lesson_07["switch_triggers"])
    by_trigger = rk.execution.compare(
        outcomes={
            "Triggers": outcome,
            "Timing": lesson_07["strategy_outcomes"]["timing"],
        },
        keys=["equity_npv"],
        baseline="Timing",
    ).by_case
    summary = by_trigger.summary()
    assert summary.column("case") == tuple(lesson_07["switch_triggers"])
    assert set(summary.column("count")) == {len(INDEX)}


def test_cell_16_solves_the_chosen_case_on_other_paths(lesson_07):
    """Cell 16, without ``regenerate`` and ``order_by``: a case of a batch moves paths."""
    fresh = market(keys=("up", "flat"))
    chosen = lesson_07["trigger_cases"].case(key="1.05")
    outcome = solve(specification=chosen.across(paths=fresh)).raise_for_status()
    assert [case.key for case in outcome.cases] == ["up", "flat"]
