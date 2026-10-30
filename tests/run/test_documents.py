"""One lookup and one dependency closure for documents (#423).

``Documents`` holds documents by UUID and reads the others from a fallback;
``dependencies`` lists what a document needs; ``closure`` resolves it once.
"""

from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.io import MemoryStore
from rangekeeper.model import Metadata
from rangekeeper.run import (
    CompletionStatus,
    Diagnostic,
    Report,
    RunRecord,
    RunStatus,
    Severity,
    SolutionStatus,
)
from rangekeeper.run.documents import Documents, closure, dependencies, require_same
from rangekeeper.shared.errors import (
    ContractError,
    IdentityConflictError,
    MissingReferenceError,
    ReferenceTypeError,
    RevisionConflictError,
)
from rangekeeper.shared.references import require_revision
from tests.market.test_paths import histories


def model() -> rk.Model:
    draft = rk.Model(name="Costs").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="land_cost", units="AUD")
    project.value(key="total_cost", units="AUD")
    project.equations("total_cost = land_cost")
    return draft.commit()


def run(specification: rk.Specification, *, document=None) -> rk.Run:
    """Return a synthetic failed Run of a Specification; its report can name a document."""
    return rk.Run(
        RunRecord(
            metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
            specification=specification.id,
            report=Report(
                status=RunStatus(
                    completion=CompletionStatus.FAILED,
                    solution=SolutionStatus.NOT_ASSESSED,
                ),
                diagnostics=(
                    Diagnostic(
                        severity=Severity.ERROR,
                        code="unsupported_capability",
                        message="Synthetic: no backend was invoked.",
                        **({} if document is None else {"document": document}),
                    ),
                ),
            ),
        )
    )


def test_documents_return_their_own_documents_first_then_the_fallback():
    costs = model()
    store = MemoryStore()
    store.put(costs)
    specification = costs.specify(name="Base")
    documents = Documents([specification], fallback=store)
    assert documents.load_specification(specification.id) is specification
    assert documents.load_model(costs.id).id == costs.id
    assert documents.load(costs.id).id == costs.id  # any kind
    assert specification.id in documents and costs.id not in documents
    assert len(documents) == 1
    assert documents.get(costs.id) is None
    assert list(documents) == [specification]


def test_a_lookup_checks_the_kind_and_names_where_it_searched():
    costs = model()
    documents = Documents([costs], where="the test documents")
    with pytest.raises(ReferenceTypeError):
        documents.load_specification(costs.id)
    with pytest.raises(MissingReferenceError) as error:
        documents.load_run(uuid4())
    assert (error.value.kind, error.value.where) == ("Run", "the test documents")
    with pytest.raises(MissingReferenceError):
        documents.load(uuid4())
    with pytest.raises(TypeError):
        documents.load("not a UUID")  # type: ignore[arg-type]


def test_a_fallback_that_reads_no_runs_misses_them():
    costs = model()

    class Models:
        def load_model(self, id):
            return costs

        def load_specification(self, id):
            raise MissingReferenceError(id, kind="Specification")

    documents = Documents(fallback=Models())
    assert documents.load_model(costs.id) is costs
    with pytest.raises(MissingReferenceError):
        documents.load_run(uuid4())


def test_a_fallback_that_returns_another_revision_is_refused():
    costs, other = model(), model()

    class Wrong:
        def load_model(self, id):
            return other

        def load_specification(self, id):
            raise MissingReferenceError(id)

    with pytest.raises(IdentityConflictError):
        Documents(fallback=Wrong()).load_model(costs.id)


def test_two_documents_with_one_uuid_must_be_the_same_revision():
    costs = model()
    Documents([costs, costs])
    Documents([costs, rk.Model.from_data(data=costs.to_data())])
    data = costs.to_data()
    data["metadata"]["name"] = "Other"
    with pytest.raises(RevisionConflictError):
        Documents([costs, rk.Model.from_data(data=data)])
    with pytest.raises(RevisionConflictError):
        require_same(costs, costs.specify())
    with pytest.raises(TypeError):
        Documents(["a document"])  # type: ignore[list-item]


def test_documents_are_listed_in_the_order_of_their_uuid_text():
    first, second = model(), model()
    listed = Documents([second, first]).documents()
    assert [item.id for item in listed] == sorted((first.id, second.id), key=str)


def test_the_dependencies_of_each_kind():
    costs = model()
    specification = costs.specify(name="Base")
    batch = specification.cases(cases={"a": {}, "b": {}})
    assert list(dependencies(costs)) == []
    assert list(dependencies(specification)) == [(costs.id, rk.Model)]
    assert list(dependencies(batch))[1:] == [
        (identity, rk.Specification) for identity in batch.record.cases
    ]
    attempt = run(specification, document=costs.id)
    assert list(dependencies(attempt)) == [
        (specification.id, rk.Specification),
        (costs.id, None),
    ]


def test_a_closure_resolves_each_dependency_once():
    costs = model()
    specification = costs.specify(name="Base")
    attempt = run(specification, document=costs.id)
    store = MemoryStore()
    store.put(costs)
    store.put(specification)
    found = closure([attempt], resolver=store)
    assert {item.id for item in found} == {attempt.id, specification.id, costs.id}
    assert found.load_run(attempt.id) is attempt
    # The closure is closed: it has no fallback.
    with pytest.raises(MissingReferenceError):
        found.load_model(uuid4())


def test_a_closure_raises_for_a_missing_dependency_and_a_limit():
    costs = model()
    specification = costs.specify(name="Base")
    with pytest.raises(MissingReferenceError) as error:
        closure([specification], resolver=None, where="no resolver")
    assert error.value.where == "no resolver"
    with pytest.raises(ContractError, match="document limit"):
        closure([specification, costs], resolver=None, limit=1)
    assert len(closure([specification, costs], resolver=None, limit=2)) == 2


def test_a_closure_checks_the_kind_of_a_document_that_it_holds():
    costs = model()
    specification = costs.specify(name="Base")
    impostor = run(specification)
    data = specification.to_data()
    data["model"] = str(impostor.id)
    pinned = rk.Specification.from_data(data)
    with pytest.raises(ReferenceTypeError):
        closure([pinned, impostor], resolver=None)


def test_require_revision_checks_the_uuid_and_the_kind():
    costs = model()
    assert require_revision(costs, costs.id, rk.Model) is costs
    with pytest.raises(IdentityConflictError):
        require_revision(costs, uuid4(), rk.Model)
    with pytest.raises(ReferenceTypeError):
        require_revision(costs, costs.id, rk.Run)


def test_documents_hold_market_paths():
    paths = histories()
    documents = Documents([paths])
    assert documents.load_paths(paths.id) is paths
    assert list(dependencies(paths)) == []
    assert closure([paths], resolver=None).load(paths.id) is paths
