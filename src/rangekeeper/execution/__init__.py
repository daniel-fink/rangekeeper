"""Affine scalar execution; numerical backends remain optional and process-local.

Execution runs as typed stages (ADR-013). Each stage is a function that writes
to no store:

1. ``resolve_cases`` resolves the case graph and composes each leaf.
2. ``validate`` validates one composition against its input Model.
3. ``bind_roles`` gives each value its role.
4. ``build_problem`` makes the ``AffineProblem``.
5. A ``Backend`` solves the problem and returns a ``backends.BackendResult``,
   whose ``backends.Termination`` is the only status that generic code reads.
6. ``make_candidate`` writes the solved values into a candidate Model.
7. ``verify`` checks the candidate against the original mathematics.
8. ``assemble`` makes the ``Outcome`` of a leaf, and ``assemble_batch`` the
   Outcome of a batch. Neither validates: ``rk.run.validate`` with an
   ``Overlay`` of the unstored outputs and Runs validates the Run.

An ``Outcome`` reads its result by key, ``outcome["land_cost"]``. Its
``status`` is a ``Status``, and ``raise_for_status()`` raises when the solve
found no determined result. A batch Outcome gives the distribution of one value
across its cases: a ``Distribution`` of a scalar value, or a
``DateDistribution`` of a date value; ``mean()`` gives the ``Mean`` of its
scalar values. ``compare`` compares two or more Outcomes: side by side
(``SideBySide``), or paired with a baseline by case key (``Paired``).

``solve`` runs the stages for each case and writes nothing. ``execute`` solves,
then publishes the outputs and the Runs to a store.
``ExecutionConfig`` holds the backend, unit system, limits, tolerances and
backend options, with one source of defaults. ``DecisionResult`` names the
result of one check of a decision rule.
"""

from rangekeeper.execution.acceptance import Tolerances, Verification, verify
from rangekeeper.execution.analysis import Analysis
from rangekeeper.execution.assembly import Overlay, assemble, assemble_batch
from rangekeeper.execution.comparison import Pair, Paired, SideBySide, compare
from rangekeeper.execution.compiler import AffineProblem, Relation, Row, build_problem
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.distribution import DateDistribution, Distribution, Mean
from rangekeeper.execution.errors import OutcomeError
from rangekeeper.execution.outcome import Evidence, Outcome
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
from rangekeeper.execution.rule.result import DecisionResult
from rangekeeper.execution.settings import Limits
from rangekeeper.execution.status import Status

__all__ = [
    "AffineProblem",
    "Analysis",
    "Assertion",
    "Binding",
    "Cases",
    "DateDistribution",
    "DecisionResult",
    "Distribution",
    "Evidence",
    "ExecutionConfig",
    "Limits",
    "Mean",
    "Outcome",
    "OutcomeError",
    "Overlay",
    "Pair",
    "Paired",
    "Relation",
    "Row",
    "SideBySide",
    "Status",
    "Tolerances",
    "Validation",
    "Verification",
    "assemble",
    "assemble_batch",
    "bind_roles",
    "build_problem",
    "compare",
    "execute",
    "make_candidate",
    "resolve_cases",
    "solve",
    "validate",
    "verify",
]
