"""The equity-first cascade of lesson 03 (D2), one value for each year, for #308.

Lesson 03 writes the cascade on Flows with ``rx.max``:
``funding_need = -(net_cash_flow + loan_interest).cumulative()``,
``loan_principal = rx.max(0 AUD, funding_need - equity)``,
``loan_draws = loan_principal.diff()`` and
``equity_cash_flow = net_cash_flow + loan_interest + loan_draws``. Flow
equations, the function catalogue and ``irr`` are not in the solve yet
(#278, #279, #277), so this Model writes the same equations for each year
with scalar values, with ``rx.max`` as a call of a declared Function, and the
target IRR as the NPV row at that rate that #277 makes from a fixed IRR.
``by_hand`` calculates the same cascade in plain Python.
"""

from collections.abc import Callable
from uuid import UUID, uuid4

import rangekeeper as rk
from rangekeeper.model import Definitions, Update
from rangekeeper.model.expression.authoring import (
    add,
    equal,
    literal,
    multiply,
    reference,
    subtract,
)
from rangekeeper.schema.enums import DomainKind, ExpressionKind, ParameterKind
from rangekeeper.schema.records import (
    Call,
    Domain,
    Expression,
    Function,
    Parameter,
    Reference,
)

YEARS = (1, 2, 3, 4)
LAND = 25e6
WORKS = {1: 30e6, 2: 40e6, 3: 10e6, 4: 0.0}
INCOME = {1: 0.0, 2: 0.0, 3: 15e6, 4: 20e6}
SALE = 120e6
EQUITY = 50e6
LOAN_RATE = 0.06
TARGET_RATE = 0.15


def functions() -> tuple[Function, ...]:
    """Return the ``rx.max`` and ``rx.min`` Functions: two quantity operands each.

    They have the codes of the equation-function catalogue (#309).
    """
    quantity = Domain(kind=DomainKind.QUANTITY)

    def declared(code: str, name: str) -> Function:
        return Function(
            id=uuid4(),
            code=code,
            name=name,
            version="1",
            parameters=tuple(
                Parameter(
                    name=name,
                    domain=quantity,
                    kind=ParameterKind.POSITIONAL_OR_NAMED,
                    required=True,
                )
                for name in ("a", "b")
            ),
            result=quantity,
            semantics=f"The {name.lower()} of the two operands.",
            unit_rule="The units of the first operand.",
        )

    return (declared("rx.max", "Larger"), declared("rx.min", "Smaller"))


def with_functions(model: rk.Model) -> rk.Model:
    """Return a revision of ``model`` that declares ``functions()``."""
    definitions = model.definitions or Definitions()
    return model.revise(Update(definitions=definitions.replace(functions=functions())))


def call(model: rk.Model, code: str, *operands: Expression) -> Expression:
    """Return a call of the Function with ``code`` that ``model`` declares."""
    assert model.definitions is not None and model.definitions.functions
    function = next(f for f in model.definitions.functions if f.code == code)
    return Expression(
        id=uuid4(),
        kind=ExpressionKind.CALL,
        call=Call(function=function.id, arguments=operands),
    )


def build_model() -> rk.Model:
    """Return the cascade Model: inputs, the yearly cascade and the target NPV row."""
    draft = rk.Model(name="Equity-first cascade").edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("land_cost", "sale", "equity", "target_npv"):
        project.value(key=key, units="AUD")
    project.value(key="loan_rate", units="ratio")
    for year in YEARS:
        for key in (
            "works",
            "income",
            "net",
            "interest",
            "need",
            "principal",
            "draws",
            "equity_cash",
        ):
            project.value(key=f"{key}_{year}", units="AUD")
    model = with_functions(draft.commit())
    draft = model.edit()
    project = draft.entity(code="project")

    def r(key: str) -> Expression:
        return reference(Reference(target=project.ref(key=key).id))

    project.equations(*equations(model, r))
    return draft.commit()


def equations(
    model: rk.Model, r: Callable[[str], Expression]
) -> tuple[Expression, ...]:
    """Return the cascade's equations, year by year, and the target NPV row.

    Each equation has its own nodes: ``r`` makes a new reference each time.
    """
    found = []

    def opening(key: str, year: int) -> Expression:
        """Return the value of ``key`` at the end of the year before, zero at first."""
        return literal(0, "AUD") if year == YEARS[0] else r(f"{key}_{year - 1}")

    for year in YEARS:
        net = subtract(r(f"income_{year}"), r(f"works_{year}"))
        if year == YEARS[0]:
            net = subtract(net, r("land_cost"))
        if year == YEARS[-1]:
            net = add(net, r("sale"))
        found.append(equal(r(f"net_{year}"), net))
        interest = multiply(
            literal(-1, "dimensionless"),
            multiply(r("loan_rate"), opening("principal", year)),
        )
        found.append(equal(r(f"interest_{year}"), interest))
        cash = add(r(f"net_{year}"), r(f"interest_{year}"))
        found.append(equal(r(f"need_{year}"), subtract(opening("need", year), cash)))
        excess = subtract(r(f"need_{year}"), r("equity"))
        found.append(
            equal(
                r(f"principal_{year}"),
                call(model, "rx.max", literal(0, "AUD"), excess),
            )
        )
        draws = subtract(r(f"principal_{year}"), opening("principal", year))
        found.append(equal(r(f"draws_{year}"), draws))
        cash = add(r(f"net_{year}"), r(f"interest_{year}"))
        found.append(equal(r(f"equity_cash_{year}"), add(cash, r(f"draws_{year}"))))
    discounted = [
        multiply(
            literal((1 + TARGET_RATE) ** -year, "dimensionless"),
            r(f"equity_cash_{year}"),
        )
        for year in YEARS
    ]
    total = discounted[0]
    for item in discounted[1:]:
        total = add(total, item)
    found.append(equal(r("target_npv"), total))
    return tuple(found)


MODEL = build_model()


def q(text: str) -> rk.Quantity:
    return rk.Quantity(text=text)


def inputs() -> dict[str, rk.Quantity]:
    """Return the fixed inputs other than the land cost."""
    found = {
        "sale": rk.Quantity(magnitude=SALE, units="AUD"),
        "equity": rk.Quantity(magnitude=EQUITY, units="AUD"),
        "loan_rate": rk.Quantity(magnitude=LOAN_RATE, units="ratio"),
    }
    for year in YEARS:
        found[f"works_{year}"] = rk.Quantity(magnitude=WORKS[year], units="AUD")
        found[f"income_{year}"] = rk.Quantity(magnitude=INCOME[year], units="AUD")
    return found


def forward() -> rk.Specification:
    """Return the levered forward case: the land cost fixed, everything else free."""
    return (
        MODEL.specify(name="Levered")
        .fix(inputs())
        .fix(land_cost=rk.Quantity(magnitude=LAND, units="AUD"))
    )


def target() -> rk.Specification:
    """Return the target case: the NPV at the target rate fixed at zero, the land cost free."""
    return MODEL.specify(name="Target").fix(inputs()).fix(target_npv=q("0 AUD"))


def by_hand(land: float) -> dict[str, float]:
    """Return the cascade's values for a land cost, calculated in plain Python."""
    values: dict[str, float] = {}
    need = principal = 0.0
    npv = 0.0
    for year in YEARS:
        net = INCOME[year] - WORKS[year]
        net -= land if year == YEARS[0] else 0.0
        net += SALE if year == YEARS[-1] else 0.0
        interest = -LOAN_RATE * principal
        need = need - (net + interest)
        draws = max(0.0, need - EQUITY) - principal
        principal = max(0.0, need - EQUITY)
        cash = net + interest + draws
        npv += cash * (1 + TARGET_RATE) ** -year
        values.update(
            {
                f"net_{year}": net,
                f"interest_{year}": interest,
                f"need_{year}": need,
                f"principal_{year}": principal,
                f"draws_{year}": draws,
                f"equity_cash_{year}": cash,
            }
        )
    values["target_npv"] = npv
    return values


def target_land() -> float:
    """Return the land cost at which the NPV at the target rate is zero, by bisection."""
    low, high = 0.0, 200e6
    for _ in range(200):
        middle = (low + high) / 2
        if by_hand(middle)["target_npv"] > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def ids(*keys: str) -> tuple[UUID, ...]:
    """Return the Value UUIDs of these keys."""
    return tuple(MODEL.value(key=key).id for key in keys)
