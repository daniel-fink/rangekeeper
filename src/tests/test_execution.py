"""Scalar acceptance through public documents and real isolated Pyomo/HiGHS runs."""

from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID, uuid4

import pytest

from rangekeeper import Model, Specification
from rangekeeper.errors import MissingReferenceError, ValidationError
from rangekeeper.io import MemoryStore, DirectoryStore, yaml
from rangekeeper.run import validate
from rangekeeper.specification import SpecificationRecord
from rangekeeper.execution import Executor, Tolerances
from rangekeeper.execution import preparation, compiler, acceptance, publication
from rangekeeper.execution.backends import PyomoHighs, Result
from rangekeeper.execution.errors import NumericalError

EXAMPLES = Path(__file__).resolve().parents[2] / "schema/examples"
HOME = UUID("194afc26-3e2e-507b-ad0c-a73a4b0b2ccd")
RENT = UUID("e3fb1434-5371-5bcb-b0b8-e3af2bf65022")
NOI = UUID("9324f928-cfc8-50bb-ba99-fe8c02a6dbd2")
CAPITAL = UUID("a947d40b-d9b0-54cb-a2a4-f8f598405ac2")
RATE = UUID("0ceeb0d5-91b7-53b7-b823-2234e2262a4f")
COST = UUID("cbe37d0a-79ce-5d1b-b0cb-8d2a42acc991")


@pytest.fixture(autouse=True)
def optional_backend():
    if any(importlib.util.find_spec(name) is None for name in ("pyomo", "highspy")):
        pytest.skip("requires the optional execution extra")


def data(name):
    kind = Model if name.startswith("model") else Specification
    return yaml.read(EXAMPLES / f"{name}.yaml", kind=kind).to_data()


def fresh(document):
    document = deepcopy(document)
    document["metadata"]["previous"] = document["metadata"]["id"]
    document["metadata"]["id"] = str(uuid4())
    return document


def records(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from records(child)
    elif isinstance(value, list):
        for child in value:
            yield from records(child)


def setup(store=None, model_data=None):
    store = MemoryStore() if store is None else store
    model = Model.from_data(data("model") if model_data is None else model_data)
    store.put(model)
    for name in (
        "specification-common",
        "specification-composed-forward",
        "specification-composed-inverse",
    ):
        store.put(Specification.from_data(data(name)))
    return store, model


def spec(name="specification-forward", *, model=None, **changes):
    payload = fresh(data(name))
    payload.update(changes)
    if model is not None:
        payload["model"] = str(model.id)
    return Specification.from_data(payload)


def execute(store, specification):
    run = Executor(store).execute(specification)
    validate(run, resolver=store).raise_if_invalid()
    assert store.load_run(run.id).to_data() == run.to_data()
    return run


def output(store, run):
    assert run.report.status.solution == "feasible", [
        (d.code, d.message) for d in run.report.diagnostics
    ]
    return store.load_model(run.record.outputs[0])


def declarations(model):
    """Compare governing declarations while allowing their recorded quantities to change."""
    system = model.system.to_data()
    for node in records(system):
        if node.get("kind") == "measurement" and "id" in node:
            node.pop("quantity", None)
    return system


@pytest.mark.parametrize("disk", [False, True])
def test_declared_forward_then_inverse_on_genuine_output(tmp_path, disk):
    store, original = setup(DirectoryStore(tmp_path / "revisions") if disk else None)
    before = original.to_data()
    forward = execute(
        store,
        store.load_specification(
            UUID(data("specification-composed-forward")["metadata"]["id"])
        ),
    )
    first = output(store, forward)
    assert first.value(NOI).quantity.magnitude == pytest.approx(550000)
    assert first.value(CAPITAL).quantity.magnitude == pytest.approx(11000000)
    assert first.metadata.previous == original.id
    common = store.load_specification(
        UUID(data("specification-common")["metadata"]["id"])
    )
    changed = fresh(common.to_data())
    changed["model"] = str(first.id)
    common2 = common.revise(SpecificationRecord.from_data(changed))
    store.put(common2)
    inverse = store.load_specification(
        UUID(data("specification-composed-inverse")["metadata"]["id"])
    )
    changed = fresh(inverse.to_data())
    changed["includes"] = [str(common2.id)]
    inverse2 = inverse.revise(SpecificationRecord.from_data(changed))
    run2 = execute(store, inverse2)
    second = output(store, run2)
    assert second.value(RENT).quantity.magnitude == pytest.approx(27500)
    assert second.value(NOI).quantity.magnitude == pytest.approx(500000)
    assert second.metadata.previous == first.id
    assert first.value(RENT).quantity.magnitude == 30000
    assert original.to_data() == before
    assert (
        first.definitions.to_data()
        == second.definitions.to_data()
        == original.definitions.to_data()
    )
    assert declarations(first) == declarations(second) == declarations(original)
    area = UUID("9d86011c-1658-5c10-87c1-94d281b74e96")
    assert (
        first.value(area).quantity
        == second.value(area).quantity
        == original.value(area).quantity
    )
    assert {claim.id for claim in first.provenance.claims} <= {
        claim.id for claim in second.provenance.claims
    }
    assert {claim.id for claim in original.provenance.claims} <= {
        claim.id for claim in first.provenance.claims
    }
    assert {item.kind for item in forward.report.runtime.implementations} == {
        "compiler",
        "solver",
        "evaluator",
    }
    assert any(
        d.code == "constraint_residual" and d.tolerance is not None
        for d in run2.report.diagnostics
    )


@pytest.mark.parametrize(
    "change, expected", [("input", 11800000), ("expression", 13000000)]
)
def test_inputs_and_declared_equations_drive_results(change, expected):
    model_data = fresh(data("model"))
    if change == "expression":
        next(
            node for node in records(model_data) if node.get("operator") == "subtract"
        )["operator"] = "add"
    store, model = setup(model_data=model_data)
    payload = fresh(data("specification-forward"))
    payload["model"] = str(model.id)
    if change == "input":
        next(a for a in payload["assignments"] if a["target"]["value"] == str(RENT))[
            "quantity"
        ]["magnitude"] = 32000
    assert output(store, execute(store, Specification.from_data(payload))).value(
        CAPITAL
    ).quantity.magnitude == pytest.approx(expected)


def test_assignment_unit_conversion_is_checked_and_published_canonically():
    store, model = setup()
    payload = fresh(data("specification-forward"))
    next(a for a in payload["assignments"] if a["target"]["value"] == str(RENT))[
        "quantity"
    ] = {
        "magnitude": 2500,
        "units": "AUD/dwelling/month",
    }
    result = output(store, execute(store, Specification.from_data(payload)))
    assert result.value(RENT).quantity.units == "AUD/dwelling/year"
    assert result.value(RENT).quantity.magnitude == pytest.approx(30000)
    assert result.value(CAPITAL).quantity.magnitude == pytest.approx(11000000)


def literal(value, units="AUD"):
    return {
        "id": str(uuid4()),
        "kind": "quantity",
        "quantity": {"magnitude": value, "units": units},
    }


def reference(id):
    return {"id": str(uuid4()), "kind": "reference", "target": dict(value=str(id))}


def binary(operator, left, right):
    return {
        "id": str(uuid4()),
        "kind": "binary",
        "operator": operator,
        "operands": [left, right],
    }


def formulation(expression):
    return {
        "id": str(uuid4()),
        "expressions": [expression],
        "constraints": [{"id": str(uuid4()), "predicate": expression["id"]}],
    }


@pytest.mark.parametrize(
    "operator,bound,feasible",
    [
        ("less_than_or_equal", 12000000, True),
        ("greater_than_or_equal", 10000000, True),
        ("less_than_or_equal", 10000000, False),
        ("equal", 10000000, False),
    ],
)
def test_temporary_bounds_and_inconsistent_equations(operator, bound, feasible):
    store, model = setup()
    temporary = formulation(binary(operator, reference(CAPITAL), literal(bound)))
    run = execute(store, spec(formulations=[temporary]))
    assert run.report.status.completion == "completed"
    assert run.report.status.solution == ("feasible" if feasible else "infeasible")
    if feasible:
        assert declarations(output(store, run)) == declarations(model)
        assert all(
            f.id != UUID(temporary["id"])
            for f in output(store, run).system.formulations
        )
    else:
        assert not run.record.outputs
        assert any("provenInfeasible" in d.message for d in run.report.diagnostics)


@pytest.mark.parametrize(
    "kind",
    ["nonlinear", "strict", "objectives", "missing_role", "units", "division_zero"],
)
def test_expected_failures_have_evidence_and_no_output(kind):
    store, model = setup()
    payload = fresh(data("specification-forward"))
    if kind == "nonlinear":
        payload["assignments"] = [
            a for a in payload["assignments"] if a["target"]["value"] != str(RATE)
        ]
        payload["unknowns"].append(dict(value=str(RATE)))
    elif kind == "strict":
        payload["formulations"] = [
            formulation(binary("less_than", reference(CAPITAL), literal(12000000)))
        ]
    elif kind == "objectives":
        payload = fresh(data("specification-objectives"))
    elif kind == "missing_role":
        payload["assignments"] = [
            a for a in payload["assignments"] if a["target"]["value"] != str(RENT)
        ]
    elif kind == "units":
        payload["formulations"] = [
            formulation(
                binary("equal", reference(CAPITAL), literal(11000000, "AUD/year"))
            )
        ]
    else:
        payload["formulations"] = [
            formulation(
                binary(
                    "equal",
                    reference(CAPITAL),
                    binary("divide", literal(1), literal(0, "dimensionless")),
                )
            )
        ]
    run = execute(store, Specification.from_data(payload))
    assert run.report.status.completion == "failed"
    assert not run.record.outputs
    assert any(
        d.code
        in {"unsupported_capability", "specification_invalid", "numerical_failure"}
        for d in run.report.diagnostics
    )


def test_underdetermined_case_returns_one_candidate_without_uniqueness_claim():
    store, model = setup()
    payload = fresh(data("specification-forward"))
    payload["assignments"] = [
        a for a in payload["assignments"] if a["target"]["value"] != str(RENT)
    ]
    payload["unknowns"].append(dict(value=str(RENT)))
    run = execute(store, Specification.from_data(payload))
    assert run.report.status.solution == "feasible"
    assert any(d.code == "underdetermined" for d in run.report.diagnostics)


class WrongCandidate:
    def solve(self, problem, *, limits, remaining):
        result = PyomoHighs().solve(problem, limits=limits, remaining=remaining)
        values = dict(result.candidate)
        values[str(CAPITAL)] += 1000000
        return replace(result, candidate=values)


def test_independent_acceptance_rejects_solver_claim_and_serialized_tampering():
    store, model = setup()
    specification = spec()
    store.put(specification)
    run = Executor(store, backend=WrongCandidate()).execute(specification)
    assert run.report.status.completion == "failed"
    assert run.report.status.solution == "unknown"
    assert not run.record.outputs
    assert any(d.code == "numerical_rejection" for d in run.report.diagnostics)
    assert any(
        d.severity == "error" and d.code == "constraint_residual"
        for d in run.report.diagnostics
    )
    from rangekeeper.specification import compose

    prepared = preparation.prepare(
        compose(specification, resolver=store), resolver=store
    )
    proposed = publication.candidate(
        prepared, {str(NOI): 550000, str(CAPITAL): 11000000}, run_id=uuid4()
    )
    changed = proposed.to_data()
    next(node for node in records(changed["system"]) if node.get("id") == str(RENT))[
        "quantity"
    ]["magnitude"] = 30001
    assert not acceptance.check(prepared, Model.from_data(changed)).accepted


def test_composition_conflict_and_mixed_nested_batches_account_for_every_case():
    store, model = setup()
    good = spec()
    store.put(good)
    other = spec()
    store.put(other)
    conflict = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "0.5.0"},
            "includes": [str(good.id), str(other.id)],
        }
    )
    store.put(conflict)
    batch = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "0.5.0"},
            "model": str(model.id),
            "cases": [str(good.id), str(conflict.id)],
        }
    )
    store.put(batch)
    outer = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "0.5.0"},
            "cases": [str(batch.id), str(good.id)],
        }
    )
    parent = execute(store, outer)
    assert parent.report.status.completion == "partial"
    nested, repeated = [store.load_run(id) for id in parent.record.spawns]
    success, failed = [store.load_run(id) for id in nested.record.spawns]
    assert failed.report.status.solution == "not_assessed"
    assert any(d.code == "specification_invalid" for d in failed.report.diagnostics)
    assert repeated.id != success.id
    assert set(parent.record.outputs) == set(nested.record.outputs) | set(
        repeated.record.outputs
    )


def test_requested_settings_are_applied_or_explicitly_accounted_for():
    store, _ = setup()
    run = execute(
        store,
        spec(
            settings={
                "relative_tolerance": 1e-8,
                "iteration_limit": 123,
                "time_limit": 10,
            }
        ),
    )
    effective = run.report.runtime.settings
    assert effective.iteration_limit == 123 and effective.time_limit == 10
    assert effective.relative_tolerance is None
    assert any(
        d.code == "settings_adjusted" and "relative_tolerance" in d.message
        for d in run.report.diagnostics
    )
    evidence = json.loads(
        next(
            d.message for d in run.report.diagnostics if d.code == "solver_termination"
        )
    )
    assert evidence["solver_options"]["simplex_iteration_limit"] == 123
    assert evidence["simplex_iterations"] >= 0


def test_tiny_budget_never_claims_infeasibility():
    store, _ = setup()
    run = execute(store, spec(settings={"time_limit": 1e-7}))
    assert run.report.status.completion == "limited"
    assert run.report.status.solution == "not_assessed"
    assert any(d.code == "attempt_deadline" for d in run.report.diagnostics)
    assert not run.record.outputs


def test_deadline_kills_and_reaps_a_stalled_worker(monkeypatch, tmp_path):
    from rangekeeper.execution.backends import pyomo

    real_run = subprocess.run
    pid_file = tmp_path / "worker.pid"

    def stalled(args, **kwargs):
        script = f"import os,time;open({str(pid_file)!r},'w').write(str(os.getpid()));time.sleep(30)"
        return real_run([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(pyomo.subprocess, "run", stalled)
    store, _ = setup()
    started = time.monotonic()
    run = execute(store, spec(settings={"time_limit": 1}))
    assert time.monotonic() - started < 5
    assert run.report.status.completion == "limited"
    assert run.report.status.solution == "unknown"
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


@pytest.mark.parametrize(
    "termination", ["error", "infeasibleOrUnbounded", "unknown", "iterationLimit"]
)
def test_backend_statuses_do_not_overclaim(termination):
    class Backend:
        def solve(self, problem, **kwargs):
            return Result(termination)

    store, _ = setup()
    run = Executor(store, backend=Backend()).execute(spec())
    assert run.report.status.solution == "unknown"
    assert not run.record.outputs
    assert run.report.status.completion == (
        "failed"
        if termination == "error"
        else "limited" if termination == "iterationLimit" else "completed"
    )


def test_missing_references_and_invalid_batch_graph_raise_before_execution():
    store, _ = setup()
    missing = spec(model=Model.from_data(fresh(data("model"))))
    with pytest.raises(MissingReferenceError):
        Executor(store).execute(missing)
    id1, id2 = uuid4(), uuid4()
    for id, other in ((id1, id2), (id2, id1)):
        store.put(
            Specification.from_data(
                {
                    "metadata": {"id": str(id), "schema_version": "0.5.0"},
                    "cases": [str(other)],
                }
            )
        )
    with pytest.raises(ValidationError, match="cycle"):
        Executor(store).execute(store.load_specification(id1))


@pytest.mark.parametrize(
    "kwargs",
    [{"absolute": -1}, {"relative": 1}, {"relative": float("nan")}, {"absolute": True}],
)
def test_acceptance_policy_rejects_invalid_tolerances(kwargs):
    with pytest.raises(ValueError):
        Tolerances(**kwargs)


@pytest.mark.parametrize("truth", [True, False])
def test_constant_only_assertions_and_repeated_publication(truth):
    model_data = fresh(data("model"))
    model_data["system"]["formulations"] = [
        formulation({"id": str(uuid4()), "kind": "boolean", "boolean": truth})
    ]
    store, model = setup(model_data=model_data)
    investigation = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "0.5.0"},
            "model": str(model.id),
        }
    )
    run = execute(store, investigation)
    assert run.report.status.solution == ("feasible" if truth else "infeasible")
    if truth:
        second = spec(
            model=output(store, run), assignments=[], unknowns=[], estimates=[]
        )
        assert execute(store, second).report.status.solution == "feasible"


def test_unconstrained_unknown_has_explicit_choice_evidence():
    model_data = fresh(data("model"))
    model_data["system"]["formulations"] = []
    store, model = setup(model_data=model_data)
    # This structural Value survives removal of the valuation Formulations.
    area = UUID("9d86011c-1658-5c10-87c1-94d281b74e96")
    investigation = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "0.5.0"},
            "model": str(model.id),
            "unknowns": [dict(value=str(area))],
        }
    )
    run = execute(store, investigation)
    assert output(store, run).value(area).quantity.magnitude == 0
    assert any(d.code == "underdetermined" for d in run.report.diagnostics)
    assert any(
        str(area) in d.message and "initialized_to_zero" in d.message
        for d in run.report.diagnostics
    )


def test_real_simplex_iteration_limit_has_no_infeasibility_claim():
    import random

    randomizer = random.Random(0)
    ids = [uuid4() for _ in range(2)]
    measure = uuid4()
    equations = []
    for id in ids:
        equations.extend(
            [
                formulation(
                    binary(
                        "greater_than_or_equal",
                        reference(id),
                        literal(-5, "dimensionless"),
                    )
                ),
                formulation(
                    binary(
                        "less_than_or_equal", reference(id), literal(5, "dimensionless")
                    )
                ),
            ]
        )
    # A bounded polygon containing (1, 1) needs simplex work after presolve.
    # Equality-only fixtures can be solved entirely by presolve in these versions.
    for _ in range(6):
        coefficients = [randomizer.randint(-9, 9) for _ in ids]
        rhs = sum(coefficients) - randomizer.uniform(0.1, 2)
        terms = [
            binary("multiply", literal(c, "dimensionless"), reference(id))
            for c, id in zip(coefficients, ids)
        ]
        equations.append(
            formulation(
                binary(
                    "greater_than_or_equal",
                    binary("add", *terms),
                    literal(rhs, "dimensionless"),
                )
            )
        )
    model = Model.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "0.5.0"},
            "definitions": {
                "measures": [
                    {
                        "id": str(measure),
                        "code": "scalar",
                        "name": "Scalar",
                        "units": "dimensionless",
                    }
                ]
            },
            "system": {
                "entities": [
                    {
                        "id": str(uuid4()),
                        "characteristics": {
                            "values": [
                                {
                                    "id": str(id),
                                    "key": f"x{i}",
                                    "kind": "measurement",
                                    "measure": str(measure),
                                }
                                for i, id in enumerate(ids)
                            ]
                        },
                    }
                ],
                "formulations": equations,
            },
        }
    )
    store = MemoryStore()
    store.put(model)
    specification = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "0.5.0"},
            "model": str(model.id),
            "unknowns": [dict(value=str(id)) for id in ids],
            "settings": {"iteration_limit": 1, "time_limit": 30},
        }
    )
    run = execute(store, specification)
    assert run.report.status.completion == "limited"
    assert run.report.status.solution in {"feasible", "unknown"}
    evidence = json.loads(
        next(
            d.message for d in run.report.diagnostics if d.code == "solver_termination"
        )
    )
    assert evidence["termination"] == "iterationLimit"
    assert evidence["simplex_iterations"] == 1


def test_unknown_assignment_units_still_allow_failed_run_evidence():
    store, _ = setup()
    payload = fresh(data("specification-forward"))
    payload["assignments"][0]["quantity"]["units"] = "not_a_known_unit"
    run = execute(store, Specification.from_data(payload))
    assert run.report.status.completion == "failed"
    assert run.report.status.solution == "not_assessed"


@pytest.mark.parametrize(
    "operation", ["negate", "divide", "power", "constant_power", "conjunction"]
)
def test_supported_arithmetic_and_conjunction(operation):
    store, _ = setup()
    if operation == "negate":
        expression = {
            "id": str(uuid4()),
            "kind": "unary",
            "operator": "negate",
            "operand": reference(CAPITAL),
        }
        predicate = binary("equal", expression, literal(-11000000))
    elif operation == "divide":
        predicate = binary(
            "equal",
            binary("divide", reference(CAPITAL), literal(2, "dimensionless")),
            literal(5500000),
        )
    elif operation == "power":
        predicate = binary(
            "equal",
            binary("power", reference(CAPITAL), literal(1, "dimensionless")),
            literal(11000000),
        )
    elif operation == "constant_power":
        factor = binary(
            "power", literal(2, "dimensionless"), literal(3, "dimensionless")
        )
        predicate = binary(
            "equal", binary("multiply", reference(CAPITAL), factor), literal(88000000)
        )
    else:
        predicate = binary(
            "logical_and",
            binary("greater_than_or_equal", reference(CAPITAL), literal(10000000)),
            binary("less_than_or_equal", reference(CAPITAL), literal(12000000)),
        )
    assert (
        execute(
            store, spec(formulations=[formulation(predicate)])
        ).report.status.solution
        == "feasible"
    )


@pytest.mark.parametrize("magnitude", [float("nan"), float("inf"), True])
def test_nonfinite_or_boolean_backend_candidates_are_never_published(magnitude):
    class Backend:
        def solve(self, problem, **kwargs):
            return Result(
                "convergenceCriteriaSatisfied", {NOI: 550000.0, CAPITAL: magnitude}
            )

    store, _ = setup()
    run = Executor(store, backend=Backend()).execute(spec())
    assert run.report.status.completion == "failed"
    assert run.report.status.solution == "unknown"
    assert not run.record.outputs


def test_scalar_execution_retains_unrelated_rich_content():
    """New property/Flow content must not become implicit scalar solve variables."""
    from rangekeeper.model.content import encode

    payload = data("model")
    identity = uuid4()
    payload["system"]["entities"][0].setdefault("characteristics", {}).setdefault(
        "values", []
    ).append(
        {
            "id": str(identity),
            "key": "source-note",
            "kind": "property",
            "content": encode("retained").to_data(),
        }
    )
    store, model = setup(model_data=payload)
    run = execute(store, spec(model=model))
    assert output(store, run).value(identity).content == encode("retained")


def test_scalar_preparation_reuses_the_composed_requirements(monkeypatch):
    from rangekeeper.execution import planning as implementation

    store, _ = setup()
    specification = spec()
    compose, prepare = implementation.compose, preparation.prepare
    views = []

    def recorded(*args, **kwargs):
        view = compose(*args, **kwargs)
        views.append(view)
        return view

    def reused(view, **kwargs):
        assert views == [view]
        assert view is views[0]
        return prepare(view, **kwargs)

    monkeypatch.setattr(implementation, "compose", recorded)
    monkeypatch.setattr(preparation, "prepare", reused)
    run = execute(store, specification)
    assert run.report.status.solution == "feasible"
    assert len(views) == 1
