"""The Python form of equations (``rx``) makes the records of equation text (D32).

The equivalence tests of ADR-015: for each equation function, text and ``rx``
make identical records and the same canonical text; text reads back to the
same records; and a call evaluated on fixed data equals the value function
that it mirrors.
"""

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
        "value = 2 * (cash + need).total()",
        lambda v: v["value"] == 2 * (v["cash"] + v["need"]).total(),
    ),
]
FLOWS = frozenset({"cash", "need"})
KEYS = (
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
    if FLOWS.isdisjoint(source.replace("(", " ").replace(".", " ").split()):
        # Flow-valued equations commit with #279.
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
            ["rx.max"],
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
NEED = rk.flow.Flow(amounts=dict(zip(YEARS, (-10, 80, 30), strict=True)), units="AUD")
FIXED = {
    "noi": rk.Quantity(text="5 AUD pa"),
    "debt_service": rk.Quantity(text="7 AUD pa"),
    "cash": CASH,
    "need": NEED,
    "sale_date": date(2028, 6, 30),
}
# Each call in text, and the value function that it mirrors on FIXED.
MIRRORS: list[tuple[str, Callable[[], object]]] = [
    ("rx.max(noi, debt_service)", lambda: max(FIXED["noi"], FIXED["debt_service"])),
    ("rx.max(debt_service, noi)", lambda: max(FIXED["debt_service"], FIXED["noi"])),
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
]


@pytest.mark.parametrize(("source", "mirror"), MIRRORS, ids=[s for s, _ in MIRRORS])
def test_a_call_on_fixed_data_equals_its_value_function(project, source, mirror):
    term = parsed(project, source)
    values = {project.ref(key=key).id: value for key, value in FIXED.items()}
    result = evaluate_fixed(expression=term.to_expression(), values=values)
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
