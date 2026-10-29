"""Equation text: ``parse`` makes Expression records and ``render`` writes them."""

import random
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID, uuid4

import pytest

import rangekeeper as rk
from rangekeeper.errors import (
    AmbiguousReferenceError,
    Code,
    EquationError,
    MissingReferenceError,
)
from rangekeeper.model.expression.authoring import (
    add,
    binary,
    date_literal,
    divide,
    equal,
    literal,
    multiply,
    reference,
    subtract,
)
from rangekeeper.model.expression.text import parse, render
from rangekeeper.quantity import UnitSystem, default_units
from rangekeeper.schema.enums import ExpressionKind, Operator
from rangekeeper.schema.records import Expression, Reference

KEYS = (
    "value",
    "noi",
    "cap_rate",
    "land_cost",
    "works_cost",
    "total_cost",
    "b_start",
)


@dataclass
class Names:
    """The names of one entity, and of one other entity by its code."""

    keys: dict[str, UUID] = field(default_factory=lambda: {k: uuid4() for k in KEYS})
    others: dict[str, dict[str, UUID]] = field(
        default_factory=lambda: {"building_a": {"income": uuid4()}}
    )
    duplicates: frozenset[str] = frozenset({"twin"})

    @property
    def units(self) -> UnitSystem:
        return default_units

    def value(self, path: tuple[str, ...]) -> UUID:
        if path[0] in self.duplicates:
            raise AmbiguousReferenceError(path[0], kind="Value", by="key")
        keys = self.keys if len(path) == 1 else self.others.get(path[0], {})
        if path[-1] not in keys:
            raise MissingReferenceError(
                path[-1], kind="Value", by="key", candidates=sorted(keys)[:2]
            )
        return keys[path[-1]]

    def key(self, target: Reference) -> str:
        found = {identity: key for key, identity in self.keys.items()}
        return found[target.target]


NAMES = Names()


def ref(key: str) -> Expression:
    return reference(Reference(target=NAMES.keys[key]))


def records(expression: Expression) -> object:
    """Return the exported records without the UUIDs of their Expression nodes."""

    def strip(data: object) -> object:
        if isinstance(data, dict):
            return {k: strip(v) for k, v in data.items() if k != "id"}
        if isinstance(data, list):
            return [strip(item) for item in data]
        return data

    return strip(expression.to_data())


def text(expression: Expression) -> str:
    return render(expression=expression, name=NAMES.key)


def negate(operand: Expression) -> Expression:
    return Expression(
        id=uuid4(), kind=ExpressionKind.UNARY, operator=Operator.NEGATE, operand=operand
    )


def logical_not(operand: Expression) -> Expression:
    return Expression(
        id=uuid4(),
        kind=ExpressionKind.UNARY,
        operator=Operator.LOGICAL_NOT,
        operand=operand,
    )


def failure(source: str) -> EquationError:
    with pytest.raises(EquationError) as caught:
        parse(text=source, names=NAMES)
    assert caught.value.text == source
    return caught.value


def test_text_makes_the_same_records_as_the_record_constructors():
    parsed = parse(text="value = noi / cap_rate", names=NAMES)
    assert records(parsed) == records(
        equal(ref("value"), divide(ref("noi"), ref("cap_rate")))
    )
    parsed = parse(
        text="total_cost = land_cost + works_cost * (1 - cap_rate)", names=NAMES
    )
    expected = equal(
        ref("total_cost"),
        add(
            ref("land_cost"),
            multiply(ref("works_cost"), subtract(literal(1.0), ref("cap_rate"))),
        ),
    )
    assert records(parsed) == records(expected)


def test_each_node_has_a_new_uuid():
    first = parse(text="value = noi / cap_rate", names=NAMES)
    second = parse(text="value = noi / cap_rate", names=NAMES)
    assert first.id != second.id
    assert first.operands[1].id != second.operands[1].id


@pytest.mark.parametrize(
    "quantity",
    ["20e6 AUD", "1 dimensionless", "7 % pa", "5 %", "750 AUD per sqm pa", "2 years"],
)
def test_a_literal_is_the_quantity_of_the_same_text(quantity):
    number, _, units = quantity.partition(" ")
    source = f"value = {number}" if units == "dimensionless" else f"value = {quantity}"
    parsed = parse(text=source, names=NAMES).operands[1]
    assert parsed.kind is ExpressionKind.QUANTITY
    assert parsed.quantity == rk.Quantity(text=quantity)
    assert type(parsed.quantity.magnitude) is type(rk.Quantity(text=quantity).magnitude)


def test_constants_are_boolean_and_never_literals():
    parsed = parse(text="b_start = NEVER or True != False", names=NAMES)
    never = parsed.operands[0].operands[1]
    assert records(never) == records(date_literal(rk.duration.NEVER))
    # NEVER is a date literal with never, as a date Value records it (#387).
    assert (never.kind, never.date) == (ExpressionKind.DATE, None)
    assert text(never) == "NEVER"
    assert text(date_literal(date(2027, 1, 1))) == "<date 2027-01-01>"
    assert [o.boolean for o in parsed.operands[1].operands] == [True, False]


def test_a_dotted_path_names_a_value_of_another_entity():
    parsed = parse(text="value = building_a.income", names=NAMES)
    assert parsed.operands[1].target.target == NAMES.others["building_a"]["income"]


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (
            equal(ref("value"), multiply(ref("noi"), ref("cap_rate"))),
            "value = noi * cap_rate",
        ),
        (
            multiply(add(ref("noi"), ref("value")), ref("cap_rate")),
            "(noi + value) * cap_rate",
        ),
        (
            subtract(ref("noi"), subtract(ref("value"), ref("cap_rate"))),
            "noi - (value - cap_rate)",
        ),
        (
            subtract(subtract(ref("noi"), ref("value")), ref("cap_rate")),
            "noi - value - cap_rate",
        ),
        (
            binary(
                Operator.POWER,
                ref("noi"),
                binary(Operator.POWER, ref("value"), ref("cap_rate")),
            ),
            "noi ** value ** cap_rate",
        ),
        (
            binary(
                Operator.POWER,
                binary(Operator.POWER, ref("noi"), ref("value")),
                ref("cap_rate"),
            ),
            "(noi ** value) ** cap_rate",
        ),
        (negate(add(ref("noi"), ref("value"))), "-(noi + value)"),
        (binary(Operator.POWER, negate(ref("noi")), ref("value")), "(-noi) ** value"),
        (multiply(literal(1.25), ref("noi")), "1.25 * noi"),
        (
            binary(Operator.LESS_THAN_OR_EQUAL, ref("noi"), literal(2e7, "AUD")),
            "noi <= 20000000 AUD",
        ),
        (
            binary(
                Operator.LOGICAL_AND,
                binary(Operator.GREATER_THAN_OR_EQUAL, ref("noi"), ref("value")),
                binary(Operator.LESS_THAN, ref("noi"), ref("cap_rate")),
            ),
            "noi >= value and noi < cap_rate",
        ),
        (
            binary(
                Operator.LOGICAL_OR,
                binary(Operator.LOGICAL_AND, ref("noi"), ref("value")),
                logical_not(ref("cap_rate")),
            ),
            "noi and value or not cap_rate",
        ),
        (
            logical_not(binary(Operator.LOGICAL_OR, ref("noi"), ref("value"))),
            "not (noi or value)",
        ),
        (equal(ref("noi"), logical_not(ref("value"))), "noi = (not value)"),
        (
            equal(equal(ref("noi"), ref("value")), ref("cap_rate")),
            "(noi = value) = cap_rate",
        ),
        (equal(ref("b_start"), date_literal(rk.duration.NEVER)), "b_start = NEVER"),
        (
            equal(ref("b_start"), date_literal(date(2027, 1, 1))),
            "b_start = <date 2027-01-01>",
        ),
    ],
)
def test_render_writes_equation_text_with_the_fewest_brackets(expression, expected):
    assert text(expression) == expected


@pytest.mark.parametrize(
    "source",
    [
        "noi = coverage * debt_service",
        "total_cost = land_cost + works_cost",
        "a_start = shared_start + 1 year",
        "b_start >= shared_start + 1 year",
        "reference_income = hotel_area * hotel_rent * (1 - hotel_vacancy)"
        " + residential_area * residential_rent * (1 - residential_vacancy)",
        "value <= 0.5 * (noi + 7 % pa * land_cost) and value >= 0 AUD",
        "b_start = NEVER or not b_start > a_open",
        "rate = 1.5e-07 * growth ** 2",
    ],
)
def test_canonical_text_reads_back_to_the_same_text(source):
    names = Names(
        keys={
            word: uuid4()
            for word in source.replace("(", " ").replace(")", " ").split()
            if word.isidentifier()
            and word not in ("and", "or", "not", "NEVER", "year", "AUD", "pa")
        }
    )
    parsed = parse(text=source, names=names)
    keys = {identity: key for key, identity in names.keys.items()}
    assert render(expression=parsed, name=lambda target: keys[target.target]) == source


def random_expression(generator: random.Random, depth: int) -> Expression:
    """Return a random expression tree; literals have no sign, as in text."""
    if depth == 0 or generator.random() < 0.2:
        if generator.random() < 0.5:
            return ref(generator.choice(KEYS))
        return literal(
            generator.choice((0.0, 1.0, 2.5, 0.001, 20e6, 1.5e-7)),
            generator.choice(
                ("dimensionless", "AUD", "% pa", "sqm", "year", "AUD per sqm pa")
            ),
        )
    if generator.random() < 0.2:
        build = generator.choice((negate, logical_not))
        return build(random_expression(generator, depth - 1))
    operator = generator.choice(
        [o for o in Operator if o not in (Operator.NEGATE, Operator.LOGICAL_NOT)]
    )
    return binary(
        operator,
        random_expression(generator, depth - 1),
        random_expression(generator, depth - 1),
    )


def test_rendered_records_read_back_to_the_same_records():
    generator = random.Random(145)
    for _ in range(500):
        expression = random_expression(generator, depth=4)
        assert records(parse(text=text(expression), names=NAMES)) == records(expression)


def test_an_unknown_key_names_its_position_and_the_nearest_keys():
    error = failure("total_cost = land_cost + work_cost")
    assert error.code is Code.REFERENCE_MISSING
    assert (error.start, error.end) == (25, 34)
    assert error.suggestions == ("b_start", "cap_rate")
    assert "work_cost" in str(error)
    assert failure("value = twin").code is Code.REFERENCE_AMBIGUOUS
    assert failure("value = building_b.income").code is Code.REFERENCE_MISSING


def test_invalid_units_name_the_unit_words():
    error = failure("value = 5 dollars + 3 AUD")
    assert error.code is Code.UNITS
    assert (error.start, error.end) == (10, 17)
    error = failure("value = 5 AUD per")
    assert error.code is Code.UNITS


@pytest.mark.parametrize(
    ("source", "start", "end", "suggestions"),
    [
        ("value = rk.max(noi, cap_rate)", 8, 14, ("rx.max",)),
        ("value = rk", 8, 10, ()),
        ("value = rx.max(noi, cap_rate)", 8, 14, ()),
        ("value = rx.finance.npv(flow=noi, rate=cap_rate, on=b_start)", 8, 22, ()),
        ("value = rx", 8, 10, ()),
        ("value = max(noi, cap_rate)", 8, 11, ("rx.max",)),
        ("value = noi.cumulative()", 8, 22, ()),
        ("value = (noi + cap_rate).total()", 9, 30, ()),
        ("value = (noi + cap_rate)(1)", 9, 23, ()),
        ("value = noi.a.b", 8, 15, ()),
        ("value = (noi + cap_rate).total", 9, 30, ()),
    ],
)
def test_functions_methods_and_members_are_not_available(
    source, start, end, suggestions
):
    error = failure(source)
    assert error.code is Code.EQUATION_FUNCTION
    assert (error.start, error.end, error.suggestions) == (start, end, suggestions)


def test_a_method_reports_a_missing_value_first():
    assert failure("value = nio.cumulative()").code is Code.REFERENCE_MISSING
