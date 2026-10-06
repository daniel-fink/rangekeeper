"""Scope, diagnostics and dependency-order contracts for composable validation."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from rangekeeper._validation import (
    bounded,
    require,
    require_acyclic,
    require_ownership,
    require_unique,
)
from rangekeeper.diagnostics import Issue
from rangekeeper.errors import ContractError
from rangekeeper.model._expression import (
    build_scope,
    infer_expression_domain,
    validate_constraint_predicates,
    validate_function_signature,
)
from rangekeeper.model._formulation import (
    validate_formulation_names,
    validate_formulations,
)
from rangekeeper.validate import require_uuid


def test_argument_guards_are_distinct_from_semantic_rules():
    identity = uuid4()
    assert require_uuid(identity, "id") is identity
    with pytest.raises(TypeError, match="id must be a UUID"):
        require_uuid(str(identity), "id")
    with pytest.raises(ContractError, match="rule failed"):
        require(False, "rule failed")


def test_uniqueness_is_owner_local_case_sensitive_and_non_mutating():
    records = [{}, {"code": None}, {"code": "a"}, {"code": "A"}, {"code": ""}]
    before = deepcopy(records)
    require_unique(iter(records), "code", "code")
    require_unique([{"code": "a"}], "code", "another owner's code")
    assert records == before
    with pytest.raises(ContractError) as failure:
        require_unique([{"code": ""}, {"code": ""}], "code", "code")
    assert failure.value.path == "/1/code"


def test_uniqueness_diagnostic_retains_collection_and_escaped_field():
    with pytest.raises(ContractError) as failure:
        require_unique([{"a/b~c": "x"}, {"a/b~c": "x"}], "a/b~c", "key", path="/items")
    assert failure.value.code == "semantic.unique"
    assert failure.value.path == "/items/1/a~1b~0c"
    assert str(failure.value) == "duplicate key: x"


def test_acyclic_accepts_shared_and_external_targets_without_mutation():
    edges = {"root": ["a", "b"], "a": ["leaf"], "b": ["leaf", "external"]}
    before = deepcopy(edges)
    require_acyclic(edges, "membership")
    assert edges == before


@pytest.mark.parametrize("edges", [{"a": ["a"]}, {"a": ["b"], "b": ["a"]}])
def test_cycles_have_rule_context(edges):
    with pytest.raises(ContractError) as failure:
        require_acyclic(edges, "membership", path="/members")
    assert failure.value.code == "semantic.cycle"
    assert failure.value.path == "/members"


def test_ownership_rejects_repeated_declarations_and_containment_cycles():
    child = {"id": "one"}
    with pytest.raises(ContractError) as failure:
        require_ownership({"items": [child, child]})
    assert failure.value.code == "semantic.identity"
    assert failure.value.path == "/items/1/id"
    cycle = {}
    cycle["child"] = cycle
    with pytest.raises(ContractError) as failure:
        require_ownership(cycle)
    assert failure.value.code == "semantic.containment"
    assert failure.value.path == "/child"


def test_report_keeps_semantic_context_and_revision_identity():
    identity = uuid4()
    report = bounded(
        [],
        lambda: require_unique(
            [{"code": "same"}, {"code": "same"}], "code", "code", path="/items"
        ),
        document={"metadata": {"id": str(identity)}},
    )
    assert report.issues == (
        Issue("semantic.unique", "duplicate code: same", identity, "/items/1/code"),
    )


def test_failed_prerequisites_skip_dependent_checks():
    called = []
    issue = Issue("structure.required", "missing input")
    report = bounded([issue], lambda: called.append(True))
    assert report.issues == (issue,)
    assert called == []


def test_programming_errors_are_not_reported_as_bad_document_data():
    def broken_check():
        raise KeyError("bug in check")

    with pytest.raises(KeyError, match="bug in check"):
        bounded([], broken_check)


def test_scope_tables_are_read_only_and_checks_do_not_change_the_input():
    measure = {"id": "measure", "units": "m^2"}
    data = {"definitions": {"measures": [measure]}}
    before = deepcopy(data)
    scope = build_scope(data)
    assert scope.measures["measure"] is measure
    with pytest.raises(TypeError):
        scope.measures["other"] = measure
    with pytest.raises(FrozenInstanceError):
        scope.identities = frozenset()
    assert infer_expression_domain({"id": "p", "kind": "boolean"}, scope=scope) == {
        "kind": "boolean"
    }
    assert data == before


def test_constraint_names_and_predicates_are_separate_rules():
    predicate = {"id": "predicate", "kind": "boolean"}
    constraints = [
        {"id": "first", "code": "limit", "predicate": "predicate"},
        {"id": "second", "code": "limit", "predicate": "predicate"},
    ]
    # Two owners may reuse a code and both refer to the same predicate node.
    roots = [
        {"id": "a", "constraints": constraints[:1], "expressions": [predicate]},
        {"id": "b", "constraints": constraints[1:]},
    ]
    before = deepcopy(roots)
    validate_formulations({"formulations": roots})
    assert roots == before
    # Combining those Constraints under one owner changes only the naming rule.
    with pytest.raises(ContractError, match="duplicate Constraint code"):
        validate_formulation_names([{"constraints": constraints}])
    validate_constraint_predicates(constraints, [predicate], scope=build_scope({}))


@pytest.mark.parametrize(
    "collection,field",
    [
        ("bindings", "name"),
        ("values", "key"),
        ("constraints", "code"),
    ],
)
def test_local_naming_rule_reports_nested_owner_without_resolving_references(
    collection, field
):
    roots = [{"formulations": [{collection: [{field: "x"}, {field: "x"}]}]}]
    with pytest.raises(ContractError) as failure:
        validate_formulation_names(roots)
    assert (
        failure.value.path == f"/formulations/0/formulations/0/{collection}/1/{field}"
    )


@pytest.mark.parametrize(
    "predicate,expressions,code",
    [
        ("missing", [], "reference.predicate"),
        (
            "number",
            [
                {
                    "id": "number",
                    "kind": "quantity",
                    "quantity": {"magnitude": 1, "units": "dimensionless"},
                }
            ],
            "semantic.predicate",
        ),
    ],
)
def test_predicate_reports_reference_and_domain_failures(predicate, expressions, code):
    with pytest.raises(ContractError) as failure:
        validate_constraint_predicates(
            [{"id": "constraint", "predicate": predicate}],
            expressions,
            scope=build_scope({}),
        )
    assert failure.value.code == code
    assert failure.value.path == "/constraints/0/predicate"


def test_constraint_identity_cannot_collide_with_a_value_declaration():
    scope = build_scope(
        {"input_domains": [{"id": "value", "domain": {"kind": "number"}}]}
    )
    with pytest.raises(ContractError, match="duplicate Constraint identity"):
        validate_constraint_predicates(
            [{"id": "value", "predicate": "p"}],
            [{"id": "p", "kind": "boolean"}],
            scope=scope,
        )


def test_expression_identity_cannot_collide_with_a_constraint():
    with pytest.raises(ContractError, match="duplicate Expression identity"):
        validate_constraint_predicates(
            [{"id": "same", "predicate": "same"}],
            [{"id": "same", "kind": "boolean"}],
            scope=build_scope({}),
        )


def test_signature_validation_is_independently_composable():
    function = {
        "id": "function",
        "code": "f",
        "result": {"kind": "number"},
        "parameters": [
            {
                "name": "x",
                "kind": "positional_or_named",
                "required": False,
                "domain": {"kind": "number"},
            },
            {
                "name": "y",
                "kind": "positional_or_named",
                "required": True,
                "domain": {"kind": "number"},
            },
        ],
    }
    with pytest.raises(
        ContractError, match="required positional parameter follows optional"
    ):
        validate_function_signature(function, scope=build_scope({}))
    with pytest.raises(
        ContractError, match="required positional parameter follows optional"
    ):
        build_scope({"functions": [function]})


def test_model_and_partial_specification_share_local_naming_diagnostics():
    from rangekeeper.errors import ValidationError
    from rangekeeper.model.validation import validate as validate_model
    from rangekeeper.specification import Specification

    constraints = [
        {"id": str(uuid4()), "code": "same", "predicate": str(uuid4())}
        for _ in range(2)
    ]
    formulations = [{"id": str(uuid4()), "constraints": constraints}]
    model = {
        "metadata": {"id": str(uuid4()), "schema_version": "0.6.0"},
        "system": {"formulations": formulations},
    }
    issue = validate_model(model).issues[0]
    assert issue.code == "semantic.unique"
    assert issue.path == "/system/formulations/0/constraints/1/code"
    specification = {
        "metadata": {"id": str(uuid4()), "schema_version": "0.6.0"},
        "formulations": formulations,
    }
    with pytest.raises(ValidationError) as failure:
        Specification.from_data(specification)
    issue = failure.value.report.issues[0]
    assert issue.code == "semantic.unique"
    assert issue.path == "/formulations/0/constraints/1/code"


def test_combined_entity_assembly_namespace_reports_canonical_storage_path():
    from rangekeeper.model.validation import validate

    model = {
        "metadata": {"id": str(uuid4()), "schema_version": "0.6.0"},
        "system": {
            "entities": [{"id": str(uuid4()), "code": "same"}],
            "assemblies": [{"id": str(uuid4()), "code": "same"}],
        },
    }
    issue = validate(model).issues[0]
    assert issue.code == "semantic.unique"
    assert issue.path == "/system/assemblies/0/code"


def test_flattened_constraint_diagnostic_returns_to_its_owning_formulation():
    from rangekeeper.model.validation import validate

    model = {
        "metadata": {"id": str(uuid4()), "schema_version": "0.6.0"},
        "system": {
            "formulations": [
                {
                    "id": str(uuid4()),
                    "formulations": [
                        {
                            "id": str(uuid4()),
                            "constraints": [
                                {
                                    "id": str(uuid4()),
                                    "predicate": str(uuid4()),
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    }
    issue = validate(model).issues[0]
    assert issue.code == "reference.predicate"
    assert issue.path == "/system/formulations/0/formulations/0/constraints/0/predicate"


def test_model_ownership_diagnostic_uses_canonical_document_shape():
    from rangekeeper.model.validation import validate

    identity = str(uuid4())
    model = {
        "metadata": {"id": str(uuid4()), "schema_version": "0.6.0"},
        "system": {"entities": [{"id": identity}], "assemblies": [{"id": identity}]},
    }
    issue = validate(model).issues[0]
    assert issue.code == "semantic.identity"
    assert issue.path == "/system/assemblies/0/id"
