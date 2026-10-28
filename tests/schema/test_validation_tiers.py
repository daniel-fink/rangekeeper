"""jsonschema validates untrusted input only; typed construction uses node checks."""

from datetime import date
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.flow import Flow, Movement
from rangekeeper.io import DirectoryStore
from rangekeeper.io import json as codec
from rangekeeper.model import Entity, Metadata, System
from rangekeeper.schema import validation
from rangekeeper.shared.errors import ValidationError


@pytest.fixture
def counted(monkeypatch):
    """Count the jsonschema validations, by kind."""
    calls: list[str] = []
    original = validation._validate_json

    def counting(kind, data):
        calls.append(kind)
        return original(kind, data)

    monkeypatch.setattr(validation, "_validate_json", counting)
    return calls


def test_typed_construction_does_not_run_jsonschema(counted):
    periods = rk.duration.make_periods(
        date(2026, 1, 1), frequency=rk.duration.Frequency.MONTH, count=12
    )
    flow = Flow.from_periods(periods, [1.0] * 12, units="AUD")
    Movement(id=uuid4(), key="a", date=date(2026, 1, 1))
    flow.replace(units="USD")
    assert counted == []


def test_typed_construction_still_rejects_invalid_fields(counted):
    with pytest.raises(ValidationError) as error:
        Entity(id=uuid4(), code="  ")
    assert error.value.report.issues[0].path == "/code"
    assert counted == []


def test_untrusted_input_runs_jsonschema(counted, tmp_path):
    model = rk.Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        system=System(entities=(Entity(id=uuid4(), code="A"),)),
    )
    assert counted == []
    text = codec.dumps(model)
    counted.clear()
    codec.loads(text, kind=rk.Model)
    assert counted[:1] == ["Model"]
    counted.clear()
    rk.Model.from_data(model.to_data())
    assert counted[:1] == ["Model"]
    store = DirectoryStore(tmp_path / "records")
    store.put(model)
    counted.clear()
    # A file is untrusted input; a MemoryStore keeps validated documents.
    store.load_model(model.id)
    assert "Model" in counted
