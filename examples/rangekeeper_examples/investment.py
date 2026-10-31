"""A finite investment teaching model with separate author/formulate/specify/report steps.

This module is an example consumer, not a new domain schema. Generated Values own
all parameters and outputs. Construction has no random, solver or storage effects.

A date Value, ``sale_date``, decides the sale. ``specify`` fixes it to the last day of
a period, or with a rule that ``stop_gain_resale_rule`` makes (ADR-021).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, cast
from uuid import uuid4

from rangekeeper.duration import Frequency, Periods, PeriodTiming, offset
from rangekeeper.finance import financial
from rangekeeper.flow import Flow, Movement
from rangekeeper.model import (
    Definitions,
    Formulation,
    Measure,
    Metadata,
    Model,
    Reference,
    System,
    Update,
    Value,
    ValueKind,
)
from rangekeeper.model.expression.authoring import (
    add,
    divide,
    equal,
    literal,
    multiply,
    power,
)
from rangekeeper.model.expression.authoring import reference as ref
from rangekeeper.model.formulation import declare
from rangekeeper.quantity import Quantity
from rangekeeper.schema.records import Assignment
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.specification import Rule, Specification, Window
from rangekeeper.specification.targets import assign_flow, unknown_flow

_DEFAULTS = dict(
    units="AUD",
    start_date=date(2020, 1, 1),
    num_periods=10,
    initial_pgi=100.0,
    addl_pgi_per_period=0.0,
    growth_rate=0.02,
    vacancy_rate=0.05,
    opex_pgi_ratio=0.35,
    capex_pgi_ratio=0.1,
    cap_rate=0.05,
    discount_rate=0.07,
    acquisition_price=1000.0,
)
# The sale date, and the Flows that follow from it.
_CONTROLS = ("sale_date", "holding", "sale")
_FULL = ("base_pgi", "pgi", "vacancy", "egi", "opex", "noi", "capex", "ncf")
_HORIZON = (
    "potential_sale",
    "operations",
    "disposition",
    "total",
    "discounted",
    "horizon_pv",
)


def _own(model: Model) -> dict[str, Value]:
    """Return the Values of the Formulation that ``author`` makes."""
    if model.system is None:
        raise ValueError("Investment requires a System")
    matches = [
        f
        for f in model.system.formulations or ()
        if f.name == "Investment inputs and outputs"
    ]
    if len(matches) != 1:
        raise ValueError("expected one authored Investment formulation")
    return {v.key: v for v in matches[0].values or ()}


def values(model: Model) -> dict[str, Value]:
    """Return the example's Values by key, with no code/name fallback."""
    controls = {key: model.value(key=key) for key in _CONTROLS}
    return {**_own(model), **controls}


def author(
    parameters: Mapping | None = None,
    *,
    factors: Flow | None = None,
    cap_rates: Flow | None = None,
) -> Model:
    """Declare parameters and unresolved result shapes; all periods are annual.

    Operating year one follows the acquisition year. The final extra operating
    period supplies next-period income for reversion. ``factors`` records the
    space market price factors of one market path, such as
    ``paths[key]["space_market_price_factors"]``; without it, each factor is 1.
    ``cap_rates`` records a path of capitalization rates that replaces the
    scalar cap rate in the reversion. Each covers exactly these N+1 periods.
    Factors and rates are dimensionless, not currency.
    """
    p = {**_DEFAULTS, **(parameters or {})}
    if set(p) - set(_DEFAULTS):
        raise ValueError("unknown investment parameter")
    if type(p["num_periods"]) is not int or p["num_periods"] < 1:
        raise ValueError("num_periods must be positive")
    if (
        any(
            not 0 <= p[name] < 1
            for name in ("vacancy_rate", "opex_pgi_ratio", "capex_pgi_ratio")
        )
        or p["cap_rate"] <= 0
    ):
        raise ValueError("invalid investment ratios")
    periods = Periods(
        start=offset(value=p["start_date"], frequency=Frequency.YEAR),
        frequency=Frequency.YEAR,
        count=p["num_periods"] + 1,
    )
    base = Model.create(metadata=Metadata(id=uuid4(), schema_version="1.0.0"))
    money, ratio = uuid4(), uuid4()
    records = []
    for name in (
        "initial_pgi",
        "addl_pgi_per_period",
        "growth_rate",
        "vacancy_rate",
        "opex_pgi_ratio",
        "capex_pgi_ratio",
        "cap_rate",
        "discount_rate",
        "acquisition_price",
    ):
        monetary = name in ("initial_pgi", "addl_pgi_per_period", "acquisition_price")
        records.append(
            Value(
                id=uuid4(),
                key=name,
                kind=ValueKind.MEASUREMENT,
                measure=money if monetary else ratio,
                quantity=Quantity(
                    magnitude=p[name], units=p["units"] if monetary else "dimensionless"
                ),
            )
        )
    for name in (*_FULL, *_HORIZON):
        ps = periods if name in _FULL else periods[:-1]
        flow = _paid_at_last_day(ps, (None,) * len(ps), units=p["units"], prefix="p")
        records.append(
            Value(id=uuid4(), key=name, kind=ValueKind.FLOW, measure=money, flow=flow)
        )
    records.append(
        Value(id=uuid4(), key="pv", kind=ValueKind.MEASUREMENT, measure=money)
    )
    paths = {"space_market_price_factors": factors, "reversion_cap_rates": cap_rates}
    for key, path in paths.items():
        if path is None and key == "reversion_cap_rates":
            continue
        amounts = (1,) * len(periods) if path is None else _path_amounts(path, periods)
        records.append(
            Value(
                id=uuid4(),
                key=key,
                kind=ValueKind.FLOW,
                measure=ratio,
                flow=_paid_at_last_day(
                    periods, amounts, units="dimensionless", prefix="p"
                ),
            )
        )
    # 1 in the last sale period: the resale rule reads it, so a sale always happens.
    final = (0,) * (p["num_periods"] - 1) + (1,)
    records.append(
        Value(
            id=uuid4(),
            key="final_period",
            kind=ValueKind.FLOW,
            measure=ratio,
            flow=_paid_at_last_day(
                periods[:-1], final, units="dimensionless", prefix="p"
            ),
        )
    )
    system = cast(dict[str, Any], base.system.to_data() if base.system else {})
    system.setdefault("formulations", []).append(
        Formulation(
            id=uuid4(), name="Investment inputs and outputs", values=tuple(records)
        ).to_data()
    )
    definitions = cast(
        dict[str, Any], base.definitions.to_data() if base.definitions else {}
    )
    definitions.setdefault("measures", []).extend(
        [
            Measure(
                id=money,
                code=f"money_{money.hex}",
                name="Investment amount",
                units=p["units"],
            ).to_data(),
            Measure(
                id=ratio,
                code=f"ratio_{ratio.hex}",
                name="Periodic factor",
                units="dimensionless",
            ).to_data(),
        ]
    )
    authored = base.revise(
        Update(
            system=System.from_data(system),
            definitions=Definitions.from_data(definitions),
        )
    )
    return _with_sale_controls(authored, periods=periods[:-1])


def _with_sale_controls(model: Model, *, periods: Periods) -> Model:
    """Add the sale date, and the holding and sale Flows that follow from it.

    The sale period holds 1 in both Flows, so its operating income counts. Later
    periods hold 0.
    """
    draft = model.edit()
    controls = draft.add_entity(code="sale_controls", classification="sale_controls")
    controls.date(key="sale_date")
    controls.flow(key="holding", units="dimensionless", periods=periods)
    controls.flow(key="sale", units="dimensionless", periods=periods)
    controls.equations(
        "sale = rx.flow.event(amount=1, on=sale_date)",
        "holding = 1 - sale.cumulative() + sale",
    )
    return draft.commit()


def _path_amounts(path: Flow, periods: Periods) -> tuple[float, ...]:
    """Return the amounts of a market path Flow over the investment periods."""
    if [m.period for m in path.movements] != list(periods):
        raise ValueError("a market path must cover the complete investment horizon")
    return tuple(m.number for m in path.movements)


def _inputs(model):
    own = values(model)
    return own, own["space_market_price_factors"], own.get("reversion_cap_rates")


def _sale_days(model: Model) -> tuple[date, ...]:
    """Return the day on which a sale in each period happens: its last day."""
    return tuple(m.resolve() for m in _flow(values(model)["total"]).movements)


def formulate(model: Model) -> Model:
    """Declare growth, operating, reversion, control and discount equations only.

    Reversion uses next-period NCF. A recorded path of capitalization rates can
    replace the scalar rate. The controls include the sale period's operating
    income. No recorded magnitudes are substituted into the mathematics.
    ``author`` declares the equations of the controls.
    """
    v, factors, caps = _inputs(model)
    equations = []

    def r(name, key=None):
        return ref(
            Reference(target=v[name].id)
            if key is None
            else Reference(
                target=next(m.id for m in _flow(v[name]).movements if m.key == key)
            )
        )

    def set_equation(name, key, rhs):
        equations.append((name + "/" + (key or "scalar"), equal(r(name, key), rhs)))

    for i, item in enumerate(_flow(v["pgi"]).movements):
        key = item.key
        set_equation(
            "base_pgi",
            key,
            add(
                multiply(
                    r("initial_pgi"),
                    power(add(literal(1), r("growth_rate")), literal(i)),
                ),
                multiply(literal(i), r("addl_pgi_per_period")),
            ),
        )
        set_equation(
            "pgi",
            key,
            multiply(
                r("base_pgi", key),
                ref(
                    Reference(
                        target=next(
                            m.id for m in factors.flow.movements if m.key == key
                        )
                    )
                ),
            ),
        )
        for name, fraction in [
            ("vacancy", "vacancy_rate"),
            ("opex", "opex_pgi_ratio"),
            ("capex", "capex_pgi_ratio"),
        ]:
            set_equation(
                name, key, multiply(multiply(literal(-1), r(fraction)), r("pgi", key))
            )
        set_equation("egi", key, add(r("pgi", key), r("vacancy", key)))
        set_equation("noi", key, add(r("egi", key), r("opex", key)))
        set_equation("ncf", key, add(r("noi", key), r("capex", key)))
    discounted_operations = None
    total = None
    for i, item in enumerate(_flow(v["total"]).movements):
        key, next_key = item.key, _flow(v["ncf"]).movements[i + 1].key
        holding = ref(Reference(target=_flow(v["holding"]).movements[i].id))
        sale = ref(Reference(target=_flow(v["sale"]).movements[i].id))
        cap = (
            ref(Reference(target=caps.flow.movements[i].id)) if caps else r("cap_rate")
        )
        set_equation("potential_sale", key, divide(r("ncf", next_key), cap))
        set_equation("operations", key, multiply(r("ncf", key), holding))
        set_equation("disposition", key, multiply(r("potential_sale", key), sale))
        set_equation("total", key, add(r("operations", key), r("disposition", key)))
        divisor = power(add(literal(1), r("discount_rate")), literal(i + 1))
        set_equation("discounted", key, divide(r("total", key), divisor))
        discounted_operations = (
            divide(r("ncf", key), divisor)
            if discounted_operations is None
            else add(discounted_operations, divide(r("ncf", key), divisor))
        )
        set_equation(
            "horizon_pv",
            key,
            add(discounted_operations, divide(r("potential_sale", key), divisor)),
        )
        total = (
            r("discounted", key) if total is None else add(total, r("discounted", key))
        )
    set_equation("pv", None, total)
    declarations = declare(
        id=uuid4(),
        name="Investment equations",
        equations=equations,
        # The market path inputs are own Values of the example.
        values=[x.id for x in _own(model).values()],
    )
    assert model.system is not None
    data = cast(dict[str, Any], model.system.to_data())
    data["formulations"].append(declarations.to_data())
    return model.revise(Update(system=System.from_data(data)))


def specify(
    model: Model, *, rule: Rule | None = None, sale_period: int | None = None
) -> Specification:
    """Explicitly fix input parameters/path and select result unknowns.

    The sale date is fixed to the last day of ``sale_period``, or decided by
    ``rule``. Without either, the sale is in the final period. This call alone does
    not solve, save or alter any Model.
    """
    v, factors, caps = _inputs(model)
    days = _sale_days(model)
    if rule is not None and sale_period is not None:
        raise ValueError("choose a rule or a fixed sale period")
    sale_period = len(days) if sale_period is None else sale_period
    if type(sale_period) is not int or not 1 <= sale_period <= len(days):
        raise ValueError("sale period outside investment horizon")
    assignments = [
        Assignment(target=Reference(target=item.id), quantity=item.quantity)
        for item in v.values()
        if item.kind is ValueKind.MEASUREMENT and item.quantity is not None
    ]
    assignments.extend(assign_flow(model, factors.id))
    assignments.extend(assign_flow(model, v["final_period"].id))
    if caps:
        assignments.extend(assign_flow(model, caps.id))
    unknowns = (
        Reference(target=v["pv"].id),
        *(
            target
            for name in (*_FULL, *_HORIZON, "holding", "sale")
            for target in unknown_flow(model, v[name].id)
        ),
    )
    specification = Specification(
        record=SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            model=model.id,
            assignments=tuple(assignments),
            unknowns=unknowns,
        ),
        model=model,
    )
    return specification.fix(sale_date=days[sale_period - 1] if rule is None else rule)


@dataclass(frozen=True)
class InvestmentReport:
    """Derived presentation results; canonical outputs remain in the accepted Model."""

    model: Model
    cashflows: Flow
    pv: Quantity
    npv: Quantity
    irr: financial.IrrResult
    sale_date: date


def _flow(value: Value) -> Flow:
    if value.flow is None:
        raise ValueError(f"{value.key} has no declared Flow")
    return value.flow


def _quantity(value: Value) -> Quantity:
    if value.quantity is None:
        raise ValueError(f"{value.key} remains unresolved")
    return value.quantity


def report(model: Model) -> InvestmentReport:
    """Calculate dated IRR on accepted quantities, using the dedicated financial library.

    PV comes from governing equations. Acquisition is at the preceding year end;
    zero post-sale entries are excluded from IRR timing. Missing results fail.
    """
    v = values(model)
    sale = [m for m in _flow(v["sale"]).movements if m.magnitude == 1]
    if len(sale) != 1:
        raise ValueError("investment output must have exactly one sale")
    sale_date = v["sale_date"].date
    assert sale_date is not None
    first_period = _flow(v["total"]).movements[0].period
    assert first_period is not None
    first = first_period.start
    from datetime import timedelta

    purchase = Movement(
        id=uuid4(),
        key="acquisition",
        date=first - timedelta(days=1),
        magnitude=-abs(_quantity(v["acquisition_price"]).number),
    )
    operating = tuple(
        Movement(id=uuid4(), key=m.key, date=m.date, magnitude=m.magnitude)
        for m in _flow(v["total"]).movements
        if m.resolve() <= sale_date
    )
    cashflows = Flow(units=_flow(v["total"]).units, movements=(purchase, *operating))
    pv = _quantity(v["pv"])
    if pv is None:
        raise ValueError("PV remains unresolved")
    return InvestmentReport(
        model,
        cashflows,
        pv,
        Quantity(
            magnitude=pv.number - abs(_quantity(v["acquisition_price"]).number),
            units=pv.units,
        ),
        financial.calculate_irr(flow=cashflows),
        sale_date,
    )


def stop_gain_resale_rule(
    model: Model,
    *,
    threshold: float = 1.2,
    minimum_holding_periods: int = 3,
) -> Rule:
    """Return a rule that sells at the first factor above a threshold, else at the end.

    Give it to ``specify``, which fixes ``sale_date`` with it. The market factor of a
    period is known on the last day of that period, so the rule checks on that day.
    It starts in the period that ``minimum_holding_periods`` gives, a positive count
    that includes the sale period. The threshold is dimensionless and strict.

    The condition holds in the last period through ``final_period``, so the rule
    always decides on or before that day. ``otherwise`` would act only after the last
    period, and a decision must not change a date before it.
    """
    days = _sale_days(model)
    if type(
        minimum_holding_periods
    ) is not int or not 1 <= minimum_holding_periods <= len(days):
        raise ValueError("minimum holding must lie within the declared horizon")
    window = Window(earliest=days[minimum_holding_periods - 1], latest=days[-1])
    condition = f"space_market_price_factors > {threshold} or final_period == 1"
    return window.where(condition=condition).first(otherwise=days[-1])


def horizon_returns(model: Model) -> Flow:
    """Calculate dated IRR for each hypothetical sale horizon from accepted amounts.

    These are hindsight alternatives, not rule decisions. Each sale includes
    the current period's operating amount and its potential sale proceeds.
    """
    from datetime import timedelta

    v = values(model)
    first_period = _flow(v["total"]).movements[0].period
    assert first_period is not None
    first = first_period.start
    purchase = Movement(
        id=uuid4(),
        key="acquisition",
        date=first - timedelta(days=1),
        magnitude=-abs(_quantity(v["acquisition_price"]).number),
    )
    result = []
    for index, sale in enumerate(_flow(v["potential_sale"]).movements):
        movements = [purchase]
        for i, amount in enumerate(_flow(v["ncf"]).movements[: index + 1]):
            if amount.magnitude is None or sale.magnitude is None:
                raise ValueError("horizon reporting requires resolved amounts")
            movements.append(
                Movement(
                    id=uuid4(),
                    key=amount.key,
                    date=amount.date,
                    magnitude=amount.number + (sale.number if i == index else 0),
                )
            )
        irr = financial.calculate_irr(
            flow=Flow(units=_flow(v["total"]).units, movements=tuple(movements))
        )
        result.append(
            Movement(id=uuid4(), key=sale.key, date=sale.date, magnitude=100 * irr.rate)
        )
    return Flow(units="percent", movements=tuple(result))


def _paid_at_last_day(periods, magnitudes, *, units, prefix):
    """Return a Flow over Periods, each Movement paid on the last day of its Period."""
    return Flow(
        units=units,
        movements=tuple(
            Movement(
                id=uuid4(),
                key=f"{prefix}{i + 1}",
                period=period,
                date=period.resolve(timing=PeriodTiming.LAST),
                magnitude=magnitude,
            )
            for i, (period, magnitude) in enumerate(
                zip(periods, magnitudes, strict=True)
            )
        ),
    )
