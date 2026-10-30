"""The Python form of equations (``rx``) makes the records of equation text (D32).

The equivalence tests of ADR-015: for each equation function, text and ``rx``
make identical records and the same canonical text; text reads back to the
same records; and a call evaluated on fixed data equals the value function
that it mirrors.
"""

import dataclasses
import random
from collections.abc import Callable
from datetime import date

import pytest

import rangekeeper as rk
import rangekeeper.expressions as rx
from rangekeeper.errors import Code, ContractError, EquationError
from rangekeeper.model.expression import terms, text
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.evaluation import evaluate_fixed
from rangekeeper.schema.enums import DomainKind, Operator
from rangekeeper.schema.records import Expression
from rangekeeper.shared.registry import Registry

YEARS = rk.duration.Periods(
    start=date(2027, 1, 1), frequency=rk.duration.Frequency.YEAR, count=3
)


def records(expression: Expression) -> object:
    """Return the exported records without the UUIDs of their Expression nodes."""

    def strip(data: object) -> object:
        if isinstance(data, dict):
            return {k: strip(v) for k, v in data.items() if k != "id"}
        if isinstance(data, list):
            return [strip(item) for item in data]
        return data

    return strip(expression.to_data())


@pytest.fixture
def draft():
    return rk.Model(name="Equations").edit()


@pytest.fixture
def project(draft):
    project = draft.add_entity(code="project", classification="project")
    project.value(key="noi", units="AUD pa")
    project.value(key="coverage", units="ratio")
    project.value(key="debt_service", units="AUD pa")
    project.value(key="cap_rate", units="ratio")
    project.value(key="value", units="AUD")
    project.flow(key="cash", units="AUD", periods=YEARS)
    project.flow(key="need", units="AUD", periods=YEARS)
    project.date(key="sale_date")
    project.value(key="growth", units="% pa")
    project.value(key="irr", units="% pa")
    project.flow(key="loan", units="AUD", periods=YEARS)
    return project


class Names:
    """The names of equation text on one entity handle."""

    units = rk.quantity.default_units

    def __init__(self, project) -> None:
        self.project = project

    def value(self, path: tuple[str, ...]):
        return self.project.ref(key=".".join(path))


def parsed(project, source: str) -> terms.Term:
    """Return the Term of equation text on the project."""
    return text.read(text=source, names=Names(project))


def committed(draft) -> list[Expression]:
    """Return the equations of the project in the committed revision."""
    (formulation,) = draft.commit().system.formulations
    return list(formulation.expressions)


def test_the_lesson_02_aside_gives_the_text_form(project):
    noi = project.ref(key="noi")
    coverage = project.ref(key="coverage")
    debt_service = project.ref(key="debt_service")
    assert (noi == coverage * debt_service).text == "noi = coverage * debt_service"


# Each equation in text, and the same equation in rx.
OPERATORS: list[tuple[str, Callable[..., object]]] = [
    (
        "noi = coverage * debt_service",
        lambda v: v["noi"] == v["coverage"] * v["debt_service"],
    ),
    (
        "value = noi * 1 year / cap_rate",
        lambda v: v["value"] == v["noi"] * "1 year" / v["cap_rate"],
    ),
    (
        "noi >= debt_service + 0 AUD pa",
        lambda v: v["noi"] >= v["debt_service"] + "0 AUD pa",
    ),
    (
        "noi - debt_service != 2 AUD pa",
        lambda v: v["noi"] - v["debt_service"] != "2 AUD pa",
    ),
    ("cap_rate ** 2 < 1", lambda v: v["cap_rate"] ** 2 < 1),
    ("-noi <= debt_service", lambda v: -v["noi"] <= v["debt_service"]),
    (
        "noi >= debt_service and cap_rate > 0 or not coverage < 1",
        lambda v: (
            ((v["noi"] >= v["debt_service"]) & (v["cap_rate"] > 0))
            | ~(v["coverage"] < 1)
        ),
    ),
    ("sale_date = NEVER", lambda v: v["sale_date"] == rk.duration.NEVER),
    (
        "rx.max(noi, 0 AUD pa) >= debt_service",
        lambda v: rx.max(v["noi"], "0 AUD pa") >= v["debt_service"],
    ),
    (
        "value = cash.at(on=sale_date)",
        lambda v: v["value"] == v["cash"].at(on=v["sale_date"]),
    ),
    ("value = cash.total()", lambda v: v["value"] == v["cash"].total()),
    ("need = cash.shift(by=-1)", lambda v: v["need"] == v["cash"].shift(by=-1)),
    (
        "need = rx.max(0 AUD, cash - need)",
        lambda v: v["need"] == rx.max("0 AUD", v["cash"] - v["need"]),
    ),
    (
        "need = rx.min(cash, need * 2)",
        lambda v: v["need"] == rx.min(v["cash"], v["need"] * 2),
    ),
    (
        "value = 2 * (cash + need).total()",
        lambda v: v["value"] == 2 * (v["cash"] + v["need"]).total(),
    ),
    # The catalogue (#278).
    ("need = cash.cumulative()", lambda v: v["need"] == v["cash"].cumulative()),
    ("need = cash.diff()", lambda v: v["need"] == v["cash"].diff()),
    (
        "need = cash.since(on=sale_date)",
        lambda v: v["need"] == v["cash"].since(on=v["sale_date"]),
    ),
    (
        "need = cash.until(on=NEVER)",
        lambda v: v["need"] == v["cash"].until(on=rk.duration.NEVER),
    ),
    (
        "value <= cash.first() + cash.last()",
        lambda v: v["value"] <= v["cash"].first() + v["cash"].last(),
    ),
    (
        "value = rx.max(0 AUD, cash.max() - cash.min())",
        lambda v: v["value"] == rx.max("0 AUD", v["cash"].max() - v["cash"].min()),
    ),
    (
        "need = -rx.flow.event(amount=value, on=sale_date)",
        lambda v: v["need"] == -rx.flow.event(amount=v["value"], on=v["sale_date"]),
    ),
    (
        "value = rx.finance.npv(flow=cash, rate=growth, on=sale_date)",
        lambda v: (
            v["value"]
            == rx.finance.npv(flow=v["cash"], rate=v["growth"], on=v["sale_date"])
        ),
    ),
    (
        "irr = rx.finance.irr(flow=loan)",
        lambda v: v["irr"] == rx.finance.irr(flow=v["loan"]),
    ),
    (
        "need = -rx.finance.interest(balance=loan, rate=7 % pa)",
        lambda v: v["need"] == -rx.finance.interest(balance=v["loan"], rate="7 % pa"),
    ),
    (
        "need = rx.profile.compounding(initial=value, rate=growth)",
        lambda v: (
            v["need"] == rx.profile.compounding(initial=v["value"], rate=v["growth"])
        ),
    ),
    (
        "need = rx.profile.linear(initial=value, rate=2 % pa)",
        lambda v: v["need"] == rx.profile.linear(initial=v["value"], rate="2 % pa"),
    ),
    (
        "need = rx.profile.constant(initial=value)",
        lambda v: v["need"] == rx.profile.constant(initial=v["value"]),
    ),
    (
        "need = rx.profile.uniform(total=value)",
        lambda v: v["need"] == rx.profile.uniform(total=v["value"]),
    ),
    (
        "need = -rx.profile.scurve(total=value)",
        lambda v: v["need"] == -rx.profile.scurve(total=v["value"]),
    ),
]
KEYS = (
    "growth",
    "irr",
    "loan",
    "noi",
    "coverage",
    "debt_service",
    "cap_rate",
    "value",
    "cash",
    "need",
    "sale_date",
)


@pytest.mark.parametrize(("source", "build"), OPERATORS, ids=[s for s, _ in OPERATORS])
def test_text_and_rx_make_identical_records_and_text(draft, project, source, build):
    handles = {key: project.ref(key=key) for key in KEYS}
    term = build(handles)
    assert isinstance(term, rx.Term)
    assert term.text == source
    assert records(term.to_expression()) == records(
        parsed(project, source).to_expression()
    )
    project.equations(source, term)
    from_text, from_rx = committed(draft)
    assert records(from_text) == records(from_rx)


def test_each_function_and_method_is_in_the_equivalence_tests():
    written = " ".join(source for source, _ in OPERATORS)
    for function in functions:
        spelled = (
            function.code if function.form.value == "function" else f".{function.name}("
        )
        assert spelled in written, function.code


def test_named_and_positional_arguments_make_the_same_records(project):
    noi, service = project.ref(key="noi"), project.ref(key="debt_service")
    by_name = terms.call("rx.max", left=noi, right=service)
    assert records(by_name.to_expression()) == records(
        rx.max(noi, service).to_expression()
    )
    assert by_name.text == "rx.max(noi, debt_service)"


def test_a_term_knows_its_kind_and_units(project):
    cash, noi = project.ref(key="cash"), project.ref(key="noi")
    assert (cash.total().kind, cash.total().units) == (DomainKind.QUANTITY, "AUD")
    assert rx.max("0 AUD", cash).kind is DomainKind.FLOW
    assert rx.max("0 AUD pa", noi).kind is DomainKind.QUANTITY
    assert (noi >= 1).kind is DomainKind.BOOLEAN
    assert (project.ref(key="sale_date") + "1 year").kind is DomainKind.DATE


def test_handles_build_equations_and_compare_by_id(project):
    noi = project.ref(key="noi")
    assert project.ref(key="noi").id == noi.id
    with pytest.raises(TypeError, match="no truth value"):
        bool(noi == project.ref(key="noi"))
    with pytest.raises(TypeError, match="no truth value"):
        if noi >= 1:
            pass
    assert {noi: 1}[noi] == 1
    with pytest.raises(TypeError, match="cannot use a list"):
        noi + [1]  # type: ignore[operator]
    with pytest.raises(TypeError, match="not a handle"):
        project.equations(noi)


def test_an_equation_is_boolean(project):
    with pytest.raises(ContractError, match="Boolean") as error:
        project.equations(project.ref(key="noi") + "1 AUD pa")
    assert error.value.code is Code.PREDICATE


@pytest.mark.parametrize(
    ("build", "code", "suggestions"),
    [
        (lambda v: v["cash"].at(on=v["noi"]), Code.EQUATION_FUNCTION, []),
        (lambda v: v["noi"].total(), Code.EQUATION_FUNCTION, []),
        (
            lambda v: terms.call("Flow.at", v["cash"], when=v["sale_date"]),
            Code.EQUATION_FUNCTION,
            ["on"],
        ),
        (lambda v: terms.call("Flow.at", v["cash"]), Code.EQUATION_FUNCTION, ["on="]),
        (
            lambda v: terms.call("Flow.at", v["cash"], v["sale_date"]),
            Code.EQUATION_FUNCTION,
            ["on="],
        ),
        (
            lambda v: terms.call("rx.mux", v["noi"], v["noi"]),
            Code.EQUATION_FUNCTION,
            ["rx.max", "rx.min"],
        ),
        (
            lambda v: terms.call("rx.max", v["noi"], left=v["noi"]),
            Code.EQUATION_FUNCTION,
            [],
        ),
        (lambda v: rx.max(v["noi"], v["sale_date"]), Code.EQUATION_FUNCTION, []),
    ],
)
def test_calls_are_checked_when_written(project, build, code, suggestions):
    handles = {key: project.ref(key=key) for key in KEYS}
    with pytest.raises(ContractError) as error:
        build(handles)
    assert error.value.code is code
    assert error.value.values["suggestions"] == suggestions


def test_text_reports_a_call_at_the_argument_that_fails(project):
    with pytest.raises(EquationError) as error:
        project.equations("value = cash.at(on=noi)")
    assert error.value.code is Code.EQUATION_FUNCTION
    assert error.value.text[error.value.start : error.value.end] == "on=noi"
    with pytest.raises(EquationError) as error:
        project.equations("value = cash.at(when=sale_date)")
    assert error.value.suggestions == ("on",)
    with pytest.raises(EquationError) as error:
        project.equations("value = rk.max(noi, debt_service)")
    assert error.value.suggestions == ("rx.max",)


def test_the_draft_adds_the_function_records_that_equations_call(draft, project):
    project.equations("value = cash.total()", "noi = rx.max(noi, debt_service)")
    project.equations(project.ref(key="value") >= project.ref(key="cash").total())
    model = draft.commit()
    codes = sorted(record.code for record in model.definitions.functions)
    assert codes == ["Flow.total", "rx.max"]
    assert {record.id for record in model.definitions.functions} == {
        functions.method(name="total").id,
        functions.function(name="max").id,
    }
    draft = model.edit()
    draft.entity(code="project").equations("value = cash.total() + 1 AUD")
    assert len(draft.commit().definitions.functions) == 2


# A call on fixed data equals its value function.

CASH = rk.flow.Flow(amounts=dict(zip(YEARS, (100, -50, 25), strict=True)), units="AUD")
LOAN = rk.flow.Flow(amounts=dict(zip(YEARS, (-100, 60, 60), strict=True)), units="AUD")
NEED = rk.flow.Flow(amounts=dict(zip(YEARS, (-10, 80, 30), strict=True)), units="AUD")
FIXED = {
    "noi": rk.Quantity(text="5 AUD pa"),
    "debt_service": rk.Quantity(text="7 AUD pa"),
    "cash": CASH,
    "need": NEED,
    "sale_date": date(2028, 6, 30),
    "value": rk.Quantity(text="90 AUD"),
    "growth": rk.Quantity(text="3 % pa"),
    "loan": LOAN,
}
# Each call in text, and the value function that it mirrors on FIXED.
MIRRORS: list[tuple[str, Callable[[], object]]] = [
    ("rx.max(noi, debt_service)", lambda: max(FIXED["noi"], FIXED["debt_service"])),
    ("rx.max(debt_service, noi)", lambda: max(FIXED["debt_service"], FIXED["noi"])),
    ("rx.min(noi, debt_service)", lambda: min(FIXED["noi"], FIXED["debt_service"])),
    (
        "rx.min(0 AUD, cash)",
        lambda: rk.flow.Flow(
            amounts=dict(zip(YEARS, (0, -50, 0), strict=True)), units="AUD"
        ),
    ),
    (
        "rx.max(0 AUD, cash - need)",
        lambda: rk.flow.Flow(
            amounts={
                period: max(0, a - b)
                for period, a, b in zip(
                    YEARS, (100, -50, 25), (-10, 80, 30), strict=True
                )
            },
            units="AUD",
        ),
    ),
    ("cash.at(on=sale_date)", lambda: CASH.at(on=date(2028, 6, 30))),
    ("cash.total()", lambda: CASH.total()),
    ("cash.shift(by=-1)", lambda: CASH.shift(by=-1)),
    ("(cash + need).total()", lambda: (CASH + NEED).total()),
    ("-cash.total() + 1 AUD", lambda: -CASH.total() + rk.Quantity(text="1 AUD")),
    # The catalogue (#278).
    ("cash.cumulative()", lambda: CASH.cumulative()),
    ("cash.diff()", lambda: CASH.diff()),
    ("cash.since(on=sale_date)", lambda: CASH.since(on=date(2028, 6, 30))),
    ("cash.until(on=sale_date)", lambda: CASH.until(on=date(2028, 6, 30))),
    ("cash.since(on=NEVER)", lambda: CASH.since(on=rk.duration.NEVER)),
    ("cash.first()", lambda: CASH.first()),
    ("cash.last()", lambda: CASH.last()),
    ("cash.min()", lambda: CASH.min()),
    ("cash.max()", lambda: CASH.max()),
    (
        "rx.flow.event(amount=value, on=sale_date)",
        lambda: rk.flow.Flow(
            amounts=dict(zip(YEARS, (0, 90, 0), strict=True)), units="AUD"
        ),
    ),
    (
        "rx.flow.event(amount=value, on=NEVER)",
        lambda: rk.flow.Flow(
            amounts=dict(zip(YEARS, (0, 0, 0), strict=True)), units="AUD"
        ),
    ),
    (
        "rx.finance.npv(flow=cash, rate=growth, on=sale_date)",
        lambda: rk.finance.npv(flow=CASH, rate="3 % pa", on=date(2028, 6, 30)),
    ),
    ("rx.finance.irr(flow=loan)", lambda: rk.finance.irr(flow=LOAN)),
    (
        "rx.finance.interest(balance=loan, rate=growth)",
        lambda: rk.finance.interest(balance=LOAN, rate="3 % pa"),
    ),
    (
        "rx.profile.compounding(initial=value, rate=growth)",
        lambda: rk.flow.Flow.from_profile(
            profile=rk.profile.Compounding(rate="3 % pa"),
            periods=YEARS,
            initial="90 AUD",
        ),
    ),
    (
        "rx.profile.linear(initial=value, rate=growth)",
        lambda: rk.flow.Flow.from_profile(
            profile=rk.profile.Linear(rate="3 % pa"), periods=YEARS, initial="90 AUD"
        ),
    ),
    (
        "rx.profile.constant(initial=value)",
        lambda: rk.flow.Flow.from_profile(
            profile=rk.profile.Constant(), periods=YEARS, initial="90 AUD"
        ),
    ),
    (
        "rx.profile.uniform(total=value)",
        lambda: rk.flow.Flow.from_profile(
            profile=rk.profile.Uniform(), periods=YEARS, total="90 AUD"
        ),
    ),
    (
        "rx.profile.scurve(total=value)",
        lambda: rk.flow.Flow.from_profile(
            profile=rk.profile.SCurve(), periods=YEARS, total="90 AUD"
        ),
    ),
]


@pytest.mark.parametrize(("source", "mirror"), MIRRORS, ids=[s for s, _ in MIRRORS])
def test_a_call_on_fixed_data_equals_its_value_function(project, source, mirror):
    term = parsed(project, source)
    values = {project.ref(key=key).id: value for key, value in FIXED.items()}
    result = evaluate_fixed(
        expression=term.to_expression(), values=values, periods=YEARS
    )
    assert result == mirror()


def test_each_function_and_method_is_evaluated_on_fixed_data():
    written = " ".join(source for source, _ in MIRRORS)
    for function in functions:
        spelled = (
            function.code if function.form.value == "function" else f".{function.name}("
        )
        assert spelled in written, function.code


def test_a_comparison_of_flows_holds_in_every_period(project):
    values = {project.ref(key=key).id: value for key, value in FIXED.items()}
    holds = parsed(project, "rx.max(0 AUD, cash) >= cash")
    assert evaluate_fixed(expression=holds.to_expression(), values=values) is True
    fails = parsed(project, "cash >= 0 AUD")
    assert evaluate_fixed(expression=fails.to_expression(), values=values) is False


# Random trees of operators, built with rx, read back from their text.


def random_term(generator: random.Random, handles: dict, depth: int):
    if depth == 0 or generator.random() < 0.25:
        if generator.random() < 0.6:
            return handles[
                generator.choice(("noi", "coverage", "debt_service", "cap_rate"))
            ]
        return generator.choice(("0 AUD pa", "2.5 % pa", "1.5e-07 ratio", 3, 0.5))
    if generator.random() < 0.15:
        return -terms.operand(random_term(generator, handles, depth - 1))
    if generator.random() < 0.15:
        return rx.max(
            random_term(generator, handles, depth - 1),
            random_term(generator, handles, depth - 1),
        )
    operator = generator.choice(
        (
            Operator.ADD,
            Operator.SUBTRACT,
            Operator.MULTIPLY,
            Operator.DIVIDE,
            Operator.POWER,
        )
    )
    return terms.binary(
        operator,
        random_term(generator, handles, depth - 1),
        random_term(generator, handles, depth - 1),
    )


def test_random_rx_trees_read_back_from_their_text(project):
    handles = {key: project.ref(key=key) for key in KEYS}
    generator = random.Random(309)
    for _ in range(300):
        left = terms.operand(random_term(generator, handles, depth=4))
        equation = left == handles["noi"]
        assert records(parsed(project, equation.text).to_expression()) == records(
            equation.to_expression()
        )


def test_a_flow_made_from_amounts_needs_the_periods_that_it_defines(project):
    term = parsed(project, "rx.flow.event(amount=value, on=sale_date)")
    values = {project.ref(key=key).id: value for key, value in FIXED.items()}
    with pytest.raises(ContractError) as error:
        evaluate_fixed(expression=term.to_expression(), values=values)
    assert error.value.code is Code.EQUATION_FUNCTION


@pytest.mark.parametrize(
    ("source", "part", "code"),
    [
        (
            "need = rx.finance.npv(flow=noi, rate=growth, on=sale_date)",
            "flow=noi",
            Code.EQUATION_FUNCTION,
        ),
        (
            "need = rx.finance.npv(flow=cash, rate=value, on=sale_date)",
            "rate=value",
            Code.UNITS,
        ),
        (
            "need = rx.finance.npv(cash, growth, sale_date)",
            "rx.finance.npv(cash, growth, sale_date)",
            Code.EQUATION_FUNCTION,
        ),
        (
            "need = rx.profile.uniform(total=value, length=2 AUD)",
            "length=2 AUD",
            Code.UNITS,
        ),
        (
            "need = rx.profile.uniform(total=value, start=noi)",
            "start=noi",
            Code.EQUATION_FUNCTION,
        ),
        (
            "need = rx.profile.compound(initial=value, rate=growth)",
            "rx.profile.compound",
            Code.EQUATION_FUNCTION,
        ),
        (
            "need = rx.flow.event(amount=value)",
            "rx.flow.event(amount=value)",
            Code.EQUATION_FUNCTION,
        ),
        (
            "need = cash.since(sale_date)",
            "cash.since(sale_date)",
            Code.EQUATION_FUNCTION,
        ),
    ],
)
def test_catalogue_calls_are_checked_when_written(project, source, part, code):
    with pytest.raises(EquationError) as error:
        project.equations(source)
    assert error.value.code is code
    assert error.value.text[error.value.start : error.value.end] == part


def test_text_suggests_the_nearest_function(project):
    with pytest.raises(EquationError) as error:
        project.equations("need = rx.profile.compound(initial=value, rate=growth)")
    assert error.value.suggestions[0] == "rx.profile.compounding"


@dataclasses.dataclass(frozen=True, kw_only=True)
class Step:
    """Growth profile: the initial amount, then twice it from the second Period."""

    takes = "initial"
    start: object = None

    def factors(self, *, periods):
        return tuple(1.0 if index == 0 else 2.0 for index, _ in enumerate(periods))


@pytest.fixture
def extension(monkeypatch):
    """Register a profile in copies of the two registries, so no other test sees it.

    The registries have no public way to remove a name, so the fixture
    replaces their tables for the test.
    """
    registry = Registry("profiles", type)
    for name in rk.profile.profiles.names():
        registry.register(name=name, implementation=rk.profile.profiles.get(name))
    registry.register(name="step_test", implementation=Step)
    monkeypatch.setattr(rk.profile, "profiles", registry)
    monkeypatch.setattr(functions, "_entries", dict(functions._entries))
    monkeypatch.setattr(functions, "_ids", dict(functions._ids))


def test_a_profile_from_the_extension_point_is_an_equation_function(project, extension):
    term = rx.profile.step_test(initial=project.ref(key="value"))
    assert term.text == "rx.profile.step_test(initial=value)"
    assert parsed(project, term.text).text == term.text
    values = {project.ref(key="value").id: rk.Quantity(text="90 AUD")}
    result = evaluate_fixed(
        expression=term.to_expression(), values=values, periods=YEARS
    )
    assert [m.number for m in result.movements] == [90, 180, 180]
    with pytest.raises(AttributeError):
        rx.profile.not_a_profile  # noqa: B018


def test_the_calls_of_lessons_05_and_07_parse_as_written(draft):
    """Lesson 05 cell 10 and lesson 07 cell 17c, as equations on their values.

    Cell 17c gives its terms to ``add_to`` (#283); here each term is the
    right side of an equation.
    """
    project = draft.add_entity(code="project", classification="project")
    for key, units in (("b_land_share", "ratio"), ("land_cost", "AUD")):
        project.value(key=key, units=units)
    for key in ("x_cost", "b_site_value"):
        project.value(key=key, units="AUD")
    project.value(key="x_income", units="AUD pa")
    for key in ("b_sale_date", "expansion_date", "x_open"):
        project.date(key=key)
    for key in ("rent_index", "b_site_sale", "works", "income"):
        units = "ratio" if key == "rent_index" else "AUD"
        project.flow(key=key, units=units, periods=YEARS)
    sources = (
        "b_site_value = b_land_share * land_cost * rent_index.at(on=b_sale_date)",
        "b_site_sale = rx.flow.event(amount=b_site_value, on=b_sale_date)",
        "x_open = expansion_date + 1 year",
        "works = -rx.profile.uniform(total=x_cost, start=expansion_date, length=1 year)",
        "income = rx.profile.constant(initial=x_income, start=x_open)",
    )
    project.equations(*sources)
    for source in sources:
        assert parsed(project, source).text == source
