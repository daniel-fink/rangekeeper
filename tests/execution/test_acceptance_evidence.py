"""Acceptance is strict, and Run evidence and execution manifests stay exact."""

from copy import deepcopy
from datetime import date
from uuid import uuid4

import pytest

from rangekeeper.execution.rule import RuleCapabilityError, evaluate
from rangekeeper.io import MemoryStore
from rangekeeper.model import Model
from rangekeeper.run import Run, validate
from rangekeeper.schema.validation import document_version
from rangekeeper.specification import Specification
from rangekeeper.specification.rule import RuleSet


def metadata(kind):
    return {"id": str(uuid4()), "schema_version": document_version(kind)}


def publication(model_data, output_data, *, rules=None, decisions=None):
    """Construct reported evidence without invoking an evaluator or solver."""
    model = Model.from_data(model_data)
    output_data["metadata"] = {
        **metadata("Model"),
        "previous": str(model.id),
    }
    output = Model.from_data(output_data)
    spec_data = {"metadata": metadata("Specification"), "model": str(model.id)}
    if rules is not None:
        spec_data["rules"] = rules
    spec = Specification.from_data(spec_data)
    store = MemoryStore()
    for item in (model, output, spec):
        store.put(item)
    report = {
        "status": {"completion": "completed", "solution": "feasible"},
        "runtime": {
            "implementations": [
                {
                    "kind": "evaluator",
                    "name": "independent-test-fixture",
                    "version": "1",
                }
            ]
        },
    }
    if decisions is not None:
        report["rule_evidence"] = decisions
    run = Run.from_data(
        {
            "metadata": metadata("Run"),
            "specification": str(spec.id),
            "outputs": [str(output.id)],
            "report": report,
        }
    )
    return run, store


@pytest.mark.parametrize(
    "before,after",
    [
        (0, False),
        (0, 0.0),
        ({"nested": [0]}, {"nested": [False]}),
        ({"items": [0, 1]}, {"items": [1, 0]}),
        ({"value": None}, {}),
    ],
)
def test_run_preserves_historical_claim_types_order_and_field_presence(before, after):
    data = {
        "metadata": metadata("Model"),
        "provenance": {
            "claims": [
                {
                    "id": str(uuid4()),
                    "kind": "asserted",
                    "content": before,
                    "method": {"code": "independent-test-fixture", "version": "1"},
                }
            ]
        },
    }
    unchanged, resolver = publication(data, deepcopy(data))
    assert validate(unchanged, resolver=resolver).valid
    output = deepcopy(data)
    output["provenance"]["claims"][0]["content"] = after
    forged, resolver = publication(data, output)
    result = validate(forged, resolver=resolver)
    assert not result.valid
    assert any("historical Claims changed" in issue.message for issue in result.issues)


@pytest.mark.parametrize("published", [True, False])
def test_recorded_control_without_prior_outcome_fails_runtime_and_stored_evidence(
    published,
):
    target, measure, point = (str(uuid4()) for _ in range(3))
    reference = {"target": target}
    quantity = {"magnitude": 1, "units": "dimensionless"}
    at = date(2027, 1, 1).isoformat()
    data = {
        "metadata": metadata("Model"),
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
                    "id": str(uuid4()),
                    "values": [
                        {
                            "id": target,
                            "key": "control",
                            "kind": "measurement",
                            "measure": measure,
                            "quantity": quantity,
                        }
                    ],
                }
            ]
        },
    }
    rules = {
        "id": str(uuid4()),
        "targets": [reference],
        "decisions": [
            {
                "id": point,
                "at": at,
                "observations": [
                    {"name": "control", "target": reference, "available_at": at}
                ],
                "rules": [],
                "fallback": [
                    {"kind": "assign", "target": reference, "quantity": quantity}
                ],
            }
        ],
    }
    with pytest.raises(RuleCapabilityError, match="earlier decision"):
        evaluate(RuleSet.from_data(rules), model=Model.from_data(data))
    forged = {
        "decision": point,
        "at": at,
        "observations": [
            {
                "name": "control",
                "target": reference,
                "quantity": quantity,
                "available_at": at,
            }
        ],
        "assignments": [{"target": reference, "quantity": quantity}],
        "terminated": False,
    }
    run, resolver = publication(data, deepcopy(data), rules=rules, decisions=[forged])
    if not published:
        raw = run.to_data()
        raw.pop("outputs")
        raw["report"]["status"]["solution"] = "unknown"
        raw["report"]["diagnostics"] = [
            {
                "severity": "info",
                "code": "fixture",
                "message": "Recorded rules trace without publication",
            }
        ]
        run = Run.from_data(raw)
    result = validate(run, resolver=resolver)
    assert not result.valid
    assert any("earlier decision" in issue.message for issue in result.issues)


def test_execution_manifest_tracks_shared_arithmetic_and_ignores_comments(tmp_path):
    import shutil
    from pathlib import Path

    import rangekeeper
    from rangekeeper.execution.implementation import _ENTRIES, fingerprint, sources

    source = Path(rangekeeper.__file__).parent
    shutil.copytree(
        source, tmp_path, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pyc")
    )
    before = {role: fingerprint(role, package=tmp_path) for role in _ENTRIES}
    # Shared arithmetic is in the import closure of both roles.
    assert all(
        "model/expression/evaluation.py" in sources(role, package=tmp_path)
        for role in _ENTRIES
    )
    arithmetic = tmp_path / "model/expression/evaluation.py"
    text = arithmetic.read_text()
    arithmetic.write_text(text + "\n# Presentation-only comment.\n")
    assert {role: fingerprint(role, package=tmp_path) for role in _ENTRIES} == before
    arithmetic.write_text(text + "\nIMPLEMENTATION_TEST_CHANGE = 1\n")
    assert all(
        fingerprint(role, package=tmp_path) != original
        for role, original in before.items()
    )
    arithmetic.unlink()
    with pytest.raises(FileNotFoundError):
        fingerprint("evaluator", package=tmp_path)


def test_strict_acceptance_is_exact_and_rejects_unfixed_references_before_cancellation():
    from rangekeeper.execution.acceptance import _comparisons
    from rangekeeper.execution.errors import UnsupportedError
    from rangekeeper.model import Expression, Reference
    from rangekeeper.model.expression import ExpressionKind, Operator
    from rangekeeper.quantity import Quantity, default_units

    target = uuid4()
    ref = Expression(
        id=uuid4(), kind=ExpressionKind.REFERENCE, target=Reference(target=target)
    )
    tiny = Expression(
        id=uuid4(),
        kind=ExpressionKind.QUANTITY,
        quantity=Quantity(magnitude=1e-12, units="dimensionless"),
    )
    predicate = Expression(
        id=uuid4(),
        kind=ExpressionKind.BINARY,
        operator=Operator.LESS_THAN,
        operands=(ref, tiny),
    )
    values = {target: Quantity(magnitude=0, units="dimensionless")}
    relation, left, right, exact = next(
        _comparisons(predicate, values, units=default_units, fixed={target})
    )
    assert relation == "less_than" and exact and left.magnitude < right.magnitude
    cancelled = predicate.replace(operands=(ref, ref.replace(id=uuid4())))
    with pytest.raises(UnsupportedError, match="fixed"):
        tuple(_comparisons(cancelled, values, units=default_units))
    relation, left, right, exact = next(
        _comparisons(cancelled, values, units=default_units, fixed={target})
    )
    assert exact and not left.magnitude < right.magnitude


@pytest.mark.parametrize("number", [False, complex(1, 2), float("inf"), float("nan")])
def test_shared_numerical_quantity_rejects_nonfinite_boolean_and_complex(number):
    from rangekeeper.model.expression.evaluation import finite_quantity
    from rangekeeper.shared.errors import NumericalError

    with pytest.raises(NumericalError):
        finite_quantity(number, "dimensionless")


def test_rule_result_normalizes_and_checks_outcomes():
    from dataclasses import FrozenInstanceError

    from rangekeeper.execution.rule import RuleResult
    from rangekeeper.model import Reference
    from rangekeeper.quantity import Quantity
    from rangekeeper.specification import Assignment
    from rangekeeper.specification.rule import RuleEvidence

    assignment = Assignment(
        target=Reference(target=uuid4()),
        quantity=Quantity(magnitude=1, units="dimensionless"),
    )
    outcome = RuleEvidence(
        decision=uuid4(),
        at=date(2027, 1, 1),
        observations=(),
        assignments=(assignment,),
        terminated=False,
    )
    supplied = [outcome]
    result = RuleResult(evidence=supplied)
    supplied.clear()
    assert result.evidence == (outcome,) and result.assignments == (assignment,)
    with pytest.raises(FrozenInstanceError):
        result.evidence = ()
    with pytest.raises(TypeError):
        RuleResult(evidence=[assignment])


def test_execution_manifest_tracks_actual_currency_catalogue(monkeypatch):
    from rangekeeper.execution import implementation
    from rangekeeper.quantity import UnitSystem

    before = implementation.fingerprint("compiler")
    assert before == implementation.fingerprint("compiler")
    monkeypatch.setattr(
        implementation, "default_units", UnitSystem(currencies=("AUD",))
    )
    assert implementation.fingerprint("compiler") != before
