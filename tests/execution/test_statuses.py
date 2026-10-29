"""One table maps each expected failure, and one each termination, to a status (#134)."""

import ast
import inspect
import textwrap

import pytest

from rangekeeper.errors import Code
from rangekeeper.execution import attempt, statuses
from rangekeeper.execution.backends import Termination
from rangekeeper.execution.statuses import Reached
from rangekeeper.run import CompletionStatus, Severity, SolutionStatus
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import (
    AttemptDeadlineError,
    BackendUnavailableError,
    ContractError,
    NumericalError,
    UnitError,
    UnsupportedError,
    ValidationError,
)

FAILED, LIMITED = CompletionStatus.FAILED, CompletionStatus.LIMITED
NOT_ASSESSED, UNKNOWN = SolutionStatus.NOT_ASSESSED, SolutionStatus.UNKNOWN
INVALID = ValidationError(ValidationReport((Issue(Code.CONTRACT, "invalid"),)))


@pytest.mark.parametrize(
    "error,reached,completion,solution,code",
    [
        (
            AttemptDeadlineError("late"),
            Reached.NOTHING,
            LIMITED,
            NOT_ASSESSED,
            Code.ATTEMPT_DEADLINE,
        ),
        (
            AttemptDeadlineError("late"),
            Reached.SOLVED,
            LIMITED,
            NOT_ASSESSED,
            Code.ATTEMPT_DEADLINE,
        ),
        (INVALID, Reached.NOTHING, FAILED, NOT_ASSESSED, Code.SPECIFICATION_INVALID),
        (INVALID, Reached.BOUND, FAILED, UNKNOWN, Code.NUMERICAL_REJECTION),
        (UnsupportedError("no"), Reached.BOUND, FAILED, NOT_ASSESSED, None),
        (UnsupportedError("no"), Reached.SOLVED, FAILED, UNKNOWN, None),
        (
            UnitError("unit"),
            Reached.NOTHING,
            FAILED,
            NOT_ASSESSED,
            Code.UNSUPPORTED_CAPABILITY,
        ),
        (
            UnitError("unit"),
            Reached.SOLVED,
            FAILED,
            UNKNOWN,
            Code.UNSUPPORTED_CAPABILITY,
        ),
        (
            BackendUnavailableError("absent"),
            Reached.BOUND,
            FAILED,
            NOT_ASSESSED,
            Code.BACKEND_UNAVAILABLE,
        ),
        (
            NumericalError("nan"),
            Reached.NOTHING,
            FAILED,
            UNKNOWN,
            Code.NUMERICAL_FAILURE,
        ),
        (
            ZeroDivisionError("zero"),
            Reached.SOLVED,
            FAILED,
            UNKNOWN,
            Code.NUMERICAL_FAILURE,
        ),
    ],
)
def test_each_expected_failure_has_one_row(error, reached, completion, solution, code):
    status = statuses.failure(error, reached)
    assert (status.completion, status.solution, status.code) == (
        completion,
        solution,
        code,
    )


def test_a_deadline_is_a_warning_and_other_failures_are_errors():
    assert (
        statuses.failure(AttemptDeadlineError("late"), Reached.NOTHING).severity
        == Severity.WARNING
    )
    assert {item.before.severity for item in statuses.FAILURES[1:]} == {Severity.ERROR}


def test_an_unexpected_error_is_not_in_the_table():
    assert not isinstance(ContractError("bug"), statuses.EXPECTED)
    with pytest.raises(LookupError):
        statuses.failure(ContractError("bug"), Reached.NOTHING)


def test_the_attempt_has_one_except_arm():
    tree = ast.parse(textwrap.dedent(inspect.getsource(attempt.Attempt.execute)))
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert len(handlers) == 1


@pytest.mark.parametrize(
    "termination,completion,solution,verify",
    [
        (Termination.FEASIBLE, CompletionStatus.COMPLETED, UNKNOWN, True),
        (
            Termination.INFEASIBLE,
            CompletionStatus.COMPLETED,
            SolutionStatus.INFEASIBLE,
            False,
        ),
        (Termination.LIMITED, LIMITED, UNKNOWN, True),
        (Termination.FAILED, FAILED, UNKNOWN, False),
        (Termination.UNKNOWN, CompletionStatus.COMPLETED, UNKNOWN, True),
    ],
)
def test_each_termination_has_one_row(termination, completion, solution, verify):
    ending = statuses.TERMINATIONS[termination]
    assert (ending.completion, ending.solution, ending.verify) == (
        completion,
        solution,
        verify,
    )


def test_every_termination_has_a_row():
    assert set(statuses.TERMINATIONS) == set(Termination)


@pytest.mark.parametrize(
    "code,status",
    [
        (Code.SPECIFICATION_INVALID, statuses.Status.INVALID),
        (Code.NUMERICAL_REJECTION, statuses.Status.FAILED),
        (Code.NUMERICAL_FAILURE, statuses.Status.FAILED),
        (Code.BACKEND_UNAVAILABLE, statuses.Status.FAILED),
        (Code.UNSUPPORTED_CAPABILITY, statuses.Status.UNSUPPORTED),
        (Code.ATTEMPT_DEADLINE, statuses.Status.LIMITED),
        # An error's own code, which no row names.
        (Code.NONAFFINE_UNKNOWNS, statuses.Status.UNSUPPORTED),
        (Code.SYMBOL_LIMIT, statuses.Status.UNSUPPORTED),
    ],
)
def test_failed_reads_the_status_of_a_code_from_the_failures_table(code, status):
    assert statuses.failed(code.value) is status


def test_each_failure_row_gives_a_status():
    for item in statuses.FAILURES:
        for conclusion in (item.before, item.after):
            if conclusion is not None:
                assert isinstance(conclusion.status, statuses.Status)
