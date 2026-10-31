"""Solve the leaf cases of a batch in the calling process or in worker processes.

ADR-013 gives the design. Each worker process is a new interpreter, on every
platform, with the import path of the caller. It does not import the caller's
``__main__``. It solves one leaf for each request and returns the records of
the result. Each thread of a ``_Pool`` drives one worker process.

The first leaves always solve in the calling process. They show how long a leaf
takes, and ``gains`` then decides whether worker processes repay their start.
Where a leaf solves changes only its times: its result is a Run with the same
content, so the decision cannot change the evidence.
"""

import json
import os
import sys
import threading
import time
import traceback
import warnings
from collections import deque
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from rangekeeper import profile
from rangekeeper.execution import _boundary
from rangekeeper.execution.attempt import Attempt
from rangekeeper.execution.backends import Backend, registry
from rangekeeper.execution.backends._process import Worker
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.execution.errors import NumericalError
from rangekeeper.execution.outcome import Outcome
from rangekeeper.execution.planning import Cases
from rangekeeper.market.paths import Paths
from rangekeeper.model import Model
from rangekeeper.quantity import Quantity, unit_systems
from rangekeeper.run.documents import Documents
from rangekeeper.shared.errors import ValidationError
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.shared.registry import Registry
from rangekeeper.specification import Composition, Specification
from rangekeeper.specification.rule._declaration import parameters_of, query_of
from rangekeeper.specification.rule._query import RuleQuery

# The wall-clock seconds that worker processes cost before they repay anything:
# 0.4 s to import Rangekeeper and read the Setup, and 1.4 s more for the first
# solve of a process than for its later solves. ADR-013 has the measurements.
START_SECONDS = 2.0
# The extension points that a stage reads while it solves a leaf.
_EXTENSIONS: tuple[Registry[Any], ...] = (unit_systems, profile.profiles)
# ``Attempt`` owns the deadline of a case, in the worker process as in this one.
_NO_DEADLINE = threading.TIMEOUT_MAX / 2
_BOOT = (
    "import json, sys; sys.path[:] = json.loads(sys.argv[1]); "
    "from rangekeeper.execution._batch_worker import main; main()"
)

# Whether this process is a batch worker: a solve in it starts no process.
_in_worker = False


def enter_worker() -> None:
    """Mark this process as a batch worker, so that each solve in it stays in it."""
    global _in_worker  # noqa: PLW0603 - one fact about this process
    _in_worker = True


def worker_count(config: ExecutionConfig) -> int:
    """Return the number of processes that may solve the leaves of a batch."""
    if _in_worker:
        return 1
    if config.workers is not None:
        return config.workers
    # os.process_cpu_count (Python 3.13) respects the affinity of this process.
    cores = getattr(os, "process_cpu_count", os.cpu_count)()
    return cores or 1


def gains(*, remaining: int, seconds: float, workers: int) -> bool:
    """Return whether worker processes solve ``remaining`` leaves sooner.

    ``seconds`` is the time of one leaf. The time saved must exceed the time
    that the processes take to start.
    """
    count = min(workers, remaining)
    return remaining * seconds * (1 - 1 / count) > START_SECONDS


@dataclass(frozen=True, kw_only=True)
class Solved:
    """The Outcome of one leaf and the scope that validated it, or None."""

    outcome: Outcome
    scope: object = None


@dataclass(frozen=True, kw_only=True)
class Setup:
    """What each worker process holds for all the leaves of one batch.

    ``solver`` holds the arguments that register the backend in the worker, or
    None for an unregistered backend. ``extensions`` holds, for each point of
    ``_EXTENSIONS``, the arguments that remake each of its registrations.
    """

    config: ExecutionConfig
    backend: Backend
    solver: dict[str, Any] | None
    extensions: tuple[tuple[dict[str, Any], ...], ...]
    models: tuple[Model, ...]
    paths: tuple[Paths, ...]


@dataclass(frozen=True, kw_only=True)
class Raised:
    """An error that is not an expected failure, as a worker process caught it."""

    error: Exception
    trace: str


@dataclass(frozen=True, kw_only=True)
class Refused:
    """The reason that a worker process cannot solve the leaves of this batch."""

    reason: str


@dataclass(frozen=True, kw_only=True)
class Session:
    """The state of a worker process after its Setup."""

    config: ExecutionConfig
    backend: Backend
    resolver: DocumentResolver


def solve_leaf(
    specification: Specification,
    *,
    view: Composition | ValidationError,
    config: ExecutionConfig,
    backend: Backend,
    resolver: DocumentResolver,
) -> Solved:
    """Run the stages of one leaf; the same code in any process."""
    attempt = Attempt(
        specification,
        view,
        config=config,
        backend=backend,
        resolver=resolver,
        rules=_rules(view),
        parameters=_parameters(view),
    )
    outcome = attempt.execute()
    validation = attempt.validation
    if validation is not None and validation.report.valid and validation._scope:
        return Solved(outcome=outcome, scope=validation._scope)
    return Solved(outcome=outcome)


def _rules(view: Composition | ValidationError) -> tuple[RuleQuery, ...]:
    """Return what the rule engine reads from the rules of a leaf, in their order."""
    if isinstance(view, ValidationError):
        return ()
    return tuple(query_of(item) for item in view.requirements.rules or ())


def _parameters(view: Composition | ValidationError) -> dict[str, Quantity]:
    """Return the parameters that the rules of a leaf read, by key."""
    if isinstance(view, ValidationError):
        return {}
    return parameters_of(view.requirements)


def start_session(setup: Setup) -> Session:
    """Register the extensions of a Setup in this process, and return its Session."""
    for point, arguments in zip(_EXTENSIONS, setup.extensions, strict=True):
        for item in arguments:
            point.register(**item, replace=True)
    if setup.solver is not None:
        registry.register(**setup.solver, replace=True)
    return Session(
        config=setup.config,
        backend=setup.backend,
        resolver=Documents((*setup.models, *setup.paths)),
    )


def solve_leaves(
    *,
    leaves: Sequence[Specification],
    cases: Cases,
    config: ExecutionConfig,
    backend: Backend,
) -> list[Solved]:
    """Solve each leaf, and return the results in the order of ``leaves``.

    The first leaf of a process also pays for its one-off costs, so its time
    decides nothing. After that, each leaf's time decides whether the rest move
    to worker processes.
    """
    workers = worker_count(config)
    solved: list[Solved] = []
    for position, leaf in enumerate(leaves):
        started = time.monotonic()
        solved.append(_here(leaf, cases=cases, config=config, backend=backend))
        remaining = len(leaves) - position - 1
        if (
            position >= 1
            and remaining
            and workers > 1
            and gains(
                remaining=remaining,
                seconds=time.monotonic() - started,
                workers=workers,
            )
        ):
            rest = leaves[position + 1 :]
            return [
                *solved,
                *_elsewhere(rest, cases=cases, config=config, backend=backend),
            ]
    return solved


def _here(
    leaf: Specification,
    *,
    cases: Cases,
    config: ExecutionConfig,
    backend: Backend,
) -> Solved:
    return solve_leaf(
        leaf, view=_view(leaf, cases), config=config, backend=backend, resolver=cases
    )


def _view(leaf: Specification, cases: Cases) -> Composition | ValidationError:
    return cases.failures.get(leaf.id) or cases.compositions[leaf.id]


def _elsewhere(
    leaves: Sequence[Specification],
    *,
    cases: Cases,
    config: ExecutionConfig,
    backend: Backend,
) -> list[Solved]:
    """Solve leaves in worker processes; the calling process solves what they can't."""
    try:
        setup = _boundary.encode(_setup(cases=cases, config=config, backend=backend))
    except Exception as error:  # Pickling runs the code of an extension.
        _warn_fallback(f"its extensions cannot move between processes: {error}")
        return [
            _here(leaf, cases=cases, config=config, backend=backend) for leaf in leaves
        ]
    count = min(worker_count(config), len(leaves))
    pool = _Pool(setup=setup, leaves=leaves, cases=cases)
    replies = pool.run(count)
    if pool.refused is not None and len(replies) < len(leaves):
        _warn_fallback(f"a worker process could not take the batch: {pool.refused}")
    solved: list[Solved] = []
    for index, leaf in enumerate(leaves):
        reply = replies.get(index)
        if isinstance(reply, Raised):
            reply.error.add_note(f"In a batch worker process:\n{reply.trace}")
            raise reply.error
        if isinstance(reply, NumericalError):
            solved.append(
                _lost(leaf, cases=cases, config=config, backend=backend, error=reply)
            )
        elif reply is None:
            solved.append(_here(leaf, cases=cases, config=config, backend=backend))
        else:
            solved.append(reply)
    return solved


def _setup(*, cases: Cases, config: ExecutionConfig, backend: Backend) -> Setup:
    description = registry.describe(backend)
    solver = None
    if description.registered:
        # The fingerprint that the evidence of this process records.
        solver = {
            "name": description.name,
            "implementation": backend,
            "fingerprint": description.fingerprint,
        }
    return Setup(
        config=config,
        backend=backend,
        solver=solver,
        extensions=tuple(
            tuple(item.arguments for item in point.registrations())
            for point in _EXTENSIONS
        ),
        models=tuple(cases.models.values()),
        paths=tuple(cases.paths.values()),
    )


def _warn_fallback(reason: str) -> None:
    warnings.warn(
        "this batch solves in the calling process, with the same results, because "
        f"{reason}. ExecutionConfig(workers=1) chooses this and ends this warning.",
        RuntimeWarning,
        stacklevel=2,
    )


def _lost(
    leaf: Specification,
    *,
    cases: Cases,
    config: ExecutionConfig,
    backend: Backend,
    error: NumericalError,
) -> Solved:
    """Return the failed Run of a leaf whose worker process ended."""
    attempt = Attempt(
        leaf, _view(leaf, cases), config=config, backend=backend, resolver=cases
    )
    attempt.fail(error)
    return Solved(outcome=attempt.finish())


def _command() -> tuple[str, ...]:
    """Return the command that starts a batch worker process.

    A new interpreter is the spawn start method: nothing is inherited but the
    environment and the import path. ``multiprocessing`` is not used, because
    its spawn imports the caller's ``__main__`` again: in a script with no
    ``if __name__ == "__main__"`` guard, that solves the whole batch again in
    each process.
    """
    path = [item for item in sys.path if isinstance(item, str)]
    return (sys.executable, "-c", _BOOT, json.dumps(path))


class _Pool:
    """Worker processes that solve leaves in order; each one has one thread.

    Replies are by position in ``leaves``: a Solved, a Raised, or a
    NumericalError for a leaf whose process ended. A position with no reply was
    not solved. A Raised stops the leaves that have not started. They all come
    after it, because each leaf starts in order, so the first Raised by position
    is the error that a sequential solve raises.
    """

    def __init__(
        self,
        *,
        setup: str,
        leaves: Sequence[Specification],
        cases: Cases,
    ) -> None:
        self.setup, self.leaves, self.cases = setup, leaves, cases
        self.pending = deque(range(len(leaves)))
        self.replies: dict[int, Solved | Raised | NumericalError] = {}
        self.refused: str | None = None
        self.running: set[Worker] = set()
        self.lock = threading.Lock()

    def run(self, count: int) -> dict[int, Solved | Raised | NumericalError]:
        """Solve leaves with ``count`` processes; end each process, whatever happens."""
        threads = ThreadPoolExecutor(count, thread_name_prefix="rangekeeper-batch")
        try:
            for future in [threads.submit(self._drive) for _ in range(count)]:
                future.result()
        except BaseException:
            self._abort()
            raise
        finally:
            threads.shutdown()
        return self.replies

    def _drive(self) -> None:
        """Solve leaves in one process; replace the process when it ends."""
        worker = self._start()
        while worker is not None:
            index = self._next()
            if index is None:
                self._close(worker)
                return
            try:
                reply: Solved | Raised | NumericalError = _exchange(
                    worker, _task(self.leaves[index], self.cases)
                )
            except NumericalError as error:
                reply = NumericalError(
                    f"The worker process of this case ended; other cases go on. {error}"
                )
                self._forget(worker)
                worker = self._start() if self.pending else None
            self.replies[index] = reply
            if isinstance(reply, Raised):
                self.pending.clear()

    def _next(self) -> int | None:
        try:
            return self.pending.popleft()
        except IndexError:
            return None

    def _start(self) -> Worker | None:
        """Start a worker process with its Setup, or return None and say why."""
        try:
            worker = Worker.start(_command(), role="batch worker")
        except OSError as error:
            self.refused = str(error)
            return None
        with self.lock:
            self.running.add(worker)
        try:
            reply = _exchange(worker, self.setup)
        except NumericalError as error:
            self.refused = str(error)
            self._forget(worker)
            return None
        if isinstance(reply, Refused):
            self.refused = reply.reason
            self._close(worker)
            return None
        return worker

    def _close(self, worker: Worker) -> None:
        self._forget(worker)
        worker.close()

    def _forget(self, worker: Worker) -> None:
        with self.lock:
            self.running.discard(worker)

    def _abort(self) -> None:
        """End every process, after an interruption of the calling process."""
        self.pending.clear()
        with self.lock:
            running, self.running = self.running, set()
        for worker in running:
            worker.end()


def _task(leaf: Specification, cases: Cases) -> str:
    return _boundary.encode((leaf, _view(leaf, cases)))


def _exchange(worker: Worker, line: str) -> Any:
    """Return the decoded reply to one request; NumericalError when the worker ends."""
    try:
        reply = worker.request(line, deadline=time.monotonic() + _NO_DEADLINE)
    except ValueError as error:
        # ``_abort`` closed the worker while it answered.
        raise NumericalError(f"batch worker ended: {error}") from error
    assert reply is not None, "a request with no deadline returns its reply"
    return _boundary.decode(reply)


def raised(error: Exception) -> Raised:
    """Return a Raised that survives the trip to the calling process."""
    trace = "".join(traceback.format_exception(error))
    try:
        _boundary.decode(_boundary.encode(error))
    except Exception:  # Any exception class can fail to pickle, in its own way.
        return Raised(error=NumericalError(trace), trace=trace)
    return Raised(error=error, trace=trace)
