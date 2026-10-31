"""Independent verification of sequential rule evaluation (#215, ADR-021).

The expected values here do not come from the engine. They come from two sources
that share no code with it, and agree with each other:

1. The worked tables in ``HAND``, written out by hand from the three histories.
2. ``independent``, a small calculation in plain Python over floats. It imports
   nothing from rangekeeper. It reads the rules of this one project directly, not
   through a window or a condition.

The project is lesson 05's in small. Building A costs 100 in its start year and
earns ``30 * rent_index`` a year from a year later; Building B costs 60 and earns
``20 * rent_index`` from a year after it starts. The site of B sells for 5 when B
is abandoned. Equity is 30 and the loan limit 60. All amounts are cash per calendar
year, and the NPV discounts each year's cash from the end of the year to 2027-01-01
at 10 % a year.

The rules are those of ADR-021's worked examples:

- ``start_date``: from 2027-01-01 to 2030-01-01, when ``rent_index >= 1.05``.
- ``b_start``: from ``shared_start + 1 year`` to 2032-01-01, when
  ``rent_index >= 1.10`` and ``equity_available + loan_available >= 60``.
- ``b_sale_date``: on 2033-01-01, when ``b_start`` is NEVER.
"""

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.execution.attempt import Attempt
from rangekeeper.execution.backends import registry
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.pipeline import Pinned
from rangekeeper.execution.planning import resolve_cases
from rangekeeper.execution.status import Status
from rangekeeper.market.paths import Paths
from rangekeeper.run._rule.result import DecisionResult
from rangekeeper.schema.records import Expression, ExpressionKind
from rangekeeper.specification.rule._query import RuleQuery, parse_text

NEVER = rk.duration.NEVER
FIRST_YEAR, LAST_YEAR = 2026, 2036
HISTORIES = {
    "recovery": (1.00, 1.06, 1.12, 1.15, 1.16, 1.16, 1.16, 1.16, 1.16, 1.16, 1.16),
    "downturn": (1.00, 0.97, 0.95, 0.94, 0.93, 0.93, 0.93, 0.93, 0.93, 0.93, 0.93),
    "late": (1.00, 0.97, 0.95, 1.06, 1.12, 1.15, 1.16, 1.16, 1.16, 1.16, 1.16),
}
# The trigger of the start rule, as a parameter of the rule.
PARAMETERS = {"start_trigger": rk.Quantity(magnitude=1.05, units="ratio")}


@dataclass(frozen=True)
class Expected:
    """The decisions and values of one history."""

    start_date: date | object
    b_start: date | object
    b_sale_date: date | object
    decided_on: dict[str, date]
    equity_npv: float
    provisional_solves: int


# The worked tables, by hand.
#
# recovery: the rent index of 2027, 1.06, is known on 2028-01-01, so A starts then.
#   Works cost 100 in 2028; A earns 30 * 1.15 = 34.50 in 2029 and 30 * 1.16 = 34.80
#   a year after. B's window opens on 2029-01-01:
#     on 2029-01-01 it reads 2028: need 100.00, equity left 0, loan 70.00, available
#       -10.00; -10.00 < 60, not met.
#     on 2030-01-01 it reads 2029: need 65.50, equity left 0, loan 35.50, available
#       24.50; 24.50 < 60, not met.
#     on 2031-01-01 it reads 2030: need 30.70, equity left 0, loan 0.70, available
#       59.30; 59.30 < 60, not met.
#     on 2032-01-01 it reads 2031: need -4.10, equity left 34.10, loan 0, available
#       60; 94.10 >= 60, and 1.16 >= 1.10, so B starts on 2032-01-01.
#   B never sells: on 2033-01-01 the sale rule reads 2032-01-01, so it takes NEVER.
#   Cash by year, 2028 to 2036: -100, 34.5, 34.8, 34.8, 34.8 - 60 = -25.2,
#   34.8 + 23.2 = 58, 58, 58, 58. Discounted at 10 % from the year's end:
#   -82.6446 + 25.9204 + 23.7689 + 21.6081 - 14.2248 + 29.7632 + 27.0575 + 24.5977
#   + 22.3615 = 78.208 (exponents 2 to 10: 2028's cash is discounted from 2029-01-01).
#
# downturn: the index never reaches 1.05. On 2031-01-01, the next date after the
#   last window date, the start rule takes NEVER. B's earliest bound becomes NEVER,
#   so B takes NEVER on the same date. On 2033-01-01 the site sells: cash of 5 in
#   2033, discounted over 7 years: 5/1.1^7 = 2.566.
#
# late: the index of 2029, 1.06, is known on 2030-01-01, so A starts then. Works cost
#   100 in 2030; A earns 30 * 1.15 = 34.5 in 2031. B reads: on 2031-01-01, need 100,
#   available -10, not met; on 2032-01-01, need 65.5, available 24.5, not met. On
#   2033-01-01 B's latest bound has passed, so it takes NEVER, and then the sale rule
#   on the same date reads NEVER, so the site sells.
#   Cash by year, 2030 to 2036: -100, 34.5, 34.8, 34.8 + 5 = 39.8, 34.8, 34.8, 34.8.
#   -68.3013 + 21.4218 + 19.6439 + 20.4237 + 16.2345 + 14.7586 + 13.4170 = 37.598
#   (exponents 4 to 10).
HAND = {
    "recovery": Expected(
        start_date=date(2028, 1, 1),
        b_start=date(2032, 1, 1),
        b_sale_date=NEVER,
        decided_on={
            "start_date": date(2028, 1, 1),
            "b_start": date(2032, 1, 1),
            "b_sale_date": date(2033, 1, 1),
        },
        equity_npv=78.208,
        provisional_solves=1,
    ),
    "downturn": Expected(
        start_date=NEVER,
        b_start=NEVER,
        b_sale_date=date(2033, 1, 1),
        decided_on={
            "start_date": date(2031, 1, 1),
            "b_start": date(2031, 1, 1),
            "b_sale_date": date(2033, 1, 1),
        },
        equity_npv=2.566,
        provisional_solves=0,
    ),
    "late": Expected(
        start_date=date(2030, 1, 1),
        b_start=NEVER,
        b_sale_date=date(2033, 1, 1),
        decided_on={
            "start_date": date(2030, 1, 1),
            "b_start": date(2033, 1, 1),
            "b_sale_date": date(2033, 1, 1),
        },
        equity_npv=37.598,
        provisional_solves=1,
    ),
}


def independent(index: tuple[float, ...]) -> tuple[object, object, object, float]:
    """Return the decisions and the NPV of one history, in plain Python.

    ``index[i]`` is the rent index of calendar year ``2026 + i``, known on 1 January
    of the next year. This shares no code with rangekeeper.
    """

    def year_of(year: int) -> float:
        return index[year - FIRST_YEAR]

    start = next((y for y in range(2027, 2031) if year_of(y - 1) >= 1.05), None)
    b_year = None
    if start is not None:
        for year in range(start + 1, 2033):
            cash = _cash(index, start=start, b_start=None, sale=None)
            need = -sum(cash[y] for y in range(FIRST_YEAR, year))
            equity_left = max(0.0, 30.0 - need)
            loan = max(0.0, need - 30.0)
            available = 60.0 - loan
            if year_of(year - 1) >= 1.10 and equity_left + available >= 60.0:
                b_year = year
                break
    sale = 2033 if b_year is None else None
    cash = _cash(index, start=start, b_start=b_year, sale=sale)
    npv = sum(
        amount / 1.1 ** (year + 1 - 2027)
        for year, amount in cash.items()
        if year >= 2027
    )
    return (
        NEVER if start is None else date(start, 1, 1),
        NEVER if b_year is None else date(b_year, 1, 1),
        NEVER if sale is None else date(sale, 1, 1),
        npv,
    )


def _cash(
    index: tuple[float, ...],
    *,
    start: int | None,
    b_start: int | None,
    sale: int | None,
) -> dict[int, float]:
    cash = {}
    for offset, level in enumerate(index):
        year = FIRST_YEAR + offset
        amount = 0.0
        if start is not None:
            amount += -100.0 if year == start else 0.0
            amount += 30.0 * level if year > start else 0.0
        if b_start is not None:
            amount += -60.0 if year == b_start else 0.0
            amount += 20.0 * level if year > b_start else 0.0
        amount += 5.0 if year == sale else 0.0
        cash[year] = amount
    return cash


def project_model() -> rk.Model:
    """Return the project's Model: the same equations as the docstring describes."""
    years = rk.duration.Span(
        start=date(FIRST_YEAR, 1, 1), end=date(LAST_YEAR + 1, 1, 1)
    ).periods(frequency=rk.duration.Frequency.YEAR)
    draft = rk.Model(name="Sequential verification").edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("base_date", "start_date", "b_start", "b_sale_date"):
        project.date(key=key)
    for key in ("a_cost", "b_cost", "a_rent", "b_rent", "site_value"):
        project.value(key=key, units="AUD")
    project.value(key="equity", units="AUD")
    project.value(key="loan_limit", units="AUD")
    project.value(key="rate", units="% pa")
    project.value(key="equity_npv", units="AUD")
    project.flow(key="rent_index", units="ratio", periods=years)
    project.flow(key="a_works", units="AUD", periods=years)
    project.flow(key="b_works", units="AUD", periods=years)
    project.flow(key="a_income", units="AUD", periods=years)
    project.flow(key="b_income", units="AUD", periods=years)
    project.flow(key="site_sale", units="AUD", periods=years)
    project.flow(key="cash", units="AUD", periods=years)
    project.flow(key="funding_need", units="AUD", periods=years)
    project.flow(key="equity_available", units="AUD", periods=years)
    project.flow(key="loan_principal", units="AUD", periods=years)
    project.flow(key="loan_available", units="AUD", periods=years)
    project.equations(
        "shared_start = start_date",
        "a_open = start_date + 1 year",
        "b_open = b_start + 1 year",
        "b_start >= shared_start + 1 year",
        "a_works = -rx.flow.event(amount=a_cost, on=start_date)",
        "b_works = -rx.flow.event(amount=b_cost, on=b_start)",
        "a_income = (a_rent * rent_index).since(on=a_open)",
        "b_income = (b_rent * rent_index).since(on=b_open)",
        "site_sale = rx.flow.event(amount=site_value, on=b_sale_date)",
        "cash = a_works + b_works + a_income + b_income + site_sale",
        "funding_need = -cash.cumulative()",
        "equity_available = rx.max(0 AUD, equity - funding_need)",
        "loan_principal = rx.max(0 AUD, funding_need - equity)",
        "loan_available = loan_limit - loan_principal",
        "equity_npv = rx.finance.npv(flow=cash, rate=rate, on=base_date)",
    )
    return draft.commit()


def histories() -> Paths:
    """Return the three histories, with the amount of each year known at its end."""
    years = rk.duration.Span(
        start=date(FIRST_YEAR, 1, 1), end=date(LAST_YEAR + 1, 1, 1)
    ).periods(frequency=rk.duration.Frequency.YEAR)
    flows = {
        key: {
            "rent_index": rk.flow.Flow.from_periods(
                periods=years, magnitudes=list(index), units="ratio"
            )
        }
        for key, index in HISTORIES.items()
    }
    return Paths.from_flows(flows=flows)


def rules(model: rk.Model) -> tuple[RuleQuery, ...]:
    """Return the rules of the docstring, in their written order."""

    def text(source: str) -> Expression:
        return parse_text(text=source, model=model, parameters=PARAMETERS)

    return (
        RuleQuery(
            target=model.value(key="start_date").id,
            condition=text("rent_index >= start_trigger"),
            earliest=_date_bound(date(2027, 1, 1)),
            latest=_date_bound(date(2030, 1, 1)),
            otherwise=NEVER,
        ),
        RuleQuery(
            target=model.value(key="b_start").id,
            condition=text(
                "rent_index >= 1.10 and equity_available + loan_available >= b_cost"
            ),
            earliest=text("shared_start + 1 year"),
            latest=_date_bound(date(2032, 1, 1)),
            otherwise=NEVER,
        ),
        RuleQuery(
            target=model.value(key="b_sale_date").id,
            condition=text("b_start = NEVER"),
            earliest=_date_bound(date(2033, 1, 1)),
            latest=_date_bound(date(2033, 1, 1)),
            otherwise=NEVER,
        ),
    )


def _date_bound(value: date) -> Expression:
    return Expression(id=uuid4(), kind=ExpressionKind.DATE, date=value)


def attempts() -> dict[str, tuple[Attempt, object]]:
    """Run the project on each history, through the real stages and backend."""
    model = project_model()
    paths = histories()
    base = model.specify(name="Rules").fix(
        base_date=date(2027, 1, 1),
        a_cost="100 AUD",
        b_cost="60 AUD",
        a_rent="30 AUD",
        b_rent="20 AUD",
        site_value="5 AUD",
        equity="30 AUD",
        loan_limit="60 AUD",
        rate="10 % pa",
    )
    specification = base.across(paths=paths)
    config = ExecutionConfig()
    backend = registry.get(config.backend)
    cases = resolve_cases(specification=specification, resolver=Pinned(specification))
    found = {}
    for document in specification.record.cases:
        case = cases.documents[document]
        attempt = Attempt(
            case,
            cases.compositions[case.id],
            config=config,
            backend=backend,
            resolver=cases,
            rules=rules(model),
            parameters=PARAMETERS,
        )
        found[case.metadata.name] = (attempt, attempt.execute())
    return found


@pytest.fixture(scope="module")
def solved() -> dict[str, tuple[Attempt, object]]:
    return attempts()


@pytest.mark.parametrize("key", HISTORIES)
def test_the_hand_tables_agree_with_the_plain_calculation(key):
    """The two independent sources agree before they judge the engine."""
    start, b_start, sale, npv = independent(HISTORIES[key])
    hand = HAND[key]
    assert (start, b_start, sale) == (hand.start_date, hand.b_start, hand.b_sale_date)
    assert npv == pytest.approx(hand.equity_npv, abs=1e-3)


@pytest.mark.parametrize("key", HISTORIES)
def test_decisions_agree_with_the_independent_values(solved, key):
    attempt, outcome = solved[key]
    hand = HAND[key]
    assert outcome.status is Status.FEASIBLE, outcome.run.report.diagnostics
    decided = attempt.decisions.decided
    values = {item.key: item.value for item in decided.values()}
    assert values == {
        "start_date": hand.start_date,
        "b_start": hand.b_start,
        "b_sale_date": hand.b_sale_date,
    }
    assert {item.key: item.on for item in decided.values()} == hand.decided_on


@pytest.mark.parametrize("key", HISTORIES)
def test_the_final_candidate_holds_the_independent_npv(solved, key):
    _, outcome = solved[key]
    start, b_start, sale, npv = independent(HISTORIES[key])
    assert outcome["equity_npv"].number == pytest.approx(npv, abs=1e-6)
    assert outcome["start_date"] == start
    assert outcome["b_start"] == b_start
    assert outcome["b_sale_date"] == sale


@pytest.mark.parametrize("key", HISTORIES)
def test_the_solve_count_stays_within_the_bound(solved, key):
    attempt, _ = solved[key]
    assert attempt.decisions.solves == HAND[key].provisional_solves


def _checks(solved, key, *, rule):
    return [check for check in solved[key][0].decisions.checks if check.key == rule]


def test_each_window_date_of_the_start_rule_reads_the_year_before(solved):
    """ADR-021's table for cell 6: each check reads the period that ended on it."""
    checks = _checks(solved, "late", rule="start_date")
    assert [c.on for c in checks] == [date(y, 1, 1) for y in (2027, 2028, 2029, 2030)]
    assert [c.readings[0].value.number for c in checks] == [1.00, 0.97, 0.95, 1.06]
    assert [c.readings[0].available_on for c in checks] == [c.on for c in checks]
    assert [c.condition for c in checks] == [False, False, False, True]
    assert [c.result for c in checks] == [
        DecisionResult.NOT_MET,
        DecisionResult.NOT_MET,
        DecisionResult.NOT_MET,
        DecisionResult.DECIDED,
    ]


def test_the_funding_readings_agree_with_the_hand_table(solved):
    """Recovery: what B's rule read on each date, in the worked table above."""
    tested = [
        check
        for check in _checks(solved, "recovery", rule="b_start")
        if check.result is not DecisionResult.SKIPPED
    ]
    assert [c.on for c in tested] == [date(y, 1, 1) for y in (2029, 2030, 2031, 2032)]

    def reading(check, name):
        return next(r for r in check.readings if r.name == name).value.number

    hand = {
        date(2029, 1, 1): (1.12, 0.00, -10.00, False),
        date(2030, 1, 1): (1.15, 0.00, 24.50, False),
        date(2031, 1, 1): (1.16, 0.00, 59.30, False),
        date(2032, 1, 1): (1.16, 34.10, 60.00, True),
    }
    for check in tested:
        index, equity, loan, condition = hand[check.on]
        assert reading(check, "rent_index") == pytest.approx(index)
        assert reading(check, "equity_available") == pytest.approx(equity, abs=1e-7)
        assert reading(check, "loan_available") == pytest.approx(loan, abs=1e-7)
        assert check.condition is condition


def test_abandonment_runs_in_the_written_order_on_one_date(solved):
    """ADR-021's cell 11: on 2033-01-01, B takes NEVER, then the sale rule reads it."""
    on_the_date = [
        check
        for check in solved["late"][0].decisions.checks
        if check.on == date(2033, 1, 1)
    ]
    assert [(c.key, c.result) for c in on_the_date] == [
        ("b_start", DecisionResult.OTHERWISE),
        ("b_sale_date", DecisionResult.DECIDED),
    ]
    assert on_the_date[1].readings[0].value is NEVER


def test_each_path_reading_is_known_by_its_check(solved):
    """ADR-021, acceptance 6: every observation is known by its window date."""
    for attempt, _ in solved.values():
        for check in attempt.decisions.checks:
            for reading in check.readings:
                if reading.available_on is not None:
                    assert reading.available_on <= check.on
