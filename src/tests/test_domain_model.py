"""Canonical Model behavior, atomic revisions, and schema-owned lookup scopes."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml

from rangekeeper.model import (
    Model,
    Metadata,
    Definitions,
    System,
    Entity,
    Assembly,
    Relationship,
    Characteristics,
    Value,
    Measure,
    Quantity,
    Formulation,
    Update,
)
from rangekeeper.model import characteristics, definitions, provenance
from rangekeeper.model.diff import between
from rangekeeper.model.validation import validate
from rangekeeper.errors import (
    MissingReferenceError,
    ReferenceTypeError,
    IdentityConflictError,
    RevisionConflictError,
    UnsupportedVersionError,
    ValidationError,
    UnitError,
)
from rangekeeper.units import UnitSystem, default_units

EXAMPLES = Path(__file__).resolve().parents[2] / "schema/examples"


def load(name="model"):
    return yaml.safe_load((EXAMPLES / (name + ".yaml")).read_text())


def simple():
    measure = Measure(id=uuid4(), code="area", name="Area", units="squaremeter")
    first = Value(
        id=uuid4(),
        key="gross",
        kind="measurement",
        measure=measure.id,
        quantity=Quantity(magnitude=0, units="squaremeter"),
    )
    second = Value(id=uuid4(), key="net", kind="measurement", measure=measure.id)
    entity = Entity(
        id=uuid4(), code="A", characteristics=Characteristics(values=(first, second))
    )
    local = Value(id=uuid4(), key="gross", kind="measurement", measure=measure.id)
    child = Formulation(id=uuid4(), code="area", values=(local,))
    formulation = Formulation(id=uuid4(), formulations=(child,))
    assembly = Assembly(id=uuid4(), code="group", entities=(entity.id,))
    return Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.4.0"),
        definitions=Definitions(measures=(measure,)),
        system=System(
            entities=(entity,), assemblies=(assembly,), formulations=(formulation,)
        ),
    )


@pytest.mark.parametrize(
    "name", ["model", "model-forward-output", "model-inverse-output"]
)
def test_fixture_factories_detach_and_preserve(name):
    data = load(name)
    model = Model.from_data(data)
    assert model.to_data() == data
    assert validate(model).valid
    data["metadata"]["name"] = "changed"
    exported = model.to_data()
    exported["metadata"]["name"] = "exported"
    assert model.metadata.name not in ("changed", "exported")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        model.metadata = None
    with pytest.raises(AttributeError):
        model.metadata.name = "changed"


def test_owner_local_values_share_a_measure_without_collapsing():
    model = simple()
    entity = model.find_entities(code="A")[0]
    gross = characteristics.value(entity.characteristics, "gross")
    net = characteristics.value(entity.characteristics, "net")
    assert gross.measure == net.measure
    assert gross.quantity.magnitude == 0 and net.quantity is None
    assert model.value(gross.id) == gross and model.owner_of(gross.id) == entity.id
    assert characteristics.value(entity.characteristics, "Gross") is None
    assert characteristics.value(None, "gross") is None
    child = model.system.formulations[0].formulations[0]
    assert model.formulation(child.id) == child
    assert model.owner_of(child.id) == model.system.formulations[0].id
    assert model.owner_of(child.values[0].id) == child.id
    assert model.value(child.values[0].id).key == gross.key


def test_canonical_assembly_search_and_lookup_errors():
    model = simple()
    assembly = model.system.assemblies[0]
    assert isinstance(model.entity(assembly.id), Assembly)
    assert assembly.id not in {entity.id for entity in model.system.entities}
    assert tuple(e.id for e in model.find_entities()) == (
        model.system.entities[0].id,
        assembly.id,
    )
    assert model.find_entities(code="missing") == ()
    assert model.find_entities(code="A", name="not A") == ()
    assert model.owner_of(assembly.id) is None
    with pytest.raises(TypeError):
        model.entity(str(assembly.id))
    with pytest.raises(MissingReferenceError):
        model.entity(uuid4())
    with pytest.raises(ReferenceTypeError):
        model.value(assembly.id)
    with pytest.raises(ReferenceTypeError):
        model.relationship(assembly.id)
    with pytest.raises(MissingReferenceError):
        model.owner_of(uuid4())


def test_definition_identity_is_separate_from_code_lookup():
    model = simple()
    measure = model.definitions.measures[0]
    assert definitions.measure(model.definitions, measure.id) == measure
    assert definitions.find_measures(model.definitions, code="area") == (measure,)
    assert definitions.find_measures(model.definitions, code="AREA") == ()
    with pytest.raises(TypeError):
        definitions.measure(model.definitions, measure.code)
    with pytest.raises(MissingReferenceError):
        definitions.measure(None, measure.id)
    with pytest.raises(ReferenceTypeError):
        definitions.taxonomy(model.definitions, measure.id)


def test_revisions_preserve_old_lookup_and_provenance_atomically():
    before = Model.from_data(load())
    system = before.system.to_data()
    identity = UUID(system["entities"][0]["id"])
    old_name = before.entity(identity).name
    system["entities"][0]["name"] = "new revision"
    after = before.revise(Update(system=System.from_data(system)))
    assert after.id != before.id and after.metadata.previous == before.id
    assert after.entity(identity).name == "new revision"
    assert before.entity(identity).name == old_name
    assert after.provenance.to_data() == before.provenance.to_data()
    assert after.definitions.to_data() == before.definitions.to_data()
    assert identity in between(before, after).modified
    original = before.to_data()
    with pytest.raises(ValidationError):
        before.revise(Update(definitions=Definitions()))
    assert before.to_data() == original


def test_revision_noop_lineage_version_and_empty_sections():
    before = simple()
    with pytest.raises(RevisionConflictError):
        before.revise(Update())
    with pytest.raises(RevisionConflictError):
        before.revise(Update(metadata=Metadata(id=uuid4(), schema_version="0.4.0")))
    with pytest.raises(UnsupportedVersionError):
        before.revise(
            Update(
                metadata=Metadata(id=uuid4(), schema_version="9.0", previous=before.id)
            )
        )
    after = before.revise(Update(system=System()))
    assert after.system.to_data() == {} and before.find_entities()
    with pytest.raises(MissingReferenceError):
        after.entity(before.find_entities()[0].id)
    minimal = Model.create(metadata=Metadata(id=uuid4(), schema_version="0.4.0"))
    # Explicit empty and omitted sections remain distinct revision content.
    assert minimal.revise(Update(system=System())).to_data()["system"] == {}
    with pytest.raises(TypeError):
        Update(system=None)


def test_explicit_metadata_and_descriptive_revision():
    model = simple()
    metadata = Metadata(
        id=uuid4(), schema_version="0.4.0", previous=model.id, name="named"
    )
    revised = model.revise(Update(metadata=metadata))
    assert revised.metadata == metadata
    assert not between(model, revised).modified
    with pytest.raises(RevisionConflictError):
        revised.revise(
            Update(
                metadata=Metadata(
                    id=model.id,
                    previous=revised.id,
                    schema_version="0.4.0",
                    name="reuse",
                )
            )
        )


def test_duplicate_ownership_and_opaque_identity():
    model = simple()
    data = model.to_data()
    data["system"]["entities"].append(data["system"]["entities"][0])
    with pytest.raises(IdentityConflictError):
        Model.from_data(data)
    data = load()
    opaque = data["provenance"]["claims"][0]["content"]
    opaque["id"] = str(uuid4())
    restored = Model.from_data(data)
    with pytest.raises(MissingReferenceError):
        restored.owner_of(UUID(opaque["id"]))


def test_provenance_traversal_is_scoped_and_does_not_read_files():
    model = Model.from_data(load())
    fact = model.provenance.facts[0]
    assert provenance.fact_for(model, fact.target) == fact
    assert provenance.locations(model, fact.claims[0])
    assert provenance.fact_for(model, model.id) is None
    with pytest.raises(MissingReferenceError):
        provenance.locations(model, uuid4())
    with pytest.raises(ReferenceTypeError):
        provenance.locations(model, model.id)


def test_diff_preserves_presence_and_opaque_types_and_order():
    data = load()
    before = Model.from_data(data)
    data["provenance"]["claims"][0]["content"] = {"items": [False, 0]}
    first = Model.from_data(data)
    data["provenance"]["claims"][0]["content"] = {"items": [0, False]}
    second = Model.from_data(data)
    assert between(first, second).modified
    assert any(
        "content/items" in change.path for change in between(first, second).changes
    )
    data = before.to_data()
    data["system"]["entities"].reverse()
    assert not between(before, Model.from_data(data)).changes
    model = simple()
    data = model.to_data()
    data["system"]["entities"][0]["name"] = None
    change = next(
        change
        for change in between(model, Model.from_data(data)).changes
        if change.path.endswith("/name")
    )
    assert change.before is not None and change.after is None


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("m", "foot", True),
        ("squaremeter", "squarefoot", True),
        ("AUD", "USD", False),
        ("dwelling", "dimensionless", False),
        ("AUD/year", "AUD/dwelling/year", False),
    ],
)
def test_unit_dimensions(left, right, expected):
    assert default_units.compatible(left, right) is expected


def test_unit_conversion_and_configuration_are_immutable():
    original = Quantity(magnitude=1, units="foot")
    assert default_units.convert(original, to="m").magnitude == pytest.approx(0.3048)
    assert original.magnitude == 1 and original.units == "foot"
    with pytest.raises(UnitError):
        default_units.convert(Quantity(magnitude=1, units="AUD"), to="USD")
    with pytest.raises(UnitError):
        default_units.compatible("unknown_unit_rk", "m")
    with pytest.raises(UnitError):
        UnitSystem(currencies=("FAKE",))
    with pytest.raises(FrozenInstanceError):
        default_units.currencies = ()
    with pytest.raises(UnitError):
        UnitSystem(currencies=("AUD",)).compatible("USD", "USD")


def test_model_validates_recorded_units_but_not_opaque_content():
    model = simple()
    data = model.to_data()
    data["system"]["entities"][0]["characteristics"]["values"][0]["quantity"][
        "units"
    ] = "AUD"
    with pytest.raises(ValidationError) as error:
        Model.from_data(data)
    assert error.value.report.issues[0].code == "semantic.units"
    assert "/values/0" in error.value.report.issues[0].path
    data = model.to_data()
    data["metadata"]["schema_version"] = "9.0"
    with pytest.raises(UnsupportedVersionError):
        Model.from_data(data)


def test_ordered_mathematics_is_not_sorted_for_revision_comparison():
    from rangekeeper.model import Expression

    left = Expression(
        id=uuid4(), kind="quantity", quantity=Quantity(magnitude=1, units="m")
    )
    right = Expression(
        id=uuid4(), kind="quantity", quantity=Quantity(magnitude=2, units="m")
    )
    expression = Expression(
        id=uuid4(), kind="binary", operator="subtract", operands=(left, right)
    )
    formulation = Formulation(id=uuid4(), expressions=(expression,))
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.4.0"),
        system=System(formulations=(formulation,)),
    )
    data = model.system.to_data()
    data["formulations"][0]["expressions"][0]["operands"].reverse()
    revised = model.revise(Update(system=System.from_data(data)))
    assert expression.id in between(model, revised).modified
    assert model.formulation(formulation.id).expressions[0].operands[0].id == left.id
