"""Partial authoring, pinned composition, contributor traceability and conflicts."""

from rangekeeper.model.expression import Reference
from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from rangekeeper.model import Model, Metadata, Formulation, Value, Quantity
from rangekeeper.specification import (
    Specification,
    SpecificationRecord,
    compose,
    validate,
)
from rangekeeper.errors import (
    ValidationError,
    MissingReferenceError,
    ReferenceTypeError,
    IdentityConflictError,
    RevisionConflictError,
    UnsupportedVersionError,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "schema/examples"


def load(name):
    return yaml.safe_load((EXAMPLES / (name + ".yaml")).read_text())


class Resolver:
    """Test-only read dependency, intentionally no write/store API."""

    def __init__(self, *documents):
        self.documents = {doc.id: doc for doc in documents}
        self.calls = []

    def _get(self, id, kind):
        self.calls.append(id)
        if id not in self.documents:
            raise MissingReferenceError(str(id))
        result = self.documents[id]
        if not isinstance(result, kind):
            raise ReferenceTypeError(str(id))
        return result

    def load_model(self, id):
        return self._get(id, Model)

    def load_specification(self, id):
        return self._get(id, Specification)


def spec(**fields):
    return Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.6.0"), **fields
        )
    )


@pytest.mark.parametrize(
    "path", sorted(EXAMPLES.glob("specification*.yaml")), ids=lambda path: path.stem
)
def test_partial_and_batch_fixtures_are_locally_valid(path):
    data = yaml.safe_load(path.read_text())
    record = Specification.from_data(data)
    assert record.to_data() == data
    with pytest.raises(FrozenInstanceError):
        record.metadata = None
    with pytest.raises(AttributeError):
        record.record.metadata.name = "changed"


def test_diamond_contributes_once_with_immutable_trace():
    target = uuid4()
    base = spec(unknowns=(Reference(target=target),))
    left, right = spec(includes=(base.id,)), spec(includes=(base.id,))
    root = spec(includes=(left.id, right.id))
    resolver = Resolver(base, left, right)
    composition = compose(root, resolver=resolver)
    assert composition.root_id == root.id and composition.model_id is None
    assert composition.requirements.unknowns == (Reference(target=target),)
    assert composition.sources[("unknowns", str(target))] == base.id
    assert len(composition.contributors) == 4 and resolver.calls.count(base.id) == 1
    assert {doc.id for doc in composition.contributions} == set(
        composition.contributors
    )
    with pytest.raises(TypeError):
        composition.sources[("x",)] = root.id
    with pytest.raises(FrozenInstanceError):
        composition.model_id = uuid4()
    with pytest.raises(AttributeError):
        composition.requirements.unknowns = ()
    assert root.record.unknowns == ()
    assert not validate(composition, resolver=resolver).valid


def test_independent_duplicate_requirement_is_a_conflict():
    target = uuid4()
    left, right = spec(unknowns=(Reference(target=target),)), spec(
        unknowns=(Reference(target=target),)
    )
    root = spec(includes=(left.id, right.id))
    with pytest.raises(ValidationError, match="multiple contributors"):
        compose(root, resolver=Resolver(left, right))


def test_conflicting_model_pins_and_role_overlap():
    left, right = spec(model=uuid4()), spec(model=uuid4())
    with pytest.raises(ValidationError, match="conflicting input Model"):
        compose(spec(includes=(left.id, right.id)), resolver=Resolver(left, right))
    from rangekeeper.specification import Assignment

    target = uuid4()
    with pytest.raises(ValidationError, match="roles overlap"):
        spec(
            assignments=(
                Assignment(
                    target=Reference(target=target),
                    quantity=Quantity(magnitude=0, units="m"),
                ),
            ),
            unknowns=(Reference(target=target),),
        )


def test_missing_wrong_kind_wrong_identity_and_cycles():
    missing = spec(includes=(uuid4(),))
    with pytest.raises(MissingReferenceError):
        compose(missing, resolver=Resolver())
    model = Model.from_data(load("model"))
    with pytest.raises(ReferenceTypeError):
        compose(spec(includes=(model.id,)), resolver=Resolver(model))
    left_id, right_id = uuid4(), uuid4()
    left = Specification(
        SpecificationRecord(
            metadata=Metadata(id=left_id, schema_version="0.6.0"), includes=(right_id,)
        )
    )
    right = Specification(
        SpecificationRecord(
            metadata=Metadata(id=right_id, schema_version="0.6.0"), includes=(left_id,)
        )
    )
    with pytest.raises(ValidationError, match="cycle"):
        compose(left, resolver=Resolver(right))

    class LyingResolver(Resolver):
        def load_specification(self, id):
            return spec()

    with pytest.raises(IdentityConflictError):
        compose(missing, resolver=LyingResolver())


@pytest.mark.parametrize(
    "name", ["specification-composed-forward", "specification-composed-inverse"]
)
def test_complete_composed_investigations_pin_the_model(name):
    model = Model.from_data(load("model"))
    common = Specification.from_data(load("specification-common"))
    root = Specification.from_data(load(name))
    resolver = Resolver(model, common)
    composition = compose(root, resolver=resolver)
    assert composition.model_id == model.id
    assert validate(composition, resolver=resolver).valid
    assert not validate(composition, resolver=Resolver()).valid
    standalone = Specification.from_data(load(name.replace("composed-", "")))
    expected = compose(standalone, resolver=resolver)
    assert {a.target.target for a in composition.requirements.assignments} == {
        a.target.target for a in expected.requirements.assignments
    }
    assert {r.target for r in composition.requirements.unknowns} == {
        r.target for r in expected.requirements.unknowns
    }


def test_partial_roles_do_not_become_complete_from_recorded_values():
    model = Model.from_data(load("model"))
    common = Specification.from_data(load("specification-common"))
    resolver = Resolver(model)
    report = validate(compose(common, resolver=resolver), resolver=resolver)
    assert not report.valid and "missing solve role" in report.issues[0].message


def test_batch_is_not_flattened_or_included_as_one_investigation():
    leaf = spec()
    batch = spec(cases=(leaf.id,))
    with pytest.raises(ValidationError, match="batch"):
        compose(batch, resolver=Resolver(leaf))
    with pytest.raises(ValidationError, match="batch"):
        compose(spec(includes=(batch.id,)), resolver=Resolver(batch, leaf))
    assert batch.record.cases == (leaf.id,)


def test_local_revision_and_unknown_external_references():
    before = spec(includes=(uuid4(),))
    data = before.to_data()
    data["metadata"].update(
        id=str(uuid4()), previous=str(before.id), name="new description"
    )
    after = before.revise(SpecificationRecord.from_data(data))
    assert after.id != before.id and after.record.includes == before.record.includes
    assert before.metadata.name is None
    with pytest.raises(RevisionConflictError):
        after.revise(
            SpecificationRecord(
                metadata=Metadata(
                    id=before.id,
                    previous=after.id,
                    schema_version="0.6.0",
                    name="reuse",
                )
            )
        )
    with pytest.raises(RevisionConflictError):
        before.revise(before.record)
    data["metadata"]["schema_version"] = "9.0"
    with pytest.raises(UnsupportedVersionError):
        before.revise(SpecificationRecord.from_data(data))


def test_duplicate_local_references_and_identity_reuse_are_rejected():
    target = uuid4()
    with pytest.raises(ValidationError, match="duplicate includes"):
        spec(includes=(target, target))
    with pytest.raises(ValidationError, match="duplicate unknown"):
        spec(unknowns=(Reference(target=target), Reference(target=target)))
    metadata = Metadata(id=uuid4(), schema_version="0.6.0")
    with pytest.raises(ValidationError, match="cycle"):
        Specification(SpecificationRecord(metadata=metadata, includes=(metadata.id,)))


def test_specification_local_recorded_quantity_units_are_checked_after_composition():
    model = Model.from_data(load("model"))
    data = load("specification-forward")
    measure = model.definitions.measures[0]
    value = Value(
        id=uuid4(),
        key="local",
        kind="measurement",
        measure=measure.id,
        quantity=Quantity(magnitude=1, units="kelvin"),
    )
    data["formulations"] = [Formulation(id=uuid4(), values=(value,)).to_data()]
    local = Specification.from_data(data)
    resolver = Resolver(model)
    report = validate(compose(local, resolver=resolver), resolver=resolver)
    assert not report.valid
    assert report.issues[0].code == "semantic.units"


def test_model_resolver_must_return_the_requested_revision():
    model = Model.from_data(load("model"))
    root = Specification.from_data(load("specification-forward"))
    composition = compose(root, resolver=Resolver())
    data = model.to_data()
    data["metadata"]["id"] = str(uuid4())
    other = Model.from_data(data)

    class WrongRevision(Resolver):
        def load_model(self, id):
            return other

    assert (
        validate(composition, resolver=WrongRevision()).issues[0].code
        == "reference.identity"
    )


def test_locally_known_role_target_cannot_masquerade_as_value():
    formulation = Formulation(id=uuid4())
    with pytest.raises(ReferenceTypeError, match="wrong local record kind"):
        spec(formulations=(formulation,), unknowns=(Reference(target=formulation.id),))
