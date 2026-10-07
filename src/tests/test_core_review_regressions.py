"""Independent regressions from the final core refactoring review."""

from uuid import UUID, uuid4

import pytest

from rangekeeper._record_index import RecordIndex
from rangekeeper._schema.validation import document_version
from rangekeeper.errors import ContractError, ReferenceTypeError, ValidationError
from rangekeeper.model import Model, Value
from rangekeeper.model.formulation.validation import validate_formulation_names
from rangekeeper.specification import Specification, SpecificationRecord
from rangekeeper.specification.validation import validate_records


def metadata(kind="Specification", **fields):
    return dict(id=str(uuid4()), schema_version=document_version(kind), **fields)


class Resolver:
    def __init__(self, model, *specifications):
        self.model = model
        self.specifications = {item.id: item for item in specifications}

    def load_model(self, identity):
        assert identity == self.model.id
        return self.model

    def load_specification(self, identity):
        return self.specifications[identity]


def validate_specification(root, model, contributions, *, raw):
    if raw:
        return validate_records(
            root.to_data(),
            models={str(model.id): model.to_data()},
            specifications={str(item.id): item.to_data() for item in contributions},
        )
    resolver = Resolver(model, *contributions)
    return root.compose(resolver=resolver).validate(resolver=resolver)


@pytest.mark.parametrize("raw", [False, True])
def test_included_predecessor_remains_a_valid_contributor(raw):
    model = Model.from_data(dict(metadata=metadata("Model")))
    base = Specification.from_data(dict(metadata=metadata(), model=str(model.id)))
    root = Specification.from_data(
        dict(metadata=metadata(previous=str(base.id)), includes=[str(base.id)])
    )
    result = validate_specification(root, model, (base,), raw=raw)
    assert result.valid, result.issues


@pytest.mark.parametrize("included", [False, True])
def test_batch_revision_cannot_alias_a_leaf_formulation(included):
    model = Model.from_data(dict(metadata=metadata("Model")))
    batch_id = str(uuid4())
    contribution = dict(metadata=metadata(), formulations=[dict(id=batch_id)])
    leaf = dict(metadata=metadata(), model=str(model.id))
    if included:
        leaf["includes"] = [contribution["metadata"]["id"]]
    else:
        leaf["formulations"] = contribution.pop("formulations")
    batch = dict(metadata=dict(metadata(), id=batch_id), cases=[leaf["metadata"]["id"]])
    result = validate_records(
        batch,
        models={str(model.id): model.to_data()},
        specifications={item["metadata"]["id"]: item for item in (leaf, contribution)},
    )
    assert not result.valid
    issue = result.issues[0]
    assert issue.code == "semantic.identity"
    assert issue.path == "/formulations/0/id"


def test_batch_siblings_keep_separate_formulation_identity_scopes():
    model = Model.from_data(dict(metadata=metadata("Model")))
    formulation_id = str(uuid4())
    leaves = [
        dict(
            metadata=metadata(),
            model=str(model.id),
            formulations=[dict(id=formulation_id)],
        )
        for _ in range(2)
    ]
    batch = dict(metadata=metadata(), cases=[item["metadata"]["id"] for item in leaves])
    result = validate_records(
        batch,
        models={str(model.id): model.to_data()},
        specifications={item["metadata"]["id"]: item for item in leaves},
    )
    assert result.valid, result.issues


@pytest.mark.parametrize("raw", [False, True])
def test_local_wrong_reference_kind_is_a_structured_semantic_failure(raw):
    model = Model.from_data(dict(metadata=metadata("Model")))
    identity = str(uuid4())
    data = dict(
        metadata=metadata(),
        model=str(model.id),
        formulations=[dict(id=identity)],
        unknowns=[dict(target=identity)],
    )
    if raw:
        report = validate_records(data, models={str(model.id): model.to_data()})
    else:
        with pytest.raises(ValidationError) as failure:
            Specification.from_data(data)
        report = failure.value.report
    assert not report.valid
    issue = report.issues[0]
    assert issue.code == "reference.kind"
    assert issue.path == "/unknowns/0/target"
    assert issue.document_id == UUID(data["metadata"]["id"])
    assert all(name in issue.message for name in ("Value", "Movement", "Formulation"))


def test_direct_lookup_keeps_its_wrong_kind_exception():
    identity = uuid4()
    record = SpecificationRecord.from_data(
        dict(metadata=metadata(), formulations=[dict(id=str(identity))])
    )
    with pytest.raises(ReferenceTypeError):
        RecordIndex.build(record).get(identity, Value)


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("one_shot", [False, True])
def test_local_naming_checks_each_collection_from_one_shot_iterables(nested, one_shot):
    child = dict(
        id=str(uuid4()),
        bindings=[dict(name="duplicate", value=str(uuid4())) for _ in range(2)],
    )
    children = iter([child]) if one_shot else [child]
    roots = [dict(id=str(uuid4()), formulations=children)] if nested else children
    if one_shot:
        roots = iter(roots)
    with pytest.raises(ContractError) as failure:
        validate_formulation_names(roots)
    parent = "/formulations/0/formulations/0" if nested else "/formulations/0"
    assert failure.value.path == parent + "/bindings/1/name"


@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_binding_failure_retains_the_included_document_and_field(raw, nested):
    model = Model.from_data(dict(metadata=metadata("Model")))
    formulation = dict(
        id=str(uuid4()), bindings=[dict(name="missing", value=str(uuid4()))]
    )
    if nested:
        formulation = dict(id=str(uuid4()), formulations=[formulation])
    child = Specification.from_data(
        dict(metadata=metadata(), formulations=[formulation])
    )
    root = Specification.from_data(
        dict(metadata=metadata(), model=str(model.id), includes=[str(child.id)])
    )
    report = validate_specification(root, model, (child,), raw=raw)
    assert not report.valid
    issue = report.issues[0]
    assert issue.document_id == child.id
    parent = "/formulations/0/formulations/0" if nested else "/formulations/0"
    assert issue.path == parent + "/bindings/0/value"


def test_model_binding_failure_retains_its_system_field_path():
    data = dict(
        metadata=metadata("Model"),
        system=dict(
            formulations=[
                dict(
                    id=str(uuid4()), bindings=[dict(name="missing", value=str(uuid4()))]
                )
            ]
        ),
    )
    with pytest.raises(ValidationError) as failure:
        Model.from_data(data)
    issue = failure.value.report.issues[0]
    assert issue.document_id == UUID(data["metadata"]["id"])
    assert issue.path == "/system/formulations/0/bindings/0/value"


@pytest.mark.parametrize("failure_kind", ["binding", "units"])
def test_source_translation_uses_original_positions_once(failure_kind):
    model = Model.from_data(dict(metadata=metadata("Model")))
    declaration = dict(id=str(uuid4()))
    if failure_kind == "binding":
        declaration["bindings"] = [dict(name="missing", value=str(uuid4()))]
        tail = "/bindings/0/value"
    else:
        declaration["expressions"] = [
            dict(
                id=str(uuid4()),
                kind="quantity",
                quantity=dict(magnitude=1, units="undefined_review_unit"),
            )
        ]
        tail = "/expressions/0/quantity/units"
    child = Specification.from_data(
        dict(
            metadata=dict(metadata(), id=str(UUID(int=2))),
            formulations=[dict(id=str(uuid4())), declaration],
        )
    )
    root = Specification.from_data(
        dict(
            metadata=dict(metadata(), id=str(UUID(int=1))),
            model=str(model.id),
            includes=[str(child.id)],
            formulations=[dict(id=str(uuid4()))],
        )
    )
    report = validate_specification(root, model, (child,), raw=False)
    assert not report.valid
    assert report.issues[0].document_id == child.id
    assert report.issues[0].path == "/formulations/1" + tail


def test_raw_local_reference_failure_retains_its_contributor():
    model = Model.from_data(dict(metadata=metadata("Model")))
    identity = str(uuid4())
    child = dict(
        metadata=metadata(),
        formulations=[dict(id=identity)],
        unknowns=[dict(target=identity)],
    )
    root = dict(
        metadata=metadata(),
        model=str(model.id),
        includes=[child["metadata"]["id"]],
    )
    report = validate_records(
        root,
        models={str(model.id): model.to_data()},
        specifications={child["metadata"]["id"]: child},
    )
    assert not report.valid
    assert report.issues[0].code == "reference.kind"
    assert report.issues[0].document_id == UUID(child["metadata"]["id"])
    assert report.issues[0].path == "/unknowns/0/target"
