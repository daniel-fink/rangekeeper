"""replace checks only the changed record, OMIT removes a field, repr is short."""

from datetime import date
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.flow import Flow, Movement
from rangekeeper.model import Entity
from rangekeeper.schema import validation
from rangekeeper.shared.errors import ValidationError


@pytest.fixture
def flow():
    periods = rk.duration.Periods(
        start=date(2026, 1, 1), frequency=rk.duration.Frequency.MONTH, count=120
    )
    return Flow.from_periods(
        periods=periods, magnitudes=[float(i) for i in range(120)], units="AUD"
    )


def test_replace_does_not_run_jsonschema(flow, monkeypatch):
    def forbidden(kind):
        raise AssertionError(f"jsonschema validated a {kind}")

    validation._validator.cache_clear()
    monkeypatch.setattr(validation, "_validator", forbidden)
    replaced = flow.replace(units="USD")
    assert replaced.units == "USD" and replaced.movements == flow.movements
    assert replaced.movements[0]._data is flow.movements[0]._data
    movement = flow.movements[0].replace(magnitude=rk.OMIT, key="first")
    assert not movement.has_field("magnitude") and movement.key == "first"


def test_replace_checks_the_changed_fields_and_rules(flow):
    with pytest.raises(ValidationError) as error:
        flow.movements[0].replace(key="   ")
    assert [issue.path for issue in error.value.report.issues] == ["/key"]
    entity = Entity(id=uuid4(), code="A")
    with pytest.raises(ValidationError):
        entity.replace(code="")
    # A Value of kind flow requires a measure (a class rule).
    value = rk.model.Value(
        id=uuid4(), key="v", kind=rk.model.ValueKind.FLOW, measure=uuid4(), flow=flow
    )
    with pytest.raises(ValidationError, match="rule"):
        value.replace(measure=rk.OMIT)


def test_omit_removes_only_optional_fields():
    movement = Movement(id=uuid4(), key="a", date=date(2026, 1, 1), magnitude=1)
    removed = movement.replace(magnitude=rk.OMIT, key=rk.OMIT)
    assert removed.field_names() == ("id", "date")
    assert removed.replace(magnitude=rk.OMIT) == removed
    assert movement.replace(magnitude=None).has_field("magnitude")
    with pytest.raises(TypeError, match="Omit"):
        movement.replace(id=rk.OMIT)  # type: ignore[arg-type]


def test_record_data_in_replace_is_validated_in_full(flow):
    data = flow.movements[0].to_data()
    with pytest.raises(ValidationError):
        flow.replace(movements=({**data, "magnitude": "wrong"},))  # type: ignore[arg-type]


def test_repr_is_one_short_line(flow):
    text = repr(flow)
    assert text == "Flow(units='AUD', movements=[120])"
    assert "\n" not in repr(flow.movements[0]) and len(repr(flow.movements[0])) < 200
