"""The reusable isolated worker of the pyomo-highs backend (#130).

The worker session is private: ``pyomo._workers`` holds the idle worker of the
process, and ``pyomo._WORKER`` is the script that each new worker runs. Process
reuse, a stall and a crash are not visible through the public API, so these
tests replace the session with a new one, and the script with a small script
that makes a file named by the worker's process ID before it runs the real
worker, stalls or exits. The other tests solve through the public API.
"""

import importlib.util
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path

import pytest

from rangekeeper import Specification
from rangekeeper.errors import Code
from rangekeeper.execution import ExecutionConfig, Limits, build_problem, solve
from rangekeeper.execution.backends import BackendResult, PyomoHighs, Termination
from rangekeeper.execution.backends import pyomo as highs
from rangekeeper.execution.backends._process import Workers
from rangekeeper.run import CompletionStatus, SolutionStatus
from tests.execution.test_execution import EXAMPLES, RENT, data, fresh, setup, spec
from tests.execution.test_stages import bound

REAL = highs._WORKER
# The evidence of a solve that changes from one solve to the next.
TIMINGS = frozenset({"highs_seconds", "worker_seconds", "solver_time_limit"})
RECORD = """import os, runpy
open(os.path.join({log!r}, str(os.getpid())), "w").close()
runpy.run_path({real!r}, run_name="__main__")
"""
STALL = """import os, sys, time
open(os.path.join({log!r}, str(os.getpid())), "w").close()
sys.stdin.readline()
time.sleep(60)
"""
EXIT = """import os, sys
open(os.path.join({log!r}, str(os.getpid())), "w").close()
sys.stdin.readline()
sys.stderr.write("worker failure evidence\\n")
sys.stderr.flush()
os._exit(3)
"""


@pytest.fixture(autouse=True)
def optional_backend():
    if any(importlib.util.find_spec(name) is None for name in ("pyomo", "highspy")):
        pytest.skip("requires the optional execution extra")


@pytest.fixture
def session(monkeypatch):
    """Give the test a new worker session, and close its idle worker after it."""
    workers = Workers(highs._command)
    monkeypatch.setattr(highs, "_workers", workers)
    yield workers
    workers.close()


@pytest.fixture
def log(tmp_path):
    """Return the folder in which each new worker makes a file named by its ID.

    One file for each worker, because appends to one file from two processes
    can overwrite each other on Windows.
    """
    folder = tmp_path / "workers"
    folder.mkdir()
    return folder


def run_as(monkeypatch, *, script: str, log: Path) -> None:
    """Make each new worker of the session run ``script``."""
    path = log.parent / f"worker-{len(list(log.parent.glob('worker-*.py')))}.py"
    path.write_text(script.format(log=str(log), real=str(REAL)))
    monkeypatch.setattr(highs, "_WORKER", path)


def started(log: Path) -> list[int]:
    """Return the process ID of each worker that started."""
    return sorted(int(path.name) for path in log.iterdir())


def running(pid: int) -> bool:
    """Return whether a process with this ID exists."""
    if os.name == "nt":
        # Signal 0 does not test a process on Windows.
        listing = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return str(pid) in listing
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def problem(rent: float = 30000):
    """Return the affine problem of the forward example, with an annual rent."""
    payload = fresh(data("specification-forward"))
    for item in payload["assignments"]:
        if item["target"]["target"] == str(RENT):
            item["quantity"]["magnitude"] = rent
    _, binding = bound(Specification.from_data(payload))
    return build_problem(binding=binding)


def backend_solve(item, *, remaining: float = 30.0) -> BackendResult:
    return PyomoHighs().solve(
        problem=item, limits=Limits(), remaining=remaining, options={}
    )


def comparable(result: BackendResult) -> tuple:
    """Return the parts of a result that do not change with timing."""
    return (
        result.termination,
        dict(result.candidate or {}),
        result.implementations,
        {k: v for k, v in result.evidence.items() if k not in TIMINGS},
        result.diagnostics,
        result.limits,
    )


def recorded(outcome) -> tuple:
    """Return the evidence of an Outcome's Run without its identity and timing."""
    report = outcome.run.report
    diagnostics = tuple(
        (
            d.severity,
            d.code,
            None if d.code == Code.ATTEMPT_TIMING else d.message,
            {k: v for k, v in d.values.items() if k not in TIMINGS}
            if isinstance(d.values, Mapping)
            else d.values,
        )
        for d in report.diagnostics
    )
    return (
        report.status,
        report.runtime.implementations,
        report.runtime.settings,
        diagnostics,
        tuple((step.kind, step.message) for step in report.trace),
        outcome.status,
        outcome.free_unknowns,
    )


def test_the_solves_of_a_session_reuse_one_worker(session, monkeypatch, log):
    run_as(monkeypatch, script=RECORD, log=log)
    first = backend_solve(problem())
    second = backend_solve(problem(31000))
    store, _ = setup()
    outcome = solve(specification=spec(), resolver=store)
    assert first.termination is second.termination is Termination.FEASIBLE
    assert outcome.run.report.status.solution == SolutionStatus.FEASIBLE
    assert len(started(log)) == 1
    assert running(started(log)[0])


def test_the_worker_starts_isolated_from_the_environment(
    session, monkeypatch, tmp_path
):
    """The worker reads no PYTHON* variable and not the current folder (-I)."""
    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "pyomo.py").write_text("raise RuntimeError('planted module')\n")
    monkeypatch.chdir(planted)
    monkeypatch.setenv("PYTHONPATH", str(planted))
    assert highs._command()[1] == "-I"
    assert backend_solve(problem()).termination is Termination.FEASIBLE


def test_evidence_is_the_same_from_a_new_or_a_reused_worker(session):
    store, _ = setup()
    specification = spec()
    store.put(specification)
    new = solve(specification=specification, resolver=store)
    reused = solve(specification=specification, resolver=store)
    assert new.run.id != reused.run.id
    assert recorded(new) == recorded(reused)
    assert new.run.report.status.solution == SolutionStatus.FEASIBLE


def test_results_do_not_depend_on_the_order_of_solves(session):
    problems = (problem(), problem(31000), problem(28500))
    forward = [comparable(backend_solve(item)) for item in problems]
    session.close()
    backward = [comparable(backend_solve(item)) for item in reversed(problems)]
    alone = []
    for item in problems:
        session.close()
        alone.append(comparable(backend_solve(item)))
    assert forward == backward[::-1] == alone
    assert len({tuple(result[1].values()) for result in forward}) == 3


def test_a_solve_past_its_deadline_ends_its_worker(session, monkeypatch, log):
    run_as(monkeypatch, script=STALL, log=log)
    store, _ = setup()
    specification = spec(settings={"time_limit": 1})
    store.put(specification)
    begun = time.monotonic()
    outcome = solve(specification=specification, resolver=store)
    assert time.monotonic() - begun < 5
    assert outcome.run.report.status.completion == CompletionStatus.LIMITED
    assert outcome.run.report.status.solution == SolutionStatus.UNKNOWN
    evidence = next(
        d.values
        for d in outcome.run.report.diagnostics
        if d.code == Code.SOLVER_TERMINATION
    )
    assert evidence["termination_condition"] == "worker_deadline"
    (stalled,) = started(log)
    assert not running(stalled)
    run_as(monkeypatch, script=RECORD, log=log)
    assert backend_solve(problem()).termination is Termination.FEASIBLE
    assert len(started(log)) == 2


def test_a_worker_that_ends_keeps_its_failure_evidence(session, monkeypatch, log):
    run_as(monkeypatch, script=EXIT, log=log)
    store, _ = setup()
    outcome = solve(specification=spec(), resolver=store)
    assert outcome.run.report.status.completion == CompletionStatus.FAILED
    failure = next(
        d for d in outcome.run.report.diagnostics if d.code == Code.NUMERICAL_FAILURE
    )
    assert "solver worker exited 3" in failure.message
    assert "worker failure evidence" in failure.message
    (ended,) = started(log)
    assert not running(ended)
    run_as(monkeypatch, script=RECORD, log=log)
    assert backend_solve(problem()).termination is Termination.FEASIBLE
    assert len(started(log)) == 2


def test_a_worker_that_ended_while_idle_is_replaced(session, monkeypatch, log):
    run_as(monkeypatch, script=RECORD, log=log)
    backend_solve(problem())
    (first,) = started(log)
    os.kill(first, signal.SIGTERM)
    session.idle.process.wait(10)
    assert backend_solve(problem()).termination is Termination.FEASIBLE
    assert len(started(log)) == 2


def test_concurrent_solves_keep_one_idle_worker(session, monkeypatch, log):
    run_as(monkeypatch, script=RECORD, log=log)
    item = problem()
    results: list[BackendResult] = []
    barrier = threading.Barrier(2)

    def work():
        barrier.wait()
        results.append(backend_solve(item))

    threads = [threading.Thread(target=work) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert [result.termination for result in results] == [Termination.FEASIBLE] * 2
    assert comparable(results[0]) == comparable(results[1])
    # The IDs are the interpreters' own: on Windows, a venv's python.exe starts
    # the interpreter as its child, so Popen.pid is another process.
    workers = started(log)
    assert 1 <= len(workers) <= 2
    assert len([pid for pid in workers if running(pid)]) == 1
    assert session.idle is not None and session.idle.usable


def test_workers_close_at_interpreter_exit(tmp_path):
    script = f"""
from pathlib import Path
from rangekeeper import Model, Specification
from rangekeeper.execution import execute
from rangekeeper.execution.backends import pyomo
from rangekeeper.io import MemoryStore, yaml
examples = Path({str(EXAMPLES)!r})
store = MemoryStore()
store.put(yaml.read(path=examples / "model.yaml", kind=Model))
for name in ("specification-common", "specification-composed-forward"):
    store.put(yaml.read(path=examples / (name + ".yaml"), kind=Specification))
run = execute(specification=store.load_specification(
    yaml.read(path=examples / "specification-composed-forward.yaml", kind=Specification).id
), store=store).run
assert run.report.status.solution.value == "feasible", run.report
print(pyomo._workers.idle.process.pid)
"""
    child = subprocess.run(
        [sys.executable, "-W", "always::ResourceWarning", "-c", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    assert "ResourceWarning" not in child.stderr, child.stderr
    assert not running(int(child.stdout.split()[-1]))


def test_the_request_carries_sparse_rows():
    """The protocol is private; #130 requires that only nonzero terms cross it."""
    item = problem()
    scales = tuple(PyomoHighs._scale(row) for row in item.rows)
    request = highs._request(problem=item, scales=scales, limits=Limits(), options={})
    index = {id: position for position, id in enumerate(item.variables)}
    assert request["size"] == len(item.variables)
    for row, sent, scale in zip(item.rows, request["rows"], scales, strict=True):
        assert sent["terms"] == sorted(
            [index[id], value / scale]
            for id, value in row.residual.coefficients.items()
        )
        assert all(value != 0 for _, value in sent["terms"])


def test_a_config_with_a_new_backend_uses_the_session(session, monkeypatch, log):
    run_as(monkeypatch, script=RECORD, log=log)
    store, _ = setup()
    for _ in range(2):
        outcome = solve(
            specification=spec(),
            resolver=store,
            config=ExecutionConfig(backend=PyomoHighs()),
        )
        assert outcome.run.report.status.solution == SolutionStatus.FEASIBLE
    assert len(started(log)) == 1
