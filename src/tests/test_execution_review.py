"""Public failure boundaries found in the independent refactoring review."""

from uuid import uuid4

import pytest

from rangekeeper import Model, Specification
from rangekeeper.execution import Executor
from rangekeeper.io import MemoryStore
from rangekeeper.policies import Policy, PolicyCapabilityError, evaluate
from rangekeeper.run import CompletionStatus, SolutionStatus, validate


def identity():
    return str(uuid4())


def metadata():
    return {"id": identity(), "schema_version": "0.7.0"}


def literal(value):
    return {
        "id": identity(),
        "kind": "quantity",
        "quantity": {
            "magnitude": value,
            "units": "dimensionless",
        },
    }


def binary(operator, left, right):
    return {
        "id": identity(),
        "kind": "binary",
        "operator": operator,
        "operands": [left, right],
    }


class UncalledBackend:
    def solve(self, *args, **kwargs):
        pytest.fail("preparation failure must not invoke a backend")


def failed_run(model, specification, *, code, solution):
    store = MemoryStore()
    store.put(model)
    run = Executor(store, backend=UncalledBackend()).execute(specification)
    assert run.report.status.completion is CompletionStatus.FAILED
    assert run.report.status.solution is solution
    assert not run.record.outputs
    assert code in {item.code for item in run.report.diagnostics}
    validate(run, resolver=store).raise_if_invalid()
    assert store.load_run(run.id).to_data() == run.to_data()
    return run


@pytest.mark.parametrize("unsupported", [False, True])
def test_fixed_strict_predicate_failures_become_stored_runs(unsupported):
    functions = []
    if unsupported:
        function_id = identity()
        functions.append(
            {
                "id": function_id,
                "code": "test.constant",
                "name": "Declared constant",
                "version": "1",
                "parameters": [],
                "result": {"kind": "number"},
                "semantics": "Return a constant.",
                "unit_rule": "Dimensionless result.",
            }
        )
        left = {
            "id": identity(),
            "kind": "call",
            "call": {"function": function_id, "arguments": []},
        }
    else:
        left = binary("power", literal(-1), literal(0.5))
    predicate = binary("less_than", left, literal(1))
    constraint_id = identity()
    model = Model.from_data(
        {
            "metadata": metadata(),
            "definitions": {"functions": functions},
            "system": {
                "formulations": [
                    {
                        "id": identity(),
                        "expressions": [predicate],
                        "constraints": [
                            {"id": constraint_id, "predicate": predicate["id"]}
                        ],
                    }
                ]
            },
        }
    )
    specification = Specification.from_data(
        {
            "metadata": metadata(),
            "model": str(model.id),
        }
    )
    run = failed_run(
        model,
        specification,
        code="unsupported_capability" if unsupported else "numerical_failure",
        solution=SolutionStatus.NOT_ASSESSED if unsupported else SolutionStatus.UNKNOWN,
    )
    if unsupported:
        diagnostic = next(
            item
            for item in run.report.diagnostics
            if item.code == "unsupported_capability"
        )
        assert diagnostic.document == model.id
        assert str(diagnostic.target) == constraint_id


def test_incomplete_selected_policy_trace_uses_capability_failure_boundary():
    measure, target = identity(), identity()
    reference = {"target": target}
    model = Model.from_data(
        {
            "metadata": metadata(),
            "definitions": {
                "measures": [
                    {
                        "id": measure,
                        "code": "factor",
                        "name": "Factor",
                        "units": "dimensionless",
                    }
                ]
            },
            "system": {
                "formulations": [
                    {
                        "id": identity(),
                        "values": [
                            {
                                "id": target,
                                "key": "control",
                                "kind": "measurement",
                                "measure": measure,
                            }
                        ],
                    }
                ]
            },
        }
    )
    policy = {
        "id": identity(),
        "targets": [reference],
        "decisions": [
            {
                "id": identity(),
                "at": "2027-01-01",
                "observations": [],
                "rules": [
                    {
                        "id": identity(),
                        "condition": {
                            "id": identity(),
                            "kind": "boolean",
                            "boolean": False,
                        },
                        "actions": [
                            {
                                "kind": "assign",
                                "target": reference,
                                "quantity": {"magnitude": 1, "units": "dimensionless"},
                            }
                        ],
                    }
                ],
                "fallback": [{"kind": "terminate"}],
            }
        ],
    }
    specification = Specification.from_data(
        {
            "metadata": metadata(),
            "model": str(model.id),
            "policy": policy,
        }
    )
    with pytest.raises(PolicyCapabilityError, match="each controlled target"):
        evaluate(Policy.from_data(policy), model=model)
    failed_run(
        model,
        specification,
        code="unsupported_capability",
        solution=SolutionStatus.NOT_ASSESSED,
    )
