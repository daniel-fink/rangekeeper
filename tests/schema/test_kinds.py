"""Generated records hold data; owners add behaviour and decode as the owner class."""

from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.schema import records
from rangekeeper.schema.index import walk
from rangekeeper.schema.kinds import record_type, register
from rangekeeper.schema.records import _OWNERS, _TYPES

OWNED = {
    "Distribution": rk.model.Distribution,
    "Flow": rk.flow.Flow,
    "Movement": rk.flow.Movement,
    "Period": rk.duration.Period,
    "Quantity": rk.Quantity,
    "Span": rk.duration.Span,
}


def test_each_owned_kind_resolves_to_its_owner():
    assert set(_OWNERS) == set(OWNED)
    for kind, owner in OWNED.items():
        assert record_type(kind) is owner
        assert _TYPES[kind] in owner.__bases__
    assert record_type("Value") is records.Value


def test_generated_records_have_no_behaviour():
    for kind in OWNED:
        generated = _TYPES[kind]
        assert not {"check", "first", "number", "trim", "sample"} & set(vars(generated))


def test_construction_and_decoding_return_the_owner():
    period = records.Period(start=date(2026, 1, 1), end=date(2026, 2, 1))
    assert type(period) is rk.duration.Period
    assert period.last == date(2026, 1, 31)
    decoded = records.Period.from_data(period.to_data())
    assert type(decoded) is rk.duration.Period and decoded == period
    flow = rk.flow.Flow.from_periods(periods=[period], magnitudes=[1.0], units="USD")
    assert type(flow.movements[0]) is rk.flow.Movement
    assert type(flow.movements[0].period) is rk.duration.Period
    value = records.Value(
        id=flow.movements[0].id,
        key="v",
        kind=rk.model.ValueKind.FLOW,
        measure=None,
        flow=flow,
    )
    assert type(value.flow) is rk.flow.Flow
    assert type(value.replace(key="w").flow) is rk.flow.Flow
    kinds = {type(record) for record, _, _ in walk(value)}
    assert {rk.flow.Flow, rk.flow.Movement, rk.duration.Period} <= kinds


def test_span_is_a_period():
    span = records.Span(name="hold", start=date(2026, 1, 1), end=date(2027, 1, 1))
    assert isinstance(span, rk.duration.Period) and span.first == date(2026, 1, 1)


@pytest.mark.parametrize(
    "body, message",
    [
        ({}, "__slots__"),
        ({"__slots__": (), "__init__": lambda self: None}, "constructor"),
        ({"__slots__": (), "start": None}, "shadows fields: start"),
    ],
)
def test_register_rejects_unsafe_owners(body, message):
    cls = type(
        "Period", (records.Period,), {"__module__": "rangekeeper.duration", **body}
    )
    with pytest.raises(TypeError, match=message):
        register(cls)


def test_register_rejects_a_second_owner_or_another_module():
    second = type(
        "Period",
        (records.Period,),
        {"__module__": "rangekeeper.duration", "__slots__": ()},
    )
    with pytest.raises(TypeError, match="already registered"):
        register(second)
    elsewhere = type(
        "Period", (records.Period,), {"__module__": "example", "__slots__": ()}
    )
    with pytest.raises(TypeError, match="owned by rangekeeper.duration"):
        register(elsewhere)
    unowned = type(
        "Value", (records.Value,), {"__module__": "example", "__slots__": ()}
    )
    with pytest.raises(TypeError, match="owned by None"):
        register(unowned)


def test_generated_slots_match_the_packaged_artifact_and_children_are_cached():
    import json
    from importlib.resources import files

    from rangekeeper.schema.validation import slots_for

    packaged = json.loads(
        files("rangekeeper.schema").joinpath("slots.json").read_text()
    )
    assert {kind: slots_for(kind) for kind in _TYPES} == {
        kind: packaged[kind] for kind in _TYPES
    }
    periods = rk.duration.Periods(
        start=date(2026, 1, 1), frequency=rk.duration.Frequency.MONTH, count=3
    )
    flow = rk.flow.Flow.from_periods(
        periods=periods, magnitudes=[1.0, 2.0, 3.0], units="USD"
    )
    assert flow.movements is flow.movements
    assert flow.movements[0].period is flow.movements[0].period
    assert flow.replace(units="AUD").movements == flow.movements
