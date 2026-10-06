"""Record methods preserve wire presence, identity and numerical contracts."""

from datetime import date
import inspect
import json
from uuid import UUID, uuid4

import pytest

from rangekeeper._records import UNSET
from rangekeeper._schema import records as r
from rangekeeper.calculations.series import aggregate, align
from rangekeeper.errors import ValidationError
from rangekeeper.model import Model
from rangekeeper.model._index import Index
from rangekeeper.model.validation import validate

DAY = date(2026, 1, 1)


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"magnitude": None},
        {"claims": None},
        {"claims": []},
        {"magnitude": 0, "claims": []},
    ],
)
def test_replacement_preserves_presence_and_input(fields):
    original = r.Movement.from_data({"key": "a", "date": DAY.isoformat(), **fields})
    before = original.to_data()
    copy = original.replace(key="b", magnitude=UNSET, claims=UNSET)
    assert type(copy) is r.Movement
    assert copy is not original
    assert copy.to_data() == {**before, "key": "b"}
    assert original.to_data() == before
    assert original.replace() == original
    assert copy.replace(magnitude=None).has_field("magnitude")
    assert copy.replace(claims=()).claims == ()
    assert copy.replace(claims=None).claims is None


def test_replacement_checks_types_and_copies_mutable_content():
    movement = r.Movement(key="a", date=DAY)
    with pytest.raises(TypeError):
        movement.replace(unknown=True)
    with pytest.raises((TypeError, ValidationError)):
        movement.replace(magnitude="bad")
    with pytest.raises((ValueError, ValidationError)):
        movement.replace(magnitude=float("inf"))
    with pytest.raises(TypeError):
        movement.replace(period=r.Quantity(magnitude=1, units="m"))
    payload = {"nested": [1]}
    claim = r.Claim(
        id=uuid4(), kind="asserted", method=r.Method(code="manual"), content=payload
    )
    replacement = claim.replace(content=payload)
    payload["nested"].append(2)
    assert replacement.to_data()["content"] == {"nested": [1]}
    with pytest.raises(AttributeError):
        replacement.content = {}


def test_decoded_records_keep_methods_and_schema_inheritance():
    period = r.Period(start=DAY, end=date(2026, 2, 1))
    flow = r.Flow.from_periods([period], [2], units="m")
    value = r.Value(id=uuid4(), key="area", kind="flow", measure=uuid4(), flow=flow)
    decoded = r.Value.from_json(json.dumps(value.to_data())).flow
    assert type(decoded) is r.Flow
    assert type(decoded.movements[0]) is r.Movement
    assert type(decoded.movements[0].period) is r.Period
    assert decoded.check() is decoded
    assert decoded.movements[0].number == 2.0
    assert decoded.movements[0].resolve(timing="last_day") == date(2026, 1, 31)
    assert decoded.movements[0].replace(magnitude=3).number == 3.0
    span = r.Span(start=period.start, end=period.end, name="January")
    assert isinstance(span, r.Period)
    assert type(span.replace(name="Month")) is r.Span
    assert span.check() is span
    assert span.resolve(timing="end") == period.end


def test_check_clean_and_number_have_distinct_roles():
    flow = r.Flow.from_events([DAY, date(2026, 1, 2)], [None, 0], units="m")
    before = flow.to_data()
    assert flow.check() is flow
    with pytest.raises(ValueError, match="unresolved"):
        flow.check(resolved=True)
    with pytest.raises(ValueError, match="unresolved"):
        _ = flow.movements[0].number
    assert flow.movements[1].number == 0.0
    assert flow.clean().movements == (flow.movements[1],)
    assert flow.clean(remove_zeroes=True).movements == ()
    assert flow.to_data() == before


@pytest.mark.parametrize("reducer, expected", [("sum", 3), ("min", 1), ("max", 2)])
def test_reduction_shares_units_claims_and_coverage(reducer, expected):
    a, b = UUID(int=1), UUID(int=2)
    left = r.Flow(
        units="m", movements=(r.Movement(key="a", date=DAY, magnitude=1, claims=(a,)),)
    )
    right = r.Flow(
        units="cm",
        movements=(r.Movement(key="a", date=DAY, magnitude=200, claims=(b, a)),),
    )
    aligned = align([left, right])
    result = aligned.reduce(reducer=reducer)
    assert result == aggregate([left, right], reducer=reducer)
    assert result.flow.movements[0].number == expected
    assert result.flow.movements[0].claims == (a, b)
    assert result.coverage == (1.0,)
    assert right.units == "cm"


@pytest.mark.parametrize("reducer", ["sum", "min", "max"])
def test_reduction_distinguishes_absent_unresolved_and_zero(reducer):
    known = r.Flow.from_events([DAY], [2], units="m")
    unknown = r.Flow.from_events([DAY], [None], units="m")
    empty = r.Flow(units="m", movements=())
    skipped = aggregate([known, unknown], reducer=reducer, missing="skip")
    assert skipped.flow.movements[0].number == 2
    assert skipped.coverage == (0.5,)
    assert (
        aggregate([unknown, unknown], reducer=reducer, missing="skip")
        .flow.movements[0]
        .magnitude
        is None
    )
    assert (
        aggregate([known, unknown], reducer=reducer, missing="zero")
        .flow.movements[0]
        .magnitude
        is None
    )
    filled = aggregate([known, empty], reducer=reducer, missing="zero", join="union")
    assert filled.flow.movements[0].number == (0 if reducer == "min" else 2)
    assert filled.coverage == (0.5,)
    # Alignment must not add explicit null Claims to a present movement.
    assert not align([known, known]).flows[0].movements[0].has_field("claims")


def test_model_builds_one_index_and_reuses_it_for_validation(monkeypatch):
    build = Index.build
    calls = []

    def counted(record):
        calls.append(record)
        return build(record)

    monkeypatch.setattr(Index, "build", counted)
    model = Model.create(metadata=r.Metadata(id=uuid4(), schema_version="0.5.0"))
    assert len(calls) == 1
    validate(model).raise_if_invalid()
    assert len(calls) == 1
    Model.from_data(model.to_data())
    assert len(calls) == 2


def test_generated_classes_properties_and_replacement_have_documentation():
    for cls in r._TYPES.values():
        assert cls.__doc__
        assert cls.replace.__doc__
        assert set(inspect.signature(cls).parameters) == set(
            inspect.signature(cls.replace).parameters
        ) - {"self"}
        for name in inspect.signature(cls).parameters:
            assert getattr(cls, name).__doc__


def test_zero_filling_uses_target_units_for_offset_conversions():
    first = r.Flow.from_events([DAY], [1], units="kelvin")
    second = r.Flow.from_events([date(2026, 1, 2)], [0], units="degC")
    result = aggregate([first, second], join="union", missing="zero")
    assert [m.number for m in result.flow.movements] == [1.0, 273.15]
    assert result.coverage == (0.5, 0.5)
    assert align([first, second], join="union", missing="zero").reduce() == result
