"""Declaring rules: Window, where, first and fix(key=rule) (ADR-021, #300)."""

from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.duration import NEVER, Frequency, Span
from rangekeeper.errors import AvailabilityError, Code
from rangekeeper.run.documents import Documents
from rangekeeper.shared.errors import (
    ContractError,
    EquationError,
    MissingReferenceError,
    ValidationError,
)
from rangekeeper.specification import Role, Rule, Rules, Where, Window

YEARS = Span(start=date(2027, 1, 1), end=date(2033, 1, 1)).periods(
    frequency=Frequency.YEAR
)
WINDOW = Window(earliest=date(2027, 1, 1), latest=date(2031, 1, 1))


def small_model() -> rk.Model:
    draft = rk.Model(name="Rules").edit()
    project = draft.add_entity(code="project", classification="project")
    project.flow(key="rent_index", units="ratio", periods=YEARS)
    project.flow(key="stock", units="ratio", periods=YEARS)
    project.date(key="first")
    project.date(key="second")
    project.date(key="after_first")
    project.value(key="trigger", units="ratio")
    project.value(key="level", units="ratio")
    project.value(key="derived", units="ratio")
    project.equations(
        "after_first = first + 1 year",
        "derived = 2 * level",
    )
    return draft.commit()


def one_path() -> rk.market.Paths:
    flow = rk.flow.Flow.from_periods(
        periods=YEARS, magnitudes=[1.0] * len(YEARS), units="ratio"
    )
    return rk.market.Paths.from_flows(flows={"one": {"rent_index": flow}})


def spec(**fixes) -> rk.Specification:
    return small_model().specify().fix(trigger=1.05, **fixes)


def rising() -> Rule:
    return WINDOW.where(condition="rent_index >= trigger").first(otherwise=NEVER)


def role_of(specification: rk.Specification, key: str) -> Role:
    table = specification.roles
    return dict(zip(table.column("key"), table.column("role"), strict=True))[key]


def code_of(raised) -> Code:
    return raised.value.code


def test_the_query_makes_a_rule_without_a_model():
    query = WINDOW.where(condition="rent_index >= trigger")
    assert isinstance(query, Where)
    rule = query.first(otherwise=NEVER)
    assert (rule.window, rule.condition, rule.otherwise) == (
        WINDOW,
        "rent_index >= trigger",
        NEVER,
    )
    assert rule.then is None


def test_fix_makes_a_value_decided_and_stores_its_rule():
    made = spec().fix(first=rising())
    assert role_of(made, "first") is Role.DECIDED
    assert role_of(made, "after_first") is Role.FREE
    (stored,) = made.record.rules
    assert stored.target.target == made.model.value(key="first").id
    assert stored.earliest.date == date(2027, 1, 1)
    assert stored.latest.date == date(2031, 1, 1)
    assert stored.otherwise.never is NEVER
    assert stored.then is None and not stored.periods and stored.timing is None
    assert made.metadata.previous is not None


def test_stored_rules_read_back():
    made = spec().fix(first=rising())
    data = made.to_data()
    again = rk.Specification.from_data(data)
    assert again.record.rules == made.record.rules
    assert again.to_data() == data


def test_rules_run_in_the_order_they_are_fixed_and_a_later_fix_keeps_the_position():
    second = WINDOW.where(condition="first != NEVER").first(otherwise=NEVER)
    made = spec().fix(first=rising()).fix(second=second)
    assert list(made.rules) == ["first", "second"]
    other = WINDOW.where(condition="rent_index >= 2").first(otherwise=NEVER)
    replaced = made.fix(first=other)
    assert list(replaced.rules) == ["first", "second"]
    assert replaced.rules["first"].condition == "rent_index >= 2"


def test_a_later_fix_or_free_replaces_a_rule():
    made = spec().fix(first=rising())
    fixed = made.fix(first=date(2028, 1, 1))
    assert not fixed.rules
    freed = made.free("first")
    assert not freed.rules
    assert role_of(freed, "first") is Role.FREE


def test_a_rule_replaces_a_fix_and_its_estimate():
    made = spec(first=date(2028, 1, 1)).fix(first=rising())
    assert made.model.value(key="first").id not in {
        a.target.target for a in made.record.assignments
    }


def test_one_fix_call_gives_values_and_rules_together():
    # Cell 11: the fixed value and the rule that reads it arrive in one call.
    reads = WINDOW.where(condition="rent_index >= own").first(otherwise=NEVER)
    draft = small_model().edit()
    draft.entity(code="project").value(key="own", units="ratio")
    made = draft.commit().specify().fix(own=1.0, first=reads)
    assert list(made.rules) == ["first"]


def test_rules_is_a_mapping_that_names_a_missing_key():
    made = spec().fix(first=rising())
    rules = made.rules
    assert isinstance(rules, Rules)
    assert "first" in rules and "second" not in rules and len(rules) == 1
    with pytest.raises(MissingReferenceError):
        rules["second"]
    assert rules.get("second") is None


def test_a_rule_brings_the_fixed_values_it_reads():
    made = spec().fix(first=rising())
    rule = made.rules["first"]
    assert rule.triggers["trigger"].number == pytest.approx(1.05)
    other = small_model().specify().fix(first=rule)
    assert other.rules["first"].triggers["trigger"].number == pytest.approx(1.05)
    # A value that the other Specification fixes stays.
    mine = small_model().specify().fix(trigger=2.0).fix(first=rule)
    assert mine.rules["first"].triggers["trigger"].number == pytest.approx(2.0)


def test_a_look_ahead_raises_availability_error():
    rule = WINDOW.where(condition="rent_index.shift(by=-1) >= 1").first(otherwise=NEVER)
    with pytest.raises(AvailabilityError) as raised:
        spec().fix(first=rule)
    assert raised.value.key == "first"


def test_a_later_rule_raises_rule_order_as_a_validation_error():
    reader = WINDOW.where(condition="second == NEVER").first(otherwise=NEVER)
    with pytest.raises(ValidationError) as raised:
        spec().fix(first=reader, second=rising())
    assert code_of(raised) is Code.RULE_ORDER


def test_its_own_value_raises_rule_order():
    reader = WINDOW.where(condition="first == NEVER").first(otherwise=NEVER)
    with pytest.raises(ValidationError) as raised:
        spec().fix(first=reader)
    assert code_of(raised) is Code.RULE_ORDER


def test_a_free_scalar_raises_rule_reads_unknown():
    with pytest.raises(ValidationError) as raised:
        small_model().specify().fix(first=rising())
    assert code_of(raised) is Code.RULE_READS_UNKNOWN
    assert raised.value.report.issues[0].code is Code.RULE_READS_UNKNOWN


def test_a_free_flow_waits_for_across():
    reads_two = WINDOW.where(condition="rent_index + stock >= trigger").first(
        otherwise=NEVER
    )
    made = spec().fix(first=reads_two)
    paths = one_path()
    with pytest.raises(ValidationError) as raised:
        made.across(paths=paths)
    assert code_of(raised) is Code.RULE_READS_UNKNOWN
    single = spec().fix(first=rising())
    assert single.across(paths=paths).record.cases


def test_freeing_a_value_that_a_rule_reads_raises():
    made = spec().fix(first=rising())
    with pytest.raises(ValidationError) as raised:
        made.free("trigger")
    assert code_of(raised) is Code.RULE_READS_UNKNOWN


@pytest.mark.parametrize(
    ("key", "rule"),
    [
        # A date for a quantity, a quantity for a date, and a date as a quantity.
        ("level", WINDOW.where(condition="rent_index >= 1").first(otherwise=NEVER)),
        ("first", WINDOW.where(condition="rent_index >= 1").first(otherwise="1 ratio")),
        (
            "level",
            WINDOW.where(condition="rent_index >= 1").first(otherwise=1.0),
        ),
        ("rent_index", WINDOW.where(condition="stock >= 1").first(otherwise=1.0)),
        ("first", WINDOW.where(condition="rent_index").first(otherwise=NEVER)),
        (
            "first",
            WINDOW.where(condition="rent_index.cumulative() >= 1").first(
                otherwise=NEVER
            ),
        ),
        (
            "first",
            Window(earliest="level")
            .where(condition="rent_index >= 1")
            .first(otherwise=NEVER),
        ),
        (
            "first",
            WINDOW.where(condition="rent_index >= 1").first(
                then="hotel", otherwise=NEVER
            ),
        ),
    ],
)
def test_a_rule_of_the_wrong_kind_raises_rule_capability(key, rule):
    with pytest.raises(ValidationError) as raised:
        spec(level=1.0).fix({key: rule})
    assert code_of(raised) is Code.RULE_CAPABILITY


def test_a_quantity_rule_needs_then_and_takes_quantity_text():
    rule = WINDOW.where(condition="rent_index >= 1").first(then="2 ratio", otherwise=0)
    made = spec().fix(level=rule)
    stored = made.record.rules[0]
    assert stored.then.quantity.number == 2
    assert stored.otherwise.quantity.number == 0


def test_equation_text_keeps_one_equals_sign():
    with pytest.raises(EquationError) as raised:
        WINDOW.where(condition="first = NEVER")
    assert raised.value.suggestions == ("==",)
    draft = small_model().edit()
    with pytest.raises(EquationError):
        draft.entity(code="project").equations("level == 2")


def test_a_condition_with_equality_binds_tighter_than_and():
    rule = WINDOW.where(condition="rent_index >= 1 and first == NEVER").first(
        otherwise=NEVER
    )
    made = spec(first=date(2030, 1, 1)).fix(second=rule)
    assert made.rules["second"].condition == "rent_index >= 1 and first == NEVER"


@pytest.mark.parametrize(
    "fields",
    [
        {"earliest": date(2031, 1, 1), "latest": date(2030, 1, 1)},
        {"periods": ()},
        {"timing": rk.duration.PeriodTiming.LAST},
    ],
)
def test_a_window_that_cannot_act_raises(fields):
    with pytest.raises(ContractError) as raised:
        Window(**fields)
    assert code_of(raised) is Code.RULE_CAPABILITY


@pytest.mark.parametrize(
    "fields",
    [{"earliest": 2027}, {"latest": NEVER}, {"periods": [1]}, {"timing": "first"}],
)
def test_a_window_of_the_wrong_type_raises_type_error(fields):
    with pytest.raises(TypeError):
        Window(**fields)


def test_where_and_first_take_their_arguments_by_name():
    with pytest.raises(TypeError):
        WINDOW.where("rent_index >= 1")  # type: ignore[misc]
    with pytest.raises(TypeError):
        WINDOW.where(condition=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        WINDOW.where(condition="rent_index >= 1").first(otherwise=None)  # type: ignore[arg-type]


def test_on_keeps_the_rules_and_names_a_value_that_is_gone():
    made = spec().fix(first=rising())
    draft = made.model.edit()
    draft.entity(code="project").value(key="extra", units="ratio")
    moved = made.on(model=draft.commit())
    assert list(moved.rules) == ["first"]
    gone = made.free("first").fix(trigger=1.0)
    assert not gone.rules
    draft = made.model.edit()
    draft.entity(code="project").remove(key="trigger")
    with pytest.raises(ContractError) as raised:
        made.on(model=draft.commit())
    assert raised.value.code is Code.REFERENCE_MISSING


def test_validate_reports_what_fix_reports():
    made = spec().fix(first=rising())
    report = made.validate(resolver=Documents((made, made.model), where="test"))
    assert report.issues[0].code is Code.RULE_READS_UNKNOWN


def test_solve_runs_the_rules_and_fixes_the_decided_value():
    made = spec().fix(first=rising())
    paths = one_path()
    case = rk.execution.solve(specification=made.across(paths=paths)).case(key="one")
    assert case.run.rule_evidence is not None
    assert [row.key for row in case.trace] == ["first"] * len(case.trace)
    assert case.trace[-1].result is rk.execution.DecisionResult.OTHERWISE
