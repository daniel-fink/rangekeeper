"""A finite investment teaching model with separate author/formulate/specify/report steps.

This module is an example consumer, not a new domain schema. Generated Values own
all parameters and outputs. Construction has no random, solver or storage effects.
"""

from rangekeeper.specification.policy import ActionKind
from rangekeeper.model import ValueKind

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from datetime import date
from uuid import UUID, uuid4
from rangekeeper.model import (
    Model,
    Metadata,
    Definitions,
    Measure,
    Quantity,
    System,
    Formulation,
    Value,
    Update,
)
from rangekeeper.model.flux import Flow, Movement
from rangekeeper.model.scenario import ScenarioRealization
from rangekeeper.schema.records import (
    Reference,
    Assignment,
    Policy,
    Specification as SpecificationRecord,
)
from rangekeeper.model.duration import make_periods, offset, Frequency, PeriodTiming

from rangekeeper.model.formulation import declare
from rangekeeper.model.formulation.authoring import identify, identify_tree
from rangekeeper.model.formulation.flow import aligned, shape
from rangekeeper.model.expression.authoring import binary
from rangekeeper.specification.policy import Decision, Rule, Action, ObservationBinding
from rangekeeper.model import Reference
from rangekeeper.model.expression import Operator
from rangekeeper.model.expression.authoring import (
    reference as ref,
    literal,
    add,
    subtract,
    multiply,
    divide,
    power,
    equal,
)
from rangekeeper.specification import Specification
from rangekeeper.specification.targets import unknown_flow, assign_flow
from rangekeeper.calculations import financial, series
from rangekeeper.model.scenario.view import Market

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
_FULL = ("base_pgi", "pgi", "vacancy", "egi", "opex", "noi", "capex", "ncf")
_HORIZON = (
    "potential_sale",
    "holding",
    "sale",
    "operations",
    "disposition",
    "total",
    "discounted",
    "horizon_pv",
)


def values(model: Model) -> dict[str, Value]:
    """Return the example's owner-local Values by key, with no code/name fallback."""
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


def author(
    parameters: Mapping | None = None, *, scenario: Market | None = None
) -> Model:
    """Declare parameters and unresolved result shapes; all periods are annual.

    Operating year one follows the acquisition year. The final extra operating
    period supplies next-period income for reversion. A supplied scenario must
    cover exactly these N+1 periods. Factors are dimensionless, not currency.
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
    periods = make_periods(
        offset(p["start_date"], frequency=Frequency.YEAR),
        frequency=Frequency.YEAR,
        count=p["num_periods"] + 1,
    )
    base = (
        scenario.model
        if scenario
        else Model.create(metadata=Metadata(id=uuid4(), schema_version="0.7.0"))
    )
    if scenario and tuple(scenario.realization.plan.periods) != periods:
        raise ValueError("scenario periods must match the complete investment horizon")
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
        control = name in ("holding", "sale")
        flow = Flow.from_periods(
            ps,
            (None,) * len(ps),
            units="dimensionless" if control else p["units"],
            keys=tuple(f"p{i + 1}" for i in range(len(ps))),
            dates=tuple(period.resolve(timing=PeriodTiming.LAST) for period in ps),
        )
        records.append(
            Value(
                id=uuid4(),
                key=name,
                kind=ValueKind.FLOW,
                measure=ratio if control else money,
                flow=flow,
            )
        )
    records.append(
        Value(id=uuid4(), key="pv", kind=ValueKind.MEASUREMENT, measure=money)
    )
    # Keep a canonical local factor input when no realized scenario is supplied.
    if scenario is None:
        records.append(
            Value(
                id=uuid4(),
                key="space_market_price_factors",
                kind=ValueKind.FLOW,
                measure=ratio,
                flow=Flow.from_periods(
                    periods,
                    (1,) * len(periods),
                    units="dimensionless",
                    keys=tuple(f"p{i + 1}" for i in range(len(periods))),
                    dates=tuple(
                        period.resolve(timing=PeriodTiming.LAST) for period in periods
                    ),
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
    return base.revise(
        Update(
            system=System.from_data(system),
            definitions=Definitions.from_data(definitions),
        )
    )


def _inputs(model):
    own = values(model)
    if "space_market_price_factors" in own:
        return own, own["space_market_price_factors"], None
    realizations = model.provenance.scenarios if model.provenance else ()
    if not realizations or len(realizations) != 1:
        raise ValueError("select one scenario for this investment example")
    result = Market(model, realizations[0])
    cap_name = (
        "implied_reversion_cap_rates"
        if realizations[0].plan.method == "market"
        else "asset_market"
    )
    return own, result.space_market_price_factors, result.value(cap_name)


def formulate(model: Model) -> Model:
    """Declare growth, operating, reversion, control and discount equations only.

    Reversion uses next-period NCF. A scenario's explicit capitalization path can
    replace the scalar rate. The controls include the sale period's operating
    income. No recorded magnitudes are substituted into the mathematics.
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
    for i, item in enumerate(_flow(v["holding"]).movements):
        key, next_key = item.key, _flow(v["ncf"]).movements[i + 1].key
        cap = (
            ref(Reference(target=caps.flow.movements[i].id)) if caps else r("cap_rate")
        )
        set_equation("potential_sale", key, divide(r("ncf", next_key), cap))
        set_equation("operations", key, multiply(r("ncf", key), r("holding", key)))
        set_equation(
            "disposition", key, multiply(r("potential_sale", key), r("sale", key))
        )
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
        values=[x.id for x in v.values()] + [factors.id] + ([caps.id] if caps else []),
    )
    assert model.system is not None
    data = cast(dict[str, Any], model.system.to_data())
    data["formulations"].append(declarations.to_data())
    return model.revise(Update(system=System.from_data(data)))


def specify(
    model: Model, *, policy: Policy | None = None, sale_period: int | None = None
) -> Specification:
    """Explicitly fix input parameters/path and select result unknowns and controls.

    A policy owns controls exclusively. Without one, sale_period defaults to the
    final horizon. This call alone does not solve, save or alter any Model.
    """
    v, factors, caps = _inputs(model)
    count = len(_flow(v["holding"]).movements)
    if policy is not None and sale_period is not None:
        raise ValueError("choose a policy or fixed sale period")
    sale_period = count if sale_period is None else sale_period
    if type(sale_period) is not int or not 1 <= sale_period <= count:
        raise ValueError("sale period outside investment horizon")
    assignments = [
        Assignment(target=Reference(target=item.id), quantity=item.quantity)
        for item in v.values()
        if item.kind is ValueKind.MEASUREMENT and item.quantity is not None
    ]
    assignments.extend(assign_flow(model, factors.id))
    if caps:
        assignments.extend(assign_flow(model, caps.id))
    if policy is None:
        for i in range(count):
            assignments.extend(
                (
                    Assignment(
                        target=Reference(target=_flow(v["holding"]).movements[i].id),
                        quantity=Quantity(
                            magnitude=int(i < sale_period), units="dimensionless"
                        ),
                    ),
                    Assignment(
                        target=Reference(target=_flow(v["sale"]).movements[i].id),
                        quantity=Quantity(
                            magnitude=int(i + 1 == sale_period), units="dimensionless"
                        ),
                    ),
                )
            )
    unknowns = (
        Reference(target=v["pv"].id),
        *(
            target
            for name in (*_FULL, *_HORIZON)
            if name not in ("holding", "sale")
            for target in unknown_flow(model, v[name].id)
        ),
    )
    return Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
            model=model.id,
            assignments=tuple(assignments),
            unknowns=unknowns,
            policy=policy,
        )
    )


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
    sale_date = sale[0].resolve()
    first_period = _flow(v["total"]).movements[0].period
    assert first_period is not None
    first = first_period.start_inclusive
    from datetime import timedelta

    purchase = Movement(
        id=uuid4(),
        key="acquisition",
        date=first - timedelta(days=1),
        magnitude=-abs(_quantity(v["acquisition_price"]).magnitude),
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
            magnitude=pv.magnitude - abs(_quantity(v["acquisition_price"]).magnitude),
            units=pv.units,
        ),
        financial.calculate_irr(cashflows),
        sale_date,
    )


def build_stop_gain_resale_policy(
    model: Model,
    *,
    id: UUID | None = None,
    pricing_factor: UUID | None = None,
    holding: UUID | None = None,
    sale: UUID | None = None,
    threshold: float = 1.2,
    minimum_holding_periods: int = 3,
    mapping: Mapping[UUID, UUID] | None = None,
) -> Policy:
    """Declare one sale at first factor > threshold, otherwise at the final horizon.

    Decisions occur on each period's last included date. The sale period has
    holding=1 and sale=1, so its operating cashflow is included. Later controls
    are zero. Minimum holding is a positive count including the sale period.
    An explicit mapping selects observed Movement UUIDs when the market extends beyond the
    investment horizon. Availability still prevents future observations.
    Threshold is dimensionless. No path, cashflow or Model is changed.
    """
    if pricing_factor is None and holding is None and sale is None:
        own, factors, _ = _inputs(model)
        pricing_factor, holding, sale = factors.id, own["holding"].id, own["sale"].id
        if mapping is None:
            mapping = {
                h.id: p.id
                for h, p in zip(own["holding"].flow.movements, factors.flow.movements)
            }
    elif pricing_factor is None or holding is None or sale is None:
        raise ValueError("explicit resale roles must supply all three Values")
    id = id or uuid4()
    if mapping is None:
        rows = aligned(model, (pricing_factor, sale), holding)
    else:
        factors = {m.id: m for m in shape(model, pricing_factor).movements}
        controls = aligned(model, (sale,), holding)
        if set(mapping) != {h.id for h, _ in controls} or not set(
            mapping.values()
        ) <= set(factors):
            raise ValueError("policy mapping must cover every control coordinate")
        rows = [(h, (factors[mapping[h.id]], matches[0])) for h, matches in controls]
    if (
        not rows
        or type(minimum_holding_periods) is not int
        or not 1 <= minimum_holding_periods <= len(rows)
    ):
        raise ValueError("minimum holding must lie within the declared horizon")
    targets = tuple(
        ref
        for h, (_, s) in rows
        for ref in (Reference(target=h.id), Reference(target=s.id))
    )

    def assign(ref, magnitude):
        return Action(
            kind=ActionKind.ASSIGN,
            target=ref,
            quantity=Quantity(magnitude=magnitude, units="dimensionless"),
        )

    def sell(index):
        actions = []
        for offset, (h, (_, s)) in enumerate(rows[index:]):
            actions.extend(
                (
                    assign(Reference(target=h.id), int(offset == 0)),
                    assign(Reference(target=s.id), int(offset == 0)),
                )
            )
        return (*actions, Action(kind=ActionKind.TERMINATE))

    points = []
    for index, (h, (factor, s)) in enumerate(rows):
        at = h.resolve(timing=PeriodTiming.LAST)
        observation = ObservationBinding(
            name="pricing_factor", target=Reference(target=factor.id)
        )
        condition = identify_tree(
            id,
            "resale",
            str(h.id),
            binary(Operator.GREATER_THAN, ref(observation.target), literal(threshold)),
        )
        rules = (
            (
                Rule(
                    id=identify(id, str(h.id), "rule"),
                    condition=condition,
                    actions=sell(index),
                ),
            )
            if index + 1 >= minimum_holding_periods
            else ()
        )
        fallback = (
            sell(index)
            if index == len(rows) - 1
            else (assign(Reference(target=h.id), 1), assign(Reference(target=s.id), 0))
        )
        points.append(
            Decision(
                id=identify(id, str(h.id), "point"),
                at=at,
                observations=(observation,),
                rules=rules,
                fallback=fallback,
            )
        )
    return Policy(id=id, targets=targets, decisions=tuple(points))


def horizon_returns(model: Model) -> Flow:
    """Calculate dated IRR for each hypothetical sale horizon from accepted amounts.

    These are hindsight alternatives, not policy decisions. Each sale includes
    the current period's operating amount and its potential sale proceeds.
    """
    from datetime import timedelta

    v = values(model)
    first_period = _flow(v["total"]).movements[0].period
    assert first_period is not None
    first = first_period.start_inclusive
    purchase = Movement(
        id=uuid4(),
        key="acquisition",
        date=first - timedelta(days=1),
        magnitude=-abs(_quantity(v["acquisition_price"]).magnitude),
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
                    magnitude=amount.magnitude + (sale.magnitude if i == index else 0),
                )
            )
        irr = financial.calculate_irr(
            Flow(units=_flow(v["total"]).units, movements=tuple(movements))
        )
        result.append(
            Movement(id=uuid4(), key=sale.key, date=sale.date, magnitude=100 * irr.rate)
        )
    return Flow(units="percent", movements=tuple(result))
