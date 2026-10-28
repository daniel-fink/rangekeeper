"""Every document has the same validate() and check() verbs (ADR-011)."""

import inspect
from copy import deepcopy
from pathlib import Path
from typing import Self
from uuid import UUID, uuid4

import pytest
import yaml

import rangekeeper as rk
from rangekeeper.errors import Code, ValidationError
from rangekeeper.io import MemoryStore
from rangekeeper.quantity import UnitSystem
from rangekeeper.run import Run

EXAMPLES = Path(__file__).resolve().parents[2] / "examples/schema"
DOCUMENTS = (rk.Model, rk.Specification, Run)


def load(name):
    return yaml.safe_load((EXAMPLES / f"{name}.yaml").read_text())


def store():
    found = MemoryStore()
    for pattern, kind in (
        ("model*.yaml", rk.Model),
        ("specification*.yaml", rk.Specification),
    ):
        for path in sorted(EXAMPLES.glob(pattern)):
            found.put(kind.from_data(yaml.safe_load(path.read_text())))
    return found


def revision(name, **metadata):
    data = load(name)
    data["metadata"].update(previous=data["metadata"]["id"], id=str(uuid4()))
    data["metadata"].update(metadata)
    return data


@pytest.mark.parametrize("kind", DOCUMENTS, ids=lambda kind: kind.__name__)
def test_every_document_has_the_same_verbs(kind):
    for name in ("validate", "check"):
        parameters = inspect.signature(getattr(kind, name)).parameters
        assert list(parameters) == ["self", "resolver", "units"]
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            and parameter.default is None
            for name, parameter in parameters.items()
            if name != "self"
        )
    assert inspect.signature(kind.check).return_annotation in (Self, "Self")


@pytest.mark.parametrize(
    "document",
    [
        lambda: rk.Model.from_data(load("model")),
        lambda: rk.Specification.from_data(load("specification-forward")),
        lambda: Run.from_data(load("run-forward")),
    ],
    ids=["Model", "Specification", "Run"],
)
def test_constructed_documents_are_valid_with_and_without_resolver(document):
    document, resolver = document(), store()
    assert document.validate().valid
    assert document.check() is document
    assert document.validate(resolver=resolver).valid
    assert document.check(resolver=resolver) is document


def test_model_units_check_recorded_values_against_another_unit_system():
    model = rk.Model.from_data(load("model"))
    assert model.validate(units=model.unit_system).valid
    assert model.validate(resolver=MemoryStore()).valid
    report = model.validate(units=UnitSystem(currencies=("USD",)))
    assert report.issues and {issue.code for issue in report.issues} == {Code.UNITS}
    with pytest.raises(ValidationError):
        model.check(units=UnitSystem(currencies=("USD",)))


def test_specification_resolver_composes_and_checks_each_case():
    resolver = store()
    batch = rk.Specification.from_data(load("specification-batch"))
    assert batch.check(resolver=resolver) is batch

    partial = rk.Specification.from_data(
        {"metadata": revision("specification-forward")["metadata"]}
    )
    assert partial.validate().valid
    assert [i.code for i in partial.validate(resolver=resolver).issues] == [
        Code.MODEL_MISSING
    ]

    data = revision("specification-forward")
    data["includes"] = [str(UUID(int=9))]
    unresolved = rk.Specification.from_data(data)
    (issue,) = unresolved.validate(resolver=resolver).issues
    assert issue.code is Code.REFERENCE_MISSING


def test_batch_pin_must_match_each_case_model():
    resolver = store()
    other = deepcopy(load("model"))
    other["metadata"].update(id=str(uuid4()), previous=None)
    other["metadata"] = {k: v for k, v in other["metadata"].items() if v is not None}
    resolver.put(rk.Model.from_data(other))
    data = revision("specification-batch", model=None)
    data["metadata"].pop("model", None)
    data["model"] = other["metadata"]["id"]
    batch = rk.Specification.from_data(data)
    issues = batch.validate(resolver=resolver).issues
    assert issues and {issue.code for issue in issues} == {Code.BATCH_MODEL}
    assert all(issue.values["pinned"] == data["model"] for issue in issues)


def test_run_resolver_checks_the_tree():
    data = load("run-forward")
    data["outputs"] = [str(uuid4())]
    data["report"]["trace"] = []
    data["report"]["diagnostics"] = []
    run = Run.from_data(data)
    assert run.validate().valid
    with pytest.raises(ValidationError) as raised:
        run.check(resolver=store())
    assert raised.value.code is Code.REFERENCE_MISSING
