"""Affine scalar execution; numerical backends remain optional and process-local.

Execution runs as typed stages (ADR-013). Each stage is a function that writes
to no store:

1. ``resolve_cases`` resolves the case graph and composes each leaf.
2. ``validate`` validates one composition against its input Model.
3. ``bind_roles`` gives each value its role.
4. ``build_problem`` makes the ``AffineProblem``.
5. A ``Backend`` solves the problem.
6. ``make_candidate`` writes the solved values into a candidate Model.
7. ``verify`` checks the candidate against the original mathematics.
8. ``assemble`` makes the ``Outcome`` of a leaf, and ``assemble_batch`` the
   Outcome of a batch.

``solve`` runs the stages for each case and writes nothing. ``execute`` solves,
then publishes the outputs and the Runs to a store.
``ExecutionConfig`` holds the backend, unit system, limits, tolerances and
backend options, with one source of defaults.
"""

from rangekeeper.execution.acceptance import Tolerances, Verification, verify
from rangekeeper.execution.assembly import assemble, assemble_batch
from rangekeeper.execution.compiler import AffineProblem, build_problem
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.outcome import Outcome
from rangekeeper.execution.pipeline import execute, solve
from rangekeeper.execution.planning import Cases, resolve_cases
from rangekeeper.execution.preparation import (
    Assertion,
    Binding,
    Validation,
    bind_roles,
    validate,
)
from rangekeeper.execution.publication import make_candidate
from rangekeeper.execution.settings import Limits

__all__ = [
    "AffineProblem",
    "Assertion",
    "Binding",
    "Cases",
    "ExecutionConfig",
    "Limits",
    "Outcome",
    "Tolerances",
    "Validation",
    "Verification",
    "assemble",
    "assemble_batch",
    "bind_roles",
    "build_problem",
    "execute",
    "make_candidate",
    "resolve_cases",
    "solve",
    "validate",
    "verify",
]
