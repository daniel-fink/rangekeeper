"""Date Values and date Expressions in a Model (G15, G50, D26)."""

from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

import rangekeeper as rk
from rangekeeper.duration import NEVER
from rangekeeper.errors import ValidationError
from rangekeeper.model import ValueKind
from rangekeeper.model.expression.authoring import (
    add,
    binary,
    date_literal,
    literal,
    reference,
    subtract,
)
from rangekeeper.model.expression.evaluation import compare_dates, evaluate_date
from rangekeeper.quantity import default_units
from rangekeeper.schema.enums import ExpressionKind, Operator
from rangekeeper.schema.records import Expression, Reference, Value


def uid(name):
    return str(uuid5(NAMESPACE_URL, "date-values-test/" + name))


def date_value(key, **content):
    return {"id": uid(key), "key": key, "kind": "date", **content}


def model_data(values, expressions=()):
    """Return Model data with one project Entity, its values and its equations."""
    data = {
        "metadata": {"id": uid("model"), "schema_version": "1.0.0", "name": "Dates"},
        "definitions": {
            "measures": [
                {"id": uid("AUD"), "code": "AUD", "name": "AUD", "units": "AUD"}
            ]
        },
        "system": {
            "entities": [
                {
                    "id": uid("project"),
                    "code": "project",
                    "characteristics": {"values": list(values)},
                }
            ]
        },
    }
    if expressions:
        data["system"]["formulations"] = [
            {
                "id": uid("formulation"),
                "code": "project",
                "expressions": [item.to_data() for item in expressions],
                "constraints": [
                    {"id": uid(f"constraint {index}"), "predicate": str(item.id)}
                    for index, item in enumerate(expressions)
                ],
            }
        ]
    return data


def ref(key):
    return reference(Reference(target=uid(key)))


def test_a_date_value_records_a_date_never_or_nothing():
    plan = rk.Model.from_data(
        data=model_data(
            [
                date_value("start_date", date="2027-01-01"),
                date_value("b_start", never="never"),
                date_value("sale_date"),
            ]
        )
    )
    start, b_start, sale = plan.system.entities[0].characteristics.values
    assert (start.kind, start.date, start.never) == (
        ValueKind.DATE,
        date(2027, 1, 1),
        None,
    )
    assert (b_start.date, b_start.never) == (None, NEVER)
    assert (sale.date, sale.never, sale.measure) == (None, None, None)
    again = rk.io.json.loads(text=rk.io.json.dumps(plan), kind=rk.Model)
    assert again.to_data() == plan.to_data()


def test_a_date_value_record_takes_a_date_or_never():
    value = Value(id=uid("v"), key="start_date", kind=ValueKind.DATE, never=NEVER)
    assert value.to_data()["never"] == "never"
    dated = value.replace(date=date(2027, 1, 1))
    assert dated.to_data()["date"] == "2027-01-01"


@pytest.mark.parametrize(
    "value",
    [
        date_value("start_date", date="2027-01-01", never="never"),
        date_value("start_date", measure=uid("AUD")),
        date_value("start_date", quantity={"magnitude": "1", "units": "AUD"}),
        {
            "id": uid("land"),
            "key": "land",
            "kind": "property",
            "date": "2027-01-01",
        },
        {
            "id": uid("land"),
            "key": "land",
            "kind": "measurement",
            "measure": uid("AUD"),
            "never": "never",
        },
    ],
)
def test_date_content_belongs_only_to_a_date_value(value):
    with pytest.raises(ValidationError, match="Value"):
        rk.Model.from_data(data=model_data([value]))


def test_date_literals_and_never():
    assert date_literal(date(2027, 1, 1)).to_data()["date"] == "2027-01-01"
    never = date_literal(NEVER)
    assert (never.kind, never.never, never.date) == (ExpressionKind.DATE, NEVER, None)
    with pytest.raises(TypeError):
        date_literal(None)
    with pytest.raises(ValueError):
        Expression(id=uid("e"), kind=ExpressionKind.DATE)


def test_a_never_literal_has_the_shape_of_a_never_value() -> None:
    # One stored shape for NEVER: kind date with never, as a date Value (#387).
    literal = date_literal(NEVER).to_data()
    assert {k: v for k, v in literal.items() if k != "id"} == {
        "kind": "date",
        "never": "never",
    }
    assert "never" not in [kind.value for kind in ExpressionKind]
    with pytest.raises(ValueError):
        Expression(
            id=uid("e"), kind=ExpressionKind.DATE, date=date(2027, 1, 1), never=NEVER
        )


DATES = [
    date_value("start_date", date="2027-01-01"),
    date_value("b_start"),
    {"id": uid("land"), "key": "land", "kind": "measurement", "measure": uid("AUD")},
]


def test_date_equations_validate_in_a_model():
    equations = [
        binary(
            Operator.GREATER_THAN_OR_EQUAL,
            ref("b_start"),
            add(ref("start_date"), literal(1, "year")),
        ),
        binary(Operator.EQUAL, ref("b_start"), date_literal(NEVER)),
        binary(
            Operator.LESS_THAN,
            subtract(ref("b_start"), literal(3, "months")),
            add(literal(2, "years"), date_literal(date(2030, 1, 1))),
        ),
    ]
    model = rk.Model.from_data(data=model_data(DATES, equations))
    assert len(model.system.formulations[0].expressions) == 3


ARITHMETIC = "adds or subtracts a length"
LENGTH = "a date length is in days"
COMPARISON = "a date compares only with a date or NEVER"


@pytest.mark.parametrize(
    ("equation", "message"),
    [
        # The difference of two dates is not defined.
        (
            binary(
                Operator.EQUAL,
                subtract(ref("b_start"), ref("start_date")),
                literal(1, "year"),
            ),
            ARITHMETIC,
        ),
        (
            binary(
                Operator.EQUAL,
                ref("land"),
                binary(Operator.MULTIPLY, ref("start_date"), literal(2)),
            ),
            ARITHMETIC,
        ),
        # A length is in calendar units.
        (
            binary(
                Operator.EQUAL,
                ref("b_start"),
                add(ref("start_date"), literal(1, "AUD")),
            ),
            LENGTH,
        ),
        (
            binary(Operator.EQUAL, ref("b_start"), add(ref("start_date"), literal(1))),
            LENGTH,
        ),
        (binary(Operator.LESS_THAN, ref("b_start"), ref("land")), COMPARISON),
        (binary(Operator.EQUAL, ref("b_start"), literal(0, "AUD")), COMPARISON),
    ],
)
def test_other_date_operations_are_rejected(equation, message):
    with pytest.raises(ValidationError, match=message):
        rk.Model.from_data(data=model_data(DATES, [equation]))


def test_evaluate_a_date_expression():
    values = {UUID(uid("start_date")): date(2027, 1, 31)}

    def evaluate(node):
        return evaluate_date(node, values, units=default_units)

    assert evaluate(add(ref("start_date"), literal(1, "month"))) == date(2027, 2, 28)
    assert evaluate(add(literal(1, "year"), ref("start_date"))) == date(2028, 1, 31)
    assert evaluate(subtract(ref("start_date"), literal(1, "year"))) == date(
        2026, 1, 31
    )
    assert evaluate(
        add(add(ref("start_date"), literal(1, "year")), literal(2, "weeks"))
    ) == date(2028, 2, 14)
    assert evaluate(add(date_literal(NEVER), literal(1, "year"))) is NEVER
    assert evaluate(date_literal(date(2030, 1, 1))) == date(2030, 1, 1)


def test_never_equals_never_and_is_later_than_every_date():
    assert compare_dates(Operator.EQUAL, NEVER, NEVER)
    assert compare_dates(Operator.GREATER_THAN, NEVER, date.max)
    assert compare_dates(Operator.GREATER_THAN_OR_EQUAL, NEVER, date(2027, 1, 1))
    assert not compare_dates(Operator.LESS_THAN, NEVER, date(2027, 1, 1))
    assert compare_dates(Operator.NOT_EQUAL, NEVER, date(2027, 1, 1))
    assert compare_dates(Operator.LESS_THAN, date(2027, 1, 1), date(2028, 1, 1))


def test_date_content_survives_a_bundle(tmp_path):
    pytest.importorskip("pyarrow")
    from rangekeeper.io.bundle import Reader, write

    equations = [
        binary(Operator.EQUAL, ref("b_start"), date_literal(NEVER)),
        binary(Operator.LESS_THAN, ref("start_date"), date_literal(date(2030, 1, 1))),
    ]
    values = [
        date_value("start_date", date="2027-01-01"),
        date_value("b_start", never="never"),
        date_value("sale_date"),
    ]
    plan = rk.Model.from_data(data=model_data(values, equations))
    write(root=tmp_path / "bundle", model=plan)
    assert Reader(root=tmp_path / "bundle").model().to_data() == plan.to_data()
