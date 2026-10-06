"""Canonical workflow quantities preserve unresolved values and known zero."""

from rangekeeper.workflow._operands import model_operand, operand


def test_workflow_operands_preserve_unresolved_and_zero():
    from uuid import uuid4
    from rangekeeper.model import (
        Model,
        Metadata,
        System,
        Definitions,
        Measure,
        Value,
        Entity,
        Characteristics,
    )

    measure = Measure(id=uuid4(), code="area", name="Area", units="meter**2")
    reading = Value(id=uuid4(), key="net", kind="measurement", measure=measure.id)
    entity = Entity(
        id=uuid4(), code="A", characteristics=Characteristics(values=(reading,))
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
        definitions=Definitions(measures=(measure,)),
        system=System(entities=(entity,)),
    )
    by_key = {("space", "A"): entity}
    single = {
        "kind": "model_value",
        "identity_kind": "space",
        "key": {"value": "A"},
        "value_key": "net",
        "units": "meter**2",
    }
    result = operand(single, None, None, model, by_key, {})
    assert result.value is None and result.targets == (str(reading.id),)
    total = model_operand(
        {"kind": "model_total", "value_key": "net", "units": "meter**2"},
        None,
        None,
        model,
        by_key,
        {},
    )
    assert (
        total.value is None and total.known_subtotal is None and total.missing == ("A",)
    )
    match_zero = {"kind": "model_count", "value_key": "net", "binding": {"value": 0}}
    assert model_operand(match_zero, None, None, model, by_key, {}).value == 0
    data = model.to_data()
    data["metadata"]["id"] = str(uuid4())
    data["system"]["entities"][0]["characteristics"]["values"][0]["quantity"] = {
        "magnitude": 0,
        "units": "meter**2",
    }
    output = Model.from_data(data)
    assert model_operand(match_zero, None, None, output, {}, {}).value == 1
    assert (
        operand(
            single, None, None, output, {("space", "A"): output.entity(entity.id)}, {}
        ).value
        == 0
    )

    # A retained business-key index must not read quantities from an older revision.
    assert operand(single, None, None, output, by_key, {}).value == 0
