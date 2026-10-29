"""The backend contract: AffineProblem in, BackendResult and Termination out (#129)."""

import subprocess
from uuid import uuid4

import pytest

from rangekeeper.errors import Code
from rangekeeper.execution import (
    Analysis,
    ExecutionConfig,
    Limits,
    Relation,
    build_problem,
    execute,
)
from rangekeeper.execution.analysis import equality_rank
from rangekeeper.execution.backends import BackendResult, PyomoHighs, Termination
from rangekeeper.execution.backends import pyomo as highs
from rangekeeper.run import CompletionStatus, SolutionStatus
from rangekeeper.shared.errors import UnsupportedError
from tests.execution.test_execution import (
    CAPITAL,
    NOI,
    binary,
    data,
    formulation,
    fresh,
    literal,
    reference,
    setup,
    spec,
)
from tests.execution.test_stages import bound

A, B, C = uuid4(), uuid4(), uuid4()


@pytest.mark.parametrize(
    "rows,rank",
    [
        ([], 0),
        ([{A: 1.0}], 1),
        ([{A: 1.0, B: 1.0}, {A: 2.0, B: 2.0}], 1),
        ([{A: 1.0, B: 1.0}, {A: 1.0, B: -1.0}], 2),
        ([{A: 1e6, B: 1.0}, {A: 1.0, B: 1e-6}], 1),
        ([{A: 1.0, B: 2.0, C: 3.0}, {B: 1.0}, {A: 1.0, B: 3.0, C: 3.0}], 2),
        ([{A: 0.0}], 0),
    ],
)
def test_equality_rank_needs_no_numpy(rows, rank):
    assert equality_rank(rows, 3) == rank


def test_build_problem_analyses_rank_free_variables_and_bounds():
    _, binding = bound()
    problem = build_problem(binding)
    assert problem.variables == binding.unknowns
    assert problem.analysis == Analysis(
        rank=2, unknown_count=2, free=(), has_bounds=False
    )
    assert not problem.analysis.underdetermined
    assert problem.equalities == problem.rows and problem.bounds == ()
    assert all(isinstance(row.relation, Relation) for row in problem.rows)
    assert not hasattr(problem.rows[0], "scale")


def test_a_free_variable_and_a_bound_are_in_the_analysis():
    payload = fresh(data("specification-forward"))
    payload["formulations"] = [
        formulation(binary("less_than_or_equal", reference(CAPITAL), literal(2e7)))
    ]
    _, binding = bound(spec_from(payload))
    problem = build_problem(binding)
    assert problem.analysis.has_bounds
    assert len(problem.bounds) == 1
    assert problem.analysis.free == ()


def spec_from(payload):
    from rangekeeper import Specification

    return Specification.from_data(payload)


def test_backend_results_carry_a_termination_not_a_backend_word():
    with pytest.raises(TypeError):
        BackendResult("optimal")  # type: ignore[arg-type]
    assert {item.value for item in Termination} == {
        "feasible",
        "infeasible",
        "limited",
        "failed",
        "unknown",
    }


def test_generic_code_reads_no_backend_words_in_the_evidence():
    class Claims:
        def solve(self, problem, **kwargs):
            return BackendResult(
                Termination.UNKNOWN,
                evidence={"termination_condition": "provenInfeasible"},
            )

    store, _ = setup()
    run = execute(spec(), store, config=ExecutionConfig(backend=Claims())).run
    assert run.report.status.completion == CompletionStatus.COMPLETED
    assert run.report.status.solution == SolutionStatus.UNKNOWN
    evidence = next(
        d.values for d in run.report.diagnostics if d.code == Code.SOLVER_TERMINATION
    )
    assert evidence["termination"] == "unknown"
    assert evidence["termination_condition"] == "provenInfeasible"


def test_an_infeasible_termination_is_completed_and_infeasible():
    class Proves:
        def solve(self, problem, **kwargs):
            return BackendResult(Termination.INFEASIBLE)

    store, _ = setup()
    run = execute(spec(), store, config=ExecutionConfig(backend=Proves())).run
    assert run.report.status.completion == CompletionStatus.COMPLETED
    assert run.report.status.solution == SolutionStatus.INFEASIBLE


def test_underdetermined_analysis_comes_from_rk_not_the_backend():
    payload = fresh(data("specification-forward"))
    rent = next(
        a for a in payload["assignments"] if a["quantity"]["units"].startswith("AUD/")
    )
    payload["assignments"].remove(rent)
    payload["unknowns"].append({"target": rent["target"]["target"]})
    _, binding = bound(spec_from(payload))
    analysis = build_problem(binding).analysis
    assert analysis.underdetermined
    assert (analysis.rank, analysis.unknown_count, analysis.free) == (2, 3, ())


def no_process(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the backend started a process")

    monkeypatch.setattr(subprocess, "run", forbidden)


def test_the_highs_iteration_clamp_lives_in_the_backend(monkeypatch):
    no_process(monkeypatch)
    _, binding = bound()
    problem = build_problem(binding)
    result = PyomoHighs().solve(
        problem,
        limits=Limits(iteration_limit=highs.ITERATION_MAXIMUM + 1),
        remaining=0,
        options={},
    )
    assert result.termination is Termination.LIMITED
    assert result.limits is None
    clamp = next(d for d in result.diagnostics if d.code == Code.SETTINGS_ADJUSTED)
    assert clamp.values["effective"] == highs.ITERATION_MAXIMUM
    scaling = next(d for d in result.diagnostics if d.code == Code.SOLVER_SCALING)
    assert len(scaling.values["rows"]) == len(problem.rows)


def test_the_highs_scaling_range_lives_in_the_backend(monkeypatch):
    no_process(monkeypatch)
    payload = fresh(data("specification-forward"))
    payload["formulations"] = [
        formulation(
            binary(
                "equal",
                binary(
                    "add",
                    reference(CAPITAL),
                    binary("multiply", literal(1e-13, "year"), reference(NOI)),
                ),
                literal(11000000),
            )
        )
    ]
    specification = spec_from(payload)
    _, binding = bound(specification)
    problem = build_problem(binding)  # rk accepts the row
    with pytest.raises(UnsupportedError, match="HiGHS") as error:
        PyomoHighs().solve(problem, limits=Limits(), remaining=1, options={})
    assert error.value.document == specification.id
