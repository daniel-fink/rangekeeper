"""UUID identity survives revisions; alignment and report scope stay explicit."""

from rangekeeper.model import ValueKind

from copy import deepcopy
from datetime import date
from uuid import UUID, uuid4

import pytest

from rangekeeper.calculations import series
from rangekeeper.shared.errors import (
    IdentityConflictError,
    MissingReferenceError,
    ValidationError,
)
from rangekeeper.model.scope import target_value, target_units
from rangekeeper.io import MemoryStore
from rangekeeper.migration import upgrade_model, upgrade_specification
from rangekeeper.model import (
    Characteristics,
    Definitions,
    Entity,
    Measure,
    Metadata,
    Model,
    Reference,
    System,
    Update,
    Value,
)
from rangekeeper.model.flow import Flow, Movement, MissingValueHandling
from rangekeeper.run import Run, validate as validate_run
from rangekeeper.specification import Specification
from tests.test_domain_run import inputs, load


def example(flow=None):
    measure = Measure(id=uuid4(), code="money", name="Money", units="AUD")
    value = Value(
        id=uuid4(),
        key="cash",
        kind=ValueKind.FLOW,
        measure=measure.id,
        flow=flow or Flow.from_events([date(2027, 1, 1)], [30_000], units="AUD"),
    )
    owner = Entity(id=uuid4(), characteristics=Characteristics(values=(value,)))
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        definitions=Definitions(measures=(measure,)),
        system=System(entities=(owner,)),
    )
    return model, value


def test_reference_resolves_value_or_movement_with_units_from_owner():
    model, value = example()
    movement = value.flow.movements[0]
    ref = Reference(target=movement.id)
    assert ref.to_data() == {"target": str(movement.id)}
    assert model.resolve(Reference(target=value.id)) == value
    assert model.resolve(ref) == model.movement(movement.id) == movement
    assert model.owner_of(movement.id) == value.id
    assert target_value(model, ref) == value
    assert target_units(model, ref) == "AUD"
    with pytest.raises(TypeError):
        model.resolve(Reference(target=model.system.entities[0].id))
    with pytest.raises(MissingReferenceError):
        model.resolve(Reference(target=uuid4()))


def test_revision_changes_amount_coordinate_and_key_without_rewriting_reference():
    model, value = example()
    before = value.flow.movements[0]
    ref = Reference(target=before.id)
    changed = before.replace(magnitude=35_000, date=date(2027, 2, 1), key="revised")
    owner = model.system.entities[0]
    after = model.revise(
        Update(
            system=model.system.replace(
                entities=(
                    owner.replace(
                        characteristics=owner.characteristics.replace(
                            values=(
                                value.replace(
                                    flow=value.flow.replace(movements=(changed,))
                                ),
                            )
                        )
                    ),
                )
            )
        )
    )
    assert after.id != model.id and after.metadata.previous == model.id
    assert model.resolve(ref).number == 30_000
    assert after.resolve(ref).number == 35_000
    assert after.resolve(ref).id == before.id
    assert model.resolve(ref).date == date(2027, 1, 1)


def test_global_identity_requires_an_independent_copy_for_another_value():
    model, value = example()
    owner = model.system.entities[0]

    def append(flow):
        other = value.replace(id=uuid4(), key="other", flow=flow)
        return model.revise(
            Update(
                system=model.system.replace(
                    entities=(
                        owner.replace(
                            characteristics=owner.characteristics.replace(
                                values=(value, other)
                            )
                        ),
                    )
                )
            )
        )

    with pytest.raises(IdentityConflictError):
        append(value.flow)
    copied = value.flow.clone()
    assert copied.movements[0].id != value.flow.movements[0].id
    assert copied.movements[0].number == value.flow.movements[0].number
    append(copied)
    append(value.flow.scale(2))


def test_constructor_ids_are_explicit_but_decoders_never_invent_them():
    identity = uuid4()
    flow = Flow.from_events([date(2027, 1, 1)], [0], units="AUD", ids=[identity])
    assert flow.movements[0].id == identity
    assert not flow.movements[0].has_field("key")
    assert Flow.from_data(flow.to_data()) == flow
    data = flow.to_data()
    data["movements"][0].pop("id")
    with pytest.raises(ValidationError):
        Flow.from_data(data)


def test_coordinate_index_preserves_unresolved_records_and_rejects_duplicates():
    day = date(2027, 1, 1)
    movements = tuple(Movement(id=uuid4(), date=day, key=key) for key in ("z", "a"))
    flow = Flow(units="AUD", movements=movements)
    before = flow.to_data()
    index = flow.coordinate_index()
    assert tuple(index) == tuple(movement.coordinate for movement in movements)
    assert tuple(index.values()) == movements
    index.clear()
    assert flow.to_data() == before
    duplicate = movements[0].replace(id=uuid4())
    with pytest.raises(ValueError, match="duplicate coordinates"):
        Flow(units="AUD", movements=(*movements, duplicate)).coordinate_index()


def test_alignment_uses_coordinates_while_results_have_independent_ids():
    day = date(2027, 1, 1)
    left = Flow.from_events([day, day], [1, 2], units="AUD", keys=["a", "b"])
    right = Flow.from_events([day, day], [3, 4], units="AUD", keys=["a", "b"])
    original_ids = {m.id for f in (left, right) for m in f.movements}
    aligned = series.align([left, right])
    assert [f.to_data() for f in aligned.flows] == [left.to_data(), right.to_data()]
    result = aligned.reduce().flow
    assert [m.number for m in result.movements] == [4, 6]
    assert not original_ids.intersection(m.id for m in result.movements)
    assert [m.id for m in left.convert(units="AUD").movements] == [
        m.id for m in left.movements
    ]
    for keys in (None, ["a", "a"], ["a", None]):
        with pytest.raises(ValueError, match="repeated event"):
            Flow.from_events([day, day], [1, 2], units="AUD", keys=keys)
    later = Flow.from_events([date(2027, 2, 1)], [3], units="AUD")
    union = series.align(
        [left, later],
        join=series.AlignmentJoin.UNION,
        missing=MissingValueHandling.ZERO,
    )
    assert union.flows[0].movements[-1].id != later.movements[0].id
    assert union.flows[0].movements[0].id == left.movements[0].id


def test_old_owner_key_migrates_consistently_without_changing_source():
    model, value = example(
        Flow.from_events([date(2027, 1, 1)], [30_000], units="AUD", keys=["rent"])
    )
    old = model.to_data()
    old["metadata"]["schema_version"] = "0.5.0"
    old["system"]["entities"][0]["characteristics"]["values"][0]["flow"]["movements"][
        0
    ].pop("id")
    old["provenance"] = {
        "claims": [
            {
                "id": str(uuid4()),
                "kind": "asserted",
                "method": {"code": "manual"},
                "content": {"value": str(value.id), "movement": "rent"},
            }
        ]
    }
    original = deepcopy(old)
    spec = {
        "metadata": {"id": str(uuid4()), "schema_version": "0.5.0"},
        "model": str(model.id),
        "unknowns": [{"value": str(value.id), "movement": "rent"}],
    }
    upgraded = upgrade_model(old)
    again = upgrade_model(old)
    question = upgrade_specification(spec, model=upgraded.id)
    target = upgraded.value(value.id).flow.movements[0].id
    assert (
        target
        == again.value(value.id).flow.movements[0].id
        == question.record.unknowns[0].target
    )
    assert old == original
    assert (
        upgraded.provenance.claims[0].to_data()["content"]
        == original["provenance"]["claims"][0]["content"]
    )
    store = MemoryStore()
    store.put(upgraded)
    question.compose(resolver=store).validate(resolver=store).raise_if_invalid()


def test_diagnostic_participants_use_input_model_even_for_a_specification_subject():
    store = inputs()
    data = load("run-failed")
    spec = store.load_specification(UUID(data["specification"]))
    model = store.load_model(spec.compose(resolver=store).model_id)
    value = model.system.entities[0].characteristics.values[0]
    diagnostic = data["report"]["diagnostics"][0]
    diagnostic.update(
        document=str(spec.id),
        target=str(spec.id),
        references=[{"target": str(value.id)}],
    )
    assert validate_run(Run.from_data(data), resolver=store).valid
    unrelated, extra = example()
    store.put(unrelated)
    diagnostic["references"] = [{"target": str(extra.flow.movements[0].id)}]
    assert not validate_run(Run.from_data(data), resolver=store).valid


@pytest.mark.parametrize("kind", ["batch", "missing_input"])
def test_diagnostic_participants_require_one_valid_input_scope(kind):
    store = inputs()
    for name in ("forward", "inverse"):
        store.put(Run.from_data(load("run-" + name)))
    data = load("run-batch" if kind == "batch" else "run-failed")
    if kind == "missing_input":
        spec = Specification.from_data(
            {"metadata": {"id": str(uuid4()), "schema_version": "0.7.0"}}
        )
        store.put(spec)
        data["specification"] = str(spec.id)
    data["report"]["diagnostics"] = [
        {
            "severity": "error",
            "code": "specification_invalid",
            "message": "Scope test",
        }
    ]
    assert validate_run(Run.from_data(data), resolver=store).valid
    data["report"]["diagnostics"][0]["references"] = [{"target": str(uuid4())}]
    report = validate_run(Run.from_data(data), resolver=store)
    assert not report.valid
    assert any("valid input Model" in issue.message for issue in report.issues)


def test_constraint_subject_and_participant_scope_are_separate():
    model, value = example()
    store = MemoryStore()
    store.put(model)
    expression, constraint, local = uuid4(), uuid4(), uuid4()
    spec = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "0.7.0"},
            "model": str(model.id),
            "formulations": [
                {
                    "id": str(uuid4()),
                    "values": [
                        {
                            "id": str(local),
                            "key": "local",
                            "kind": "measurement",
                            "measure": str(value.measure),
                        }
                    ],
                    "expressions": [
                        {"id": str(expression), "kind": "boolean", "boolean": True}
                    ],
                    "constraints": [
                        {"id": str(constraint), "predicate": str(expression)}
                    ],
                }
            ],
        }
    )
    store.put(spec)
    data = load("run-failed")
    data["specification"] = str(spec.id)
    diagnostic = data["report"]["diagnostics"][0]
    diagnostic.update(
        document=str(spec.id),
        target=str(constraint),
        references=[{"target": str(value.flow.movements[0].id)}],
    )
    assert validate_run(Run.from_data(data), resolver=store).valid
    diagnostic["references"] = [{"target": str(local)}]
    assert not validate_run(Run.from_data(data), resolver=store).valid


def test_draft_conversion_preserves_source_address_entries():
    data = {"metadata": {"id": str(uuid4()), "schema_version": "0.5.0"}}
    source = str(uuid4())
    data["provenance"] = {
        "sources": [{"id": source, "name": "Source", "checksum": "abc"}],
        "claims": [
            {
                "id": str(uuid4()),
                "kind": "sourced",
                "content": {"value": "original"},
                "sources": [{"source": source, "address": {"cell": {"value": "A1"}}}],
            }
        ],
    }
    before = deepcopy(data)
    upgraded = upgrade_model(data)
    assert data == before
    assert upgraded.provenance.to_data() == before["provenance"]
