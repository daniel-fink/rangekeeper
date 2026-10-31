"""Flow-valued equations and equation functions in a solve (#276).

Each Model writes lesson 03's equations as text over Flows, with fixed date
Values. ``by_hand`` calculates the same cash flows with
the value functions of ``rk.flow`` and ``rk.finance``.
"""

from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.errors import Code, NumericalError, UnsupportedError
from rangekeeper.execution import Status, solve
from rangekeeper.quantity import isclose

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2032, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)
INPUTS = {
    "land_cost": "20e6 AUD",
    "works_cost": "60e6 AUD",
    "equity": "50e6 AUD",
    "rent": "8e6 AUD",
    "sale_amount": "120e6 AUD",
    "loan_rate": "6 % pa",
    "rate": "12 % pa",
}
EQUATIONS = (
    "land = -rx.flow.event(amount=land_cost, on=start_date)",
    "works = -rx.profile.uniform(total=works_cost, start=start_date, length=2 years)",
    "income = rx.profile.constant(initial=rent, start=start_date + 2 years)",
    "sale = rx.flow.event(amount=sale_amount, on=sale_date)",
    "net = land + works + income + sale",
    "need = -(net + interest).cumulative()",
    "principal = rx.max(0 AUD, need - equity)",
    "draws = principal.diff()",
    "interest = -rx.finance.interest(balance=principal, rate=loan_rate)",
    "equity_cash = net + interest + draws",
    "npv = rx.finance.npv(flow=equity_cash, rate=rate, on=start_date)",
    "irr = rx.finance.irr(flow=equity_cash)",
    "peak = need.max()",
)
FLOWS = (
    "land",
    "works",
    "income",
    "sale",
    "net",
    "need",
    "principal",
    "draws",
    "interest",
    "equity_cash",
)


def build(*equations: str) -> rk.Model:
    draft = rk.Model(name="Cascade").edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("land_cost", "works_cost", "equity", "npv", "peak", "sale_amount"):
        project.value(key=key, units="AUD")
    project.value(key="rent", units="AUD")
    for key in ("loan_rate", "rate", "irr"):
        project.value(key=key, units="% pa")
    project.date(key="start_date")
    project.date(key="sale_date")
    for key in FLOWS:
        project.flow(key=key, units="AUD", periods=YEARS)
    project.equations(*equations)
    return draft.commit()


MODEL = build(*EQUATIONS)


def levered() -> rk.Specification:
    return (
        MODEL.specify(name="Levered")
        .fix(INPUTS)
        .fix(start_date=date(2027, 1, 1), sale_date=date(2031, 1, 1))
    )


def aud(magnitude: float) -> rk.Quantity:
    return rk.Quantity(magnitude=magnitude, units="AUD")


def by_hand(land: float = 20e6) -> dict[str, list[float]]:
    """Return the cascade period by period, with the value functions."""
    works = rk.flow.Flow.from_profile(
        profile=rk.profile.Uniform(start=date(2027, 1, 1), length="2 years"),
        periods=YEARS,
        total=rk.Quantity(text="60e6 AUD"),
    )
    rent = rk.flow.Flow.from_profile(
        profile=rk.profile.Constant(start=date(2029, 1, 1)),
        periods=YEARS,
        initial=rk.Quantity(text="8e6 AUD"),
    )
    factor = rk.finance.interest(
        balance=rk.flow.Flow(units="AUD", amounts={p: aud(1) for p in YEARS}),
        rate=rk.Quantity(text="6 % pa"),
    )
    found: dict[str, list[float]] = {k: [] for k in ("need", "principal", "cash")}
    need = principal = 0.0
    for index in range(len(YEARS)):
        net = rent.movements[index].number - works.movements[index].number
        net += (-land if index == 0 else 0.0) + (120e6 if index == 4 else 0.0)
        # The interest is on this period's principal, so the period solves
        # principal = max(0, need - equity) with need = opening - net + r * principal.
        rate = factor.movements[index].number
        opening, before = principal, need - net
        excess = before - 50e6
        principal = excess / (1 - rate) if excess > 0 else 0.0
        interest = -rate * principal
        need = before - interest
        found["need"].append(need)
        found["principal"].append(principal)
        found["cash"].append(net + interest + principal - opening)
    return found


@pytest.fixture(scope="module")
def levered_outcome():
    return solve(specification=levered())


def test_the_cascade_solves_period_by_period(levered_outcome):
    levered_outcome.raise_for_status()
    expected = by_hand()
    for key, solved in (
        ("need", levered_outcome["need"]),
        ("principal", levered_outcome["principal"]),
        ("cash", levered_outcome["equity_cash"]),
    ):
        amounts = [m.number for m in solved.movements]
        assert amounts == pytest.approx(expected[key], abs=1e-3), key


def test_functions_after_the_affine_stage_read_the_solved_flows(levered_outcome):
    cash = levered_outcome["equity_cash"]
    assert isclose(
        actual=levered_outcome["irr"], expected=rk.finance.irr(flow=cash), relative=1e-9
    )
    assert isclose(
        actual=levered_outcome["npv"],
        expected=rk.finance.npv(flow=cash, rate="12 % pa", on=date(2027, 1, 1)),
        relative=1e-9,
    )
    assert levered_outcome["peak"] == levered_outcome["need"].max()


def test_a_fixed_irr_finds_the_land_cost():
    """Lesson 03 cell 15: the IRR fixed becomes its NPV row at that rate (#277)."""
    target = levered().fix(irr="15 % pa").free("land_cost")
    outcome = solve(specification=target).raise_for_status()
    assert isclose(
        actual=rk.finance.irr(flow=outcome["equity_cash"]),
        expected=rk.Quantity(text="15 % pa"),
        relative=1e-9,
    )


def require_no_sign_change(outcome: rk.execution.Outcome) -> None:
    """Check that ``outcome`` failed with the code of ``rk.finance.irr`` (#518)."""
    assert outcome.status is Status.FAILED
    assert [d.code for d in outcome.diagnostics if d.severity == "error"] == [
        Code.NO_SIGN_CHANGE
    ]
    with pytest.raises(NumericalError) as raised:
        outcome.raise_for_status()
    assert raised.value.code is Code.NO_SIGN_CHANGE
    assert raised.value.values["inflows"] in str(raised.value)
    assert raised.value.values["outflows"] in str(raised.value)


def test_a_solve_gives_no_irr_from_inflows_of_rounding_noise():
    """The sale leaves part of the loan unpaid, so the equity receives nothing (#518)."""
    require_no_sign_change(solve(specification=levered().fix(sale_amount="10e6 AUD")))


def test_a_fixed_irr_on_the_stressed_plan_finds_a_real_sign_change():
    target = levered().fix(sale_amount="10e6 AUD", irr="15 % pa").free("land_cost")
    outcome = solve(specification=target).raise_for_status()
    assert isclose(
        actual=rk.finance.irr(flow=outcome["equity_cash"]),
        expected=rk.Quantity(text="15 % pa"),
        relative=1e-9,
    )


def event_cash(**values: str) -> rk.Specification:
    """Return ``cash``: ``-cost`` on the first date and ``income`` on the sale date."""
    draft = rk.Model(name="Events").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="cost", units="AUD")
    project.value(key="income", units="AUD")
    project.value(key="irr", units="% pa")
    project.date(key="start_date")
    project.date(key="sale_date")
    project.flow(key="cash", units="AUD", periods=YEARS)
    project.equations(
        "cash = rx.flow.event(amount=income, on=sale_date)"
        " - rx.flow.event(amount=cost, on=start_date)",
        "irr = rx.finance.irr(flow=cash)",
    )
    return (
        draft.commit()
        .specify(name="Events")
        .fix(start_date=date(2027, 1, 1), sale_date=date(2031, 1, 1))
        .fix(**values)
    )


NOISE = "0.000000001 AUD"
SMALL = "0.00002 AUD"


def test_an_irr_of_a_small_inflow_above_the_tolerance_is_a_rate():
    outcome = solve(specification=event_cash(cost="1000 AUD", income=SMALL))
    outcome.raise_for_status()
    assert outcome["irr"] == rk.finance.irr(flow=outcome["cash"])


def test_an_irr_of_an_inflow_of_noise_is_not_a_rate():
    require_no_sign_change(
        solve(specification=event_cash(cost="1000 AUD", income=NOISE))
    )


@pytest.mark.parametrize("income", [NOISE, SMALL])
def test_a_fixed_irr_does_not_hold_on_a_small_inflow(income):
    """The NPV of a real outflow at a real rate is not zero: the row has no solution."""
    specification = event_cash(cost="1000 AUD", income=income, irr="15 % pa")
    assert solve(specification=specification).status is Status.INFEASIBLE


@pytest.mark.parametrize("income", [NOISE, "0 AUD"])
def test_a_fixed_irr_gives_no_solution_without_a_real_sign_change(income):
    """The NPV row holds at any rate here; ``rk.finance.irr`` gives no rate (#518)."""
    specification = event_cash(income=income, irr="15 % pa").free("cost")
    require_no_sign_change(solve(specification=specification))


def test_a_fixed_irr_solves_a_small_inflow_above_the_tolerance():
    specification = event_cash(income=SMALL, irr="15 % pa").free("cost")
    outcome = solve(specification=specification).raise_for_status()
    assert isclose(
        actual=rk.finance.irr(flow=outcome["cash"]),
        expected=rk.Quantity(text="15 % pa"),
        relative=1e-6,
    )


def test_a_fixed_irr_with_free_unknowns_stays_underdetermined():
    """The candidate holds one solution of many, so its sign change proves nothing."""
    specification = event_cash(irr="15 % pa").free("cost", "income")
    assert solve(specification=specification).status is Status.UNDERDETERMINED


def floor(amount: str) -> rk.execution.Outcome:
    """Solve ``paid.min() >= 5 AUD`` for a constant payment of ``amount``."""
    draft = rk.Model(name="Floor").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="amount", units="AUD")
    project.date(key="start_date")
    project.flow(key="paid", units="AUD", periods=YEARS)
    project.equations(
        "paid = rx.profile.constant(initial=amount, start=start_date)",
        "paid.min() >= 5 AUD",
    )
    model = draft.commit()
    return solve(
        specification=model.specify(name="Floor").fix(
            amount=amount, start_date=date(2027, 1, 1)
        )
    )


def test_a_bound_on_a_minimum_holds_in_every_period():
    """D5: ``x.min() >= c`` is ``x >= c`` in each period, an affine row each (#277)."""
    assert floor("6 AUD").status is Status.FEASIBLE
    below = floor("4 AUD")
    assert below.status is Status.INFEASIBLE
    rows = [d for d in below.diagnostics if d.code == Code.SOLVER_SCALING]
    assert rows  # the backend proved it, with the rows of the bound


def test_a_rate_that_the_solve_finds_is_not_affine():
    loose = levered().free("loan_rate").fix(npv="1e6 AUD")
    outcome = solve(specification=loose)
    assert outcome.status is Status.UNSUPPORTED
    with pytest.raises(UnsupportedError) as raised:
        outcome.raise_for_status()
    assert raised.value.code is Code.NONAFFINE_UNKNOWNS
