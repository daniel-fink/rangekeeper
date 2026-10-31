"""The evaluation order of ADR-021, step by step, and the trace check (#215).

Each expected date and result here is read from the small table of rent indices in
``INDEX``, not from the engine. The backend is forbidden unless a test says
otherwise, so a rule set that reads only path values proves that it needs no solve.
"""

import pickle
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.errors import (
    AvailabilityError,
    Code,
    ContractError,
    DecisionError,
)
from rangekeeper.execution.attempt import Attempt
from rangekeeper.execution.backends.base import BackendResult, Termination
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.pipeline import Pinned
from rangekeeper.execution.planning import resolve_cases
from rangekeeper.execution.preparation import bind_roles, validate
from rangekeeper.execution.rule.sequence import Decisions, Solver, run_rules
from rangekeeper.execution.settings import Limits
from rangekeeper.execution.status import Status
from rangekeeper.market.paths import Paths
from rangekeeper.run._rule.availability import path_amounts, path_known
from rangekeeper.run._rule.result import DecisionResult
from rangekeeper.run._rule.trace import Check, Reading, TraceFacts, check_trace
from rangekeeper.schema.records import Expression, ExpressionKind
from rangekeeper.specification.rule._query import RuleQuery, parse_text
from tests.execution.rule.test_sequential_verification import PARAMETERS, attempts

NEVER = rk.duration.NEVER
YEARS = rk.duration.Span(start=date(2026, 1, 1), end=date(2031, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)
# The rent index of each year, known on 1 January of the next year.
INDEX = (1.00, 1.01, 1.02, 1.20, 1.21)
DECIDED, NOT_MET, SKIPPED, OTHERWISE = (
    DecisionResult.DECIDED,
    DecisionResult.NOT_MET,
    DecisionResult.SKIPPED,
    DecisionResult.OTHERWISE,
)


class Forbidden:
    """A backend for rule sets that must not solve."""

    def solve(self, *, problem, limits, remaining, options):
        raise AssertionError("this rule set needs no provisional solve")


def small_model(*extra: str) -> rk.Model:
    draft = rk.Model(name="Small").edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("first", "second", "third"):
        project.date(key=key)
    project.value(key="level", units="ratio")
    project.value(key="price", units="AUD")
    project.flow(key="rent_index", units="ratio", periods=YEARS)
    project.flow(key="spend", units="AUD", periods=YEARS)
    project.equations(
        "spend = rx.flow.event(amount=price, on=first)",
        "after_first = first + 1 year",
        *extra,
    )
    return draft.commit()


def bound(model: rk.Model, **fixes):
    paths = Paths.from_flows(
        flows={
            "only": {
                "rent_index": rk.flow.Flow.from_periods(
                    periods=YEARS, magnitudes=list(INDEX), units="ratio"
                )
            }
        }
    )
    specification = (
        model.specify(name="Case").fix(price="10 AUD", **fixes).across(paths=paths)
    )
    cases = resolve_cases(specification=specification, resolver=Pinned(specification))
    leaf = cases.documents[specification.record.cases[0]]
    composition = cases.compositions[leaf.id]
    validation = validate(composition=composition, resolver=cases)
    return leaf, cases, bind_roles(validation=validation), paths


def on(day: date) -> Expression:
    return Expression(id=uuid4(), kind=ExpressionKind.DATE, date=day)


def rule(model, key, condition, **fields) -> RuleQuery:
    fields.setdefault("otherwise", NEVER)
    return RuleQuery(
        target=model.value(key=key).id,
        condition=parse_text(text=condition, model=model),
        **fields,
    )


def run(model, *declared, backend=None, **fixes) -> Decisions:
    _, _, binding, paths = bound(model, **fixes)
    return run_rules(
        binding=binding,
        rules=declared,
        paths=paths,
        solver=Solver(
            backend=Forbidden() if backend is None else backend,
            config=ExecutionConfig(),
            limits=Limits(),
        ),
    )


def table(decisions: Decisions, key: str) -> list[tuple[date, DecisionResult]]:
    return [(c.on, c.result) for c in decisions.checks if c.key == key]


def test_rules_on_one_date_run_in_the_written_order():
    """The first rule's decision on a date is what the second rule reads there."""
    model = small_model()
    decisions = run(
        model,
        rule(model, "first", "rent_index >= 1.20"),
        rule(model, "second", "first != NEVER", earliest=on(date(2030, 1, 1))),
    )
    # 1.20 is the index of 2029, known on 2030-01-01.
    assert decisions.decided[model.value(key="first").id].on == date(2030, 1, 1)
    assert [c.key for c in decisions.checks if c.on == date(2030, 1, 1)] == [
        "first",
        "second",
    ]
    assert decisions.decided[model.value(key="second").id].value == date(2030, 1, 1)
    assert decisions.solves == 0


def test_the_last_window_date_passing_when_the_rule_runs():
    """``otherwise`` falls on the next date of the calendar after ``latest``."""
    model = small_model()
    decisions = run(
        model,
        rule(
            model,
            "first",
            "rent_index >= 2",
            earliest=on(date(2027, 1, 1)),
            latest=on(date(2028, 1, 1)),
        ),
    )
    assert table(decisions, "first") == [
        (date(2027, 1, 1), NOT_MET),
        (date(2028, 1, 1), NOT_MET),
        (date(2029, 1, 1), OTHERWISE),
    ]


def test_a_calendar_that_ends_takes_otherwise_on_its_last_date():
    """The index of 2030 is the last that the path gives: 2031-01-01 is its date."""
    model = small_model()
    decisions = run(model, rule(model, "first", "rent_index >= 2"))
    assert table(decisions, "first")[-2:] == [
        (date(2031, 1, 1), NOT_MET),
        (date(2031, 1, 1), OTHERWISE),
    ]


def test_an_earliest_bound_that_becomes_never_closes_the_window_after_the_date():
    model = small_model()
    decisions = run(
        model,
        rule(model, "first", "rent_index >= 2", latest=on(date(2027, 1, 1))),
        rule(
            model, "second", "rent_index >= 0", earliest=_text(model, "first + 1 year")
        ),
    )
    # The first rule passes on 2028-01-01. Then the second rule's bound is NEVER.
    assert table(decisions, "first") == [
        (date(2027, 1, 1), NOT_MET),
        (date(2028, 1, 1), OTHERWISE),
    ]
    assert table(decisions, "second") == [
        (date(2027, 1, 1), SKIPPED),
        (date(2028, 1, 1), SKIPPED),
        (date(2028, 1, 1), OTHERWISE),
    ]


def test_an_undecided_earliest_keeps_the_window_closed():
    model = small_model()
    decisions = run(
        model,
        rule(model, "first", "rent_index >= 1.20"),
        rule(
            model, "second", "rent_index >= 0", earliest=_text(model, "first + 1 year")
        ),
    )
    # The first rule decides on 2030-01-01; the second opens a year later.
    assert table(decisions, "second") == [
        (date(2027, 1, 1), SKIPPED),
        (date(2028, 1, 1), SKIPPED),
        (date(2029, 1, 1), SKIPPED),
        (date(2030, 1, 1), SKIPPED),
        (date(2031, 1, 1), DECIDED),
    ]


def test_an_undecided_latest_keeps_the_window_open():
    model = small_model()
    decisions = run(
        model,
        rule(model, "second", "rent_index >= 1.21", latest=_text(model, "first")),
        rule(model, "first", "rent_index >= 1.20"),
    )
    # ``first`` is undecided until 2030-01-01, so 2027 to 2030 are open. Then its
    # value bounds the window, and 2031-01-01 has passed it.
    assert table(decisions, "second") == [
        (date(2027, 1, 1), NOT_MET),
        (date(2028, 1, 1), NOT_MET),
        (date(2029, 1, 1), NOT_MET),
        (date(2030, 1, 1), NOT_MET),
        (date(2031, 1, 1), OTHERWISE),
    ]


@pytest.mark.parametrize(
    ("condition", "truth", "result"),
    [
        ("first != NEVER", None, NOT_MET),
        ("not (first = NEVER)", None, NOT_MET),
        ("rent_index >= 0 and (first = NEVER)", None, NOT_MET),
        ("rent_index >= 2 and (first = NEVER)", False, NOT_MET),
        ("rent_index >= 0 or (first = NEVER)", True, DECIDED),
    ],
)
def test_a_reference_to_an_undecided_value_is_unknown(condition, truth, result):
    """Unknown is not true; logic decides what it can without the unknown value."""
    model = small_model()
    decisions = run(
        model,
        rule(model, "first", "rent_index >= 1.20"),
        rule(
            model,
            "second",
            condition,
            earliest=on(date(2027, 1, 1)),
            latest=on(date(2027, 1, 1)),
        ),
    )
    check = next(c for c in decisions.checks if c.key == "second")
    assert (check.on, check.condition, check.result) == (
        date(2027, 1, 1),
        truth,
        result,
    )
    readings = {r.name: r for r in check.readings}
    if "first" in readings:
        assert readings["first"].value is None


def test_a_rule_with_periods_acts_on_their_days_and_ends_at_their_end():
    model = small_model()
    months = rk.duration.Span(start=date(2029, 1, 1), end=date(2030, 1, 1)).periods(
        frequency=rk.duration.Frequency.QUARTER
    )
    first = rule(model, "first", "rent_index >= 2", periods=months)
    decisions = run(model, first)
    assert table(decisions, "first") == [
        (date(2029, 1, 1), NOT_MET),
        (date(2029, 4, 1), NOT_MET),
        (date(2029, 7, 1), NOT_MET),
        (date(2029, 10, 1), NOT_MET),
        (date(2030, 1, 1), OTHERWISE),
    ]
    # On 2029-07-01 the rule reads the index of 2028, the latest that is known.
    read = decisions.checks[2].readings[0]
    assert read.value.number == 1.02
    assert read.available_on == date(2029, 1, 1)


def test_periods_timing_moves_the_window_date():
    model = small_model()
    first = rule(
        model,
        "first",
        "rent_index >= 1.02",
        periods=YEARS[2:],
        timing=rk.duration.PeriodTiming.LAST,
    )
    decisions = run(model, first)
    # 2028-12-31 reads the index of 2027, 1.01; 2029-12-31 reads 2028, 1.02.
    assert table(decisions, "first") == [
        (date(2028, 12, 31), NOT_MET),
        (date(2029, 12, 31), DECIDED),
    ]


def test_a_shift_reads_the_movement_before():
    model = small_model()
    decisions = run(
        model,
        rule(
            model,
            "first",
            "rent_index.shift(by=1) >= 1.20",
            earliest=on(date(2028, 1, 1)),
        ),
    )
    # The index of 2029 is 1.20, known on 2030-01-01; shifted, it is read a year on.
    final = decisions.decided[model.value(key="first").id]
    assert final.on == date(2031, 1, 1)
    check = decisions.checks[-1]
    assert check.readings[0].value.number == 1.20
    assert check.readings[0].available_on == date(2030, 1, 1)


def test_a_shift_with_no_movement_before_is_unavailable():
    model = small_model()
    with pytest.raises(AvailabilityError) as raised:
        run(
            model,
            rule(model, "first", "rent_index.shift(by=1) >= 1"),
        )
    assert raised.value.code is Code.OBSERVATION_UNAVAILABLE
    assert raised.value.key == "first"
    assert raised.value.decision_date == date(2027, 1, 1)


def test_a_window_date_before_any_amount_is_known_is_unavailable():
    """ADR-021, cell 6: a calendar that opens before the path's first amount."""
    model = small_model()
    with pytest.raises(AvailabilityError) as raised:
        run(model, rule(model, "first", "rent_index >= 1", periods=YEARS))
    assert raised.value.available_on == date(2027, 1, 1)
    assert raised.value.decision_date == date(2026, 1, 1)


def test_a_look_ahead_raises_before_any_date():
    """ADR-021, cell 8."""
    model = small_model()
    with pytest.raises(AvailabilityError) as raised:
        run(model, rule(model, "first", "rent_index.shift(by=-1) >= 1"))
    assert raised.value.code is Code.OBSERVATION_UNAVAILABLE
    assert raised.value.key == "first"


def test_a_condition_on_a_later_rule_raises_rule_order():
    """ADR-021, cell 11, with the rules the other way round."""
    model = small_model()
    with pytest.raises(ContractError) as raised:
        run(
            model,
            rule(model, "second", "first = NEVER"),
            rule(model, "first", "rent_index >= 1"),
        )
    assert raised.value.code is Code.RULE_ORDER


def test_a_condition_on_its_own_value_raises_rule_order():
    model = small_model()
    with pytest.raises(ContractError) as raised:
        run(model, rule(model, "first", "first = NEVER", latest=on(date(2030, 1, 1))))
    assert raised.value.code is Code.RULE_ORDER


def test_a_scalar_that_depends_on_a_later_rule_raises_rule_order():
    model = small_model("level_later = middle", "middle = level")
    with pytest.raises(ContractError) as raised:
        run(
            model,
            rule(model, "second", "level_later >= 0", latest=on(date(2030, 1, 1))),
            rule(
                model, "level", "rent_index >= 1", then=_ratio(1), otherwise=_ratio(0)
            ),
        )
    assert raised.value.code is Code.RULE_ORDER


def test_a_condition_on_a_free_input_raises_rule_reads_unknown():
    model = small_model()
    with pytest.raises(ContractError) as raised:
        run(model, rule(model, "first", "level >= 1", latest=on(date(2030, 1, 1))))
    assert raised.value.code is Code.RULE_READS_UNKNOWN


def test_a_rule_gives_the_kind_of_value_that_its_value_holds():
    model = small_model()
    level = model.value(key="level").id
    condition = parse_text(text="rent_index >= 1", model=model)
    for declared in (
        RuleQuery(target=level, condition=condition, otherwise=NEVER),
        RuleQuery(target=level, condition=condition, otherwise=_ratio(1)),
        rule(model, "first", "rent_index >= 1", otherwise=_ratio(1)),
    ):
        with pytest.raises(ContractError) as raised:
            run(model, declared)
        assert raised.value.code is Code.RULE_CAPABILITY


def test_a_value_has_one_rule():
    model = small_model()
    first = rule(model, "first", "rent_index >= 1")
    with pytest.raises(ContractError) as raised:
        run(model, first, first)
    assert raised.value.code is Code.RULE_CAPABILITY


def test_a_decision_that_moves_a_date_into_the_past_fails():
    """ADR-021, acceptance 5: ``marketing_start = first - 6 months``, with no solve."""
    model = small_model("marketing_start = first - 6 months")
    with pytest.raises(DecisionError) as raised:
        run(model, rule(model, "first", "rent_index >= 1.20"))
    assert raised.value.code is Code.DECISION_CHANGES_PAST
    assert raised.value.values["decision"] == "first"
    assert raised.value.values["movement"] == "marketing_start"
    assert raised.value.values["date"] == "2029-07-01"


def test_a_decision_that_moves_a_movement_of_the_past_fails():
    """A fee of the total spend, in every year: a decision changes earlier fees."""
    model = small_model(
        "total_spend = spend.total()",
        "fee = total_spend * rent_index",
    )
    with pytest.raises(DecisionError) as raised:
        _solved_run(
            model,
            rule(model, "first", "rent_index >= 1.01"),
            rule(model, "second", "fee >= 100 AUD"),
        )
    assert raised.value.code is Code.DECISION_CHANGES_PAST
    assert raised.value.values["movement"] == "fee"
    assert raised.value.values["before"] == "2028-01-01"


def test_the_final_candidate_cannot_move_a_movement_of_the_past():
    """The last decision follows the last read, so only the final solve can show it."""
    model = small_model(
        "total_spend = spend.total()",
        "fee = total_spend * rent_index",
    )
    attempt, outcome = _attempt(
        model,
        rule(model, "second", "fee >= 0 AUD"),
        rule(model, "first", "rent_index >= 1.01"),
    )
    assert attempt.decisions is not None
    assert attempt.decisions.solves == 1
    # ``second`` decides on 2027-01-01, after the read that made the only solution.
    assert attempt.decisions.since == date(2027, 1, 1)
    assert outcome.status is Status.FAILED
    with pytest.raises(DecisionError) as raised:
        outcome.raise_for_status()
    assert raised.value.code is Code.DECISION_CHANGES_PAST
    assert raised.value.values["movement"] == "fee"


def test_an_infeasible_provisional_solve_names_the_constraint():
    """A fixed date that ``first``'s ``otherwise``, NEVER, breaks, at the first read."""
    model = small_model("second >= first + 1 year")
    with pytest.raises(DecisionError) as raised:
        _solved_run(
            model,
            rule(model, "first", "rent_index >= 1.01"),
            rule(model, "third", "spend >= 100 AUD"),
            second=date(2028, 6, 1),
        )
    assert raised.value.code is Code.PROVISIONAL_INFEASIBLE
    assert raised.value.values["constraints"] == ["second >= first + 1 year"]


def test_rules_that_read_a_solved_flow_solve_once_for_each_decision_before_it():
    """The bound of ADR-021: reads after no new decision reuse the last solution."""
    model = small_model()
    decisions, backend = _counted(
        model,
        rule(model, "first", "rent_index >= 1.01"),
        rule(model, "second", "spend >= 100 AUD"),
        rule(model, "third", "rent_index >= 1.20"),
    )
    # ``second`` reads ``spend`` on each date from 2027 to 2031. It solves on 2027,
    # for the state with no decision. ``first`` decides on 2028-01-01, before the
    # read of that date, which solves again; 2029 and 2030 reuse that solution.
    # ``third`` decides on 2030-01-01, after the read of that date, so the read of
    # 2031 solves once more: one solve, and one for each decision before a read.
    assert decisions.solves == 3
    assert decisions.solves == backend.calls


def test_decided_values_that_no_equation_reads_reach_the_candidate():
    model = small_model()
    level = RuleQuery(
        target=model.value(key="level").id,
        condition=parse_text(text="rent_index >= 1.20", model=model),
        then=_ratio(3),
        otherwise=_ratio(1),
    )
    _, outcome = _attempt(
        model,
        level,
        rule(model, "second", "rent_index >= 1.01"),
        first=date(2028, 1, 1),
    )
    assert outcome.status is Status.FEASIBLE
    assert outcome["level"].number == 3
    assert outcome["second"] == date(2028, 1, 1)


def test_a_decided_quantity_is_a_fixed_value_in_the_final_solve():
    model = small_model("doubled = level * 2")
    level = RuleQuery(
        target=model.value(key="level").id,
        condition=parse_text(text="rent_index >= 1.20", model=model),
        then=rk.Quantity(magnitude=3, units="ratio"),
        otherwise=rk.Quantity(magnitude=1, units="ratio"),
    )
    attempt, outcome = _attempt(model, level, first=date(2028, 1, 1))
    assert outcome.status is Status.FEASIBLE
    assert attempt.decisions.decided[level.target].on == date(2030, 1, 1)
    assert outcome["level"].number == 3
    assert outcome["doubled"].number == 6


def test_a_failed_rule_gives_a_failed_case_and_its_error_again():
    """ADR-021: an unavailable observation fails that case; the fields stay."""
    model = small_model()
    attempt, outcome = _attempt(
        model, rule(model, "first", "rent_index.shift(by=1) >= 1")
    )
    assert attempt.decisions is None
    assert outcome.status is Status.FAILED
    with pytest.raises(AvailabilityError) as raised:
        outcome.raise_for_status()
    assert raised.value.code is Code.OBSERVATION_UNAVAILABLE
    assert raised.value.key == "first"
    assert raised.value.decision_date == date(2027, 1, 1)


def test_a_moved_date_gives_a_failed_case_that_names_the_date():
    model = small_model("marketing_start = first - 6 months")
    _, outcome = _attempt(model, rule(model, "first", "rent_index >= 1.20"))
    assert outcome.status is Status.FAILED
    with pytest.raises(DecisionError) as raised:
        outcome.raise_for_status()
    assert raised.value.code is Code.DECISION_CHANGES_PAST
    assert raised.value.values["movement"] == "marketing_start"


def test_rule_errors_keep_their_fields_through_pickle():
    availability = AvailabilityError(
        "x", key="first", available_on=date(2027, 1, 1), decision_date=date(2026, 1, 1)
    )
    copy = pickle.loads(pickle.dumps(availability))
    assert (copy.key, copy.available_on, copy.decision_date) == (
        "first",
        date(2027, 1, 1),
        date(2026, 1, 1),
    )
    decision = DecisionError("x", values={"movement": "fee"})
    assert pickle.loads(pickle.dumps(decision)).values == {"movement": "fee"}


# The trace check: a changed trace fails it.


@pytest.fixture(scope="module")
def traced():
    """Return the decisions and facts of the ``late`` history of the verification."""
    attempt, outcome = attempts()["late"]
    binding = attempt.binding
    path = binding.composition.requirements.path
    paths = attempt.paths(binding)
    return (
        attempt.rules,
        attempt.decisions.checks,
        TraceFacts(
            candidate=outcome.outputs[0],
            path_known=path_known(path=path, paths=paths),
            path_amounts=path_amounts(path=path, paths=paths),
            parameters=PARAMETERS,
            units=binding.units,
        ),
        attempt,
    )


def test_the_trace_check_passes_an_unchanged_trace(traced):
    declared, checks, facts, _ = traced
    check_trace(rules=declared, checks=checks, facts=facts)


def _tampered(checks, *, key, on, change) -> tuple[Check, ...]:
    return tuple(
        change(c) if (c.key, c.on, c.result) == (key, on[0], on[1]) else c
        for c in checks
    )


def _first_reading(check, **changes) -> tuple[Reading, ...]:
    first, *rest = check.readings
    return (replace(first, **changes), *rest)


TAMPERED = {
    "another condition": lambda c: replace(c, condition=True),
    "another reading": lambda c: replace(
        c, readings=_first_reading(c, value=rk.Quantity(magnitude=2, units="ratio"))
    ),
    "read before it is known": lambda c: replace(
        c, readings=_first_reading(c, available_on=date(2040, 1, 1))
    ),
    "another availability": lambda c: replace(
        c, readings=_first_reading(c, available_on=date(2020, 1, 1))
    ),
    "no reading": lambda c: replace(c, readings=()),
}


@pytest.mark.parametrize("name", TAMPERED)
def test_a_changed_record_fails_the_trace_check(traced, name):
    declared, checks, facts, _ = traced
    changed = _tampered(
        checks,
        key="start_date",
        on=(date(2029, 1, 1), NOT_MET),
        change=TAMPERED[name],
    )
    with pytest.raises(DecisionError) as raised:
        check_trace(rules=declared, checks=changed, facts=facts)
    assert raised.value.code is Code.RULE_TRACE


def test_a_missing_window_date_fails_the_trace_check(traced):
    declared, checks, facts, _ = traced
    fewer = tuple(
        c for c in checks if (c.key, c.on) != ("start_date", date(2028, 1, 1))
    )
    with pytest.raises(DecisionError, match="no record of the window date"):
        check_trace(rules=declared, checks=fewer, facts=facts)


def test_a_decided_value_that_the_candidate_lacks_fails_the_trace_check(traced):
    declared, checks, facts, _ = traced
    changed = _tampered(
        checks,
        key="start_date",
        on=(date(2030, 1, 1), DECIDED),
        change=lambda c: replace(c, value=date(2031, 1, 1)),
    )
    with pytest.raises(DecisionError) as raised:
        check_trace(rules=declared, checks=changed, facts=facts)
    assert raised.value.code is Code.RULE_TRACE


def test_records_out_of_the_written_order_fail_the_trace_check(traced):
    declared, checks, facts, _ = traced
    # On 2033-01-01 B's rule runs before the sale rule that reads it.
    rows = list(checks)
    rows[-2], rows[-1] = rows[-1], rows[-2]
    with pytest.raises(DecisionError) as raised:
        check_trace(rules=declared, checks=tuple(rows), facts=facts)
    assert raised.value.code is Code.RULE_TRACE


def test_a_candidate_with_other_path_data_fails_the_trace_check(traced):
    declared, checks, facts, _ = traced
    amounts = {
        token: rk.Quantity(magnitude=quantity.number + 1, units=quantity.units)
        for token, quantity in facts.path_amounts.items()
    }
    with pytest.raises(DecisionError, match="differs from its source"):
        check_trace(
            rules=declared, checks=checks, facts=replace(facts, path_amounts=amounts)
        )


# Helpers of the tests above.


def _text(model: rk.Model, source: str) -> Expression:
    return parse_text(text=source, model=model)


def _ratio(number: float) -> rk.Quantity:
    return rk.Quantity(magnitude=number, units="ratio")


class Counted:
    """Answer each problem with the real backend, and count the calls that end it."""

    def __init__(self) -> None:
        self.calls = 0
        self.inner = _real_backend()

    def solve(self, *, problem, limits, remaining, options) -> BackendResult:
        result = self.inner.solve(
            problem=problem, limits=limits, remaining=remaining, options=options
        )
        assert result.termination is Termination.FEASIBLE
        self.calls += 1
        return result


def _real_backend():
    from rangekeeper.execution.backends import registry

    return registry.get(ExecutionConfig().backend)


def _solved_run(model, *declared, **fixes) -> Decisions:
    return run(model, *declared, backend=_real_backend(), **fixes)


def _counted(model, *declared, **fixes) -> tuple[Decisions, Counted]:
    backend = Counted()
    return run(model, *declared, backend=backend, **fixes), backend


def _attempt(model, *declared, **fixes):
    leaf, cases, _, _ = bound(model, **fixes)
    config = ExecutionConfig()
    attempt = Attempt(
        leaf,
        cases.compositions[leaf.id],
        config=config,
        backend=_real_backend(),
        resolver=cases,
        rules=declared,
    )
    return attempt, attempt.execute()
