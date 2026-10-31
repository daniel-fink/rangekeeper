"""A batch solves in worker processes, with the evidence of a sequential solve (#529)."""

import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from rangekeeper import Specification
from rangekeeper.execution import ExecutionConfig, _parallel, execute, solve
from rangekeeper.execution.backends import PyomoHighs, registry
from rangekeeper.execution.backends import pyomo as pyomo_backend
from rangekeeper.io import MemoryStore
from rangekeeper.quantity import UnitSystem, unit_systems
from rangekeeper.run.documents import Documents
from rangekeeper.shared.errors import ContractError
from tests.execution.test_pipeline import Recording, batch_of, dated

ROOT = Path(__file__).resolve().parents[2]
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# The fields that hold a time.
_TIMES = {
    "started_at",
    "finished_at",
    "at",
    "highs_seconds",
    "solver_time_limit",
    "worker_seconds",
}


@pytest.fixture(autouse=True)
def optional_backend():
    pytest.importorskip("pyomo")
    pytest.importorskip("highspy")


@pytest.fixture
def started(monkeypatch):
    """Let every batch use processes; return the batch workers that start."""
    monkeypatch.setattr(_parallel, "START_SECONDS", 0.0)
    workers = []
    original = _parallel.Worker.start

    def start(command, *, role="solver worker"):
        worker = original(command, role=role)
        if role == "batch worker":
            workers.append(worker)
        return worker

    monkeypatch.setattr(_parallel.Worker, "start", staticmethod(start))
    return workers


def rates(count=6):
    """Return a batch of ``count`` feasible cases, each with its own rate."""
    return dated().cases(
        cases={f"rate_{i}": {"rate": f"{i + 1} % pa"} for i in range(count)}
    )


def leaf(base, **changes):
    """Return a new leaf of ``base`` with changed fields."""
    data = base.to_data()
    data["metadata"] = {**data["metadata"], "id": str(uuid4())}
    return Specification.from_data({**data, **changes})


def mixed():
    """Return a batch with failures that stay with their cases.

    The first two cases solve in the calling process. After them come a case that
    passes its deadline, a case that does not compose, a case with an include, and
    more feasible cases.
    """
    base = dated()
    rate, *others = [item for item in base.to_data()["assignments"]]
    shared = leaf(base, assignments=others, unknowns=[])
    included = leaf(base, assignments=[rate], includes=[str(shared.id)])
    limited = leaf(base, settings={"time_limit": 1e-9})
    conflict = leaf(base, includes=[str(base.id)])
    leaves = (base, leaf(base), limited, conflict, included, leaf(base), leaf(base))
    batch = batch_of(base.model, *leaves)
    return batch, Documents((base.model, shared, *leaves, batch))


def comparable(outcome):
    """Return the documents of an Outcome, without times; UUIDs by first-seen position.

    The ``references`` of a ``constraint_residual`` diagnostic have no fixed order:
    it differs between two runs of the same code (#523).
    """
    positions: dict[str, str] = {}

    def position(match):
        return positions.setdefault(match[0], f"#{len(positions)}")

    def clean(value):
        if isinstance(value, dict):
            return {
                key: clean(child) for key, child in value.items() if key not in _TIMES
            }
        if isinstance(value, list):
            return [clean(child) for child in value if not _is_timing(child)]
        return _UUID.sub(position, value) if isinstance(value, str) else value

    def ordered(value):
        if isinstance(value, dict):
            return {
                key: (
                    sorted(child, key=lambda item: item["target"])
                    if key == "references"
                    else ordered(child)
                )
                for key, child in value.items()
            }
        return [ordered(child) for child in value] if isinstance(value, list) else value

    return [
        clean(
            ordered(
                {
                    "key": item.key,
                    "run": item.run.to_data(),
                    "outputs": [model.to_data() for model in item.outputs],
                }
            )
        )
        for item in outcome.walk()
    ]


def _is_timing(item):
    return isinstance(item, dict) and item.get("code") == "attempt_timing"


def statuses(outcome):
    return [case.status.value for case in outcome.cases]


def test_workers_do_not_change_results_or_evidence(started):
    batch, resolver = mixed()
    alone = solve(
        specification=batch, resolver=resolver, config=ExecutionConfig(workers=1)
    )
    assert started == []
    together = solve(
        specification=batch, resolver=resolver, config=ExecutionConfig(workers=3)
    )
    assert len(started) == 3
    assert comparable(together) == comparable(alone)
    assert statuses(together) == statuses(alone)
    assert statuses(together) == [
        "feasible",
        "feasible",
        "limited",
        "invalid",
        "feasible",
        "feasible",
        "feasible",
    ]
    assert "workers" not in json.dumps(together.run.to_data())


def test_cases_come_back_in_their_original_order(started):
    batch = rates()
    outcome = solve(specification=batch, config=ExecutionConfig(workers=2))
    assert started
    assert [case.key for case in outcome.cases] == [f"rate_{i}" for i in range(6)]
    assert outcome.run.record.spawns == tuple(case.run.id for case in outcome.cases)
    assert [case.run.record.specification for case in outcome.cases] == list(
        batch.record.cases
    )


def test_execute_publishes_from_the_calling_process(started):
    store = Recording()
    outcome = execute(
        specification=rates(), store=store, config=ExecutionConfig(workers=2)
    )
    assert started
    assert [item for item in store.puts if item[0] == "Run"] == [
        ("Run", item.run.id) for item in outcome.walk()
    ]
    for item in outcome.walk():
        assert store.load_run(item.run.id).to_data() == item.run.to_data()


class Reporting(PyomoHighs):
    """The solver, with the process IDs of the worker and its solver in its evidence."""

    def solve(self, *, problem, limits, remaining, options=None):
        result = super().solve(
            problem=problem, limits=limits, remaining=remaining, options=options or {}
        )
        idle = pyomo_backend._workers.idle
        evidence = {
            **result.evidence,
            "worker": os.getpid(),
            "solver": idle.process.pid,
        }
        return replace(result, evidence=evidence)


def evidence_of(outcome):
    for case in outcome.cases:
        for item in case.run.report.diagnostics:
            if item.code == "solver_termination":
                yield item.values


@pytest.mark.skipif(sys.platform == "win32", reason="signal 0 ends a Windows process")
def test_no_process_stays_behind(started):
    outcome = solve(
        specification=rates(),
        config=ExecutionConfig(workers=2, backend=Reporting()),
    )
    assert len(started) == 2
    assert all(worker.process.poll() == 0 for worker in started)
    found = [item for item in evidence_of(outcome) if item["worker"] != os.getpid()]
    assert found
    for item in found:
        for pid in (item["worker"], item["solver"]):
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)


class Ends:
    """A solver that ends the first worker process that calls it."""

    def __init__(self, *, marker, home):
        self.marker, self.home = str(marker), home
        self.solver = PyomoHighs()

    def solve(self, *, problem, limits, remaining, options=None):
        if os.getpid() != self.home:
            try:
                os.close(os.open(self.marker, os.O_CREAT | os.O_EXCL))
            except FileExistsError:
                pass
            else:
                os._exit(9)
        return self.solver.solve(
            problem=problem, limits=limits, remaining=remaining, options=options or {}
        )


def test_a_worker_process_that_ends_loses_only_its_case(started, tmp_path):
    backend = Ends(marker=tmp_path / "ended", home=os.getpid())
    outcome = solve(
        specification=rates(), config=ExecutionConfig(workers=2, backend=backend)
    )
    # The two workers, and the one that replaced the worker that ended.
    assert len(started) == 3
    assert all(worker.process.poll() is not None for worker in started)
    found = statuses(outcome)
    assert sorted(found) == ["failed", *["feasible"] * 5]
    lost = outcome.cases[found.index("failed")].run.report.diagnostics
    assert [item.code for item in lost if item.severity.value == "error"] == [
        "numerical_failure"
    ]
    assert any("batch worker exited 9" in item.message for item in lost)


class Broken:
    """A solver with an error that is not an expected failure, in a worker process."""

    def __init__(self, *, home):
        self.home = home
        self.solver = PyomoHighs()

    def solve(self, *, problem, limits, remaining, options=None):
        if os.getpid() != self.home:
            raise LookupError(f"broken in {os.getpid()}")
        return self.solver.solve(
            problem=problem, limits=limits, remaining=remaining, options=options or {}
        )


def test_an_unexpected_error_in_a_worker_raises_with_its_trace(started):
    with pytest.raises(LookupError, match="broken in") as raised:
        solve(
            specification=rates(),
            config=ExecutionConfig(workers=2, backend=Broken(home=os.getpid())),
        )
    assert any("In a batch worker process" in note for note in raised.value.__notes__)
    assert all(worker.process.poll() is not None for worker in started)


class Delegating:
    """A solver that this module registers while it runs."""

    def __init__(self):
        self.solver = PyomoHighs()

    def solve(self, *, problem, limits, remaining, options=None):
        return self.solver.solve(
            problem=problem, limits=limits, remaining=remaining, options=options or {}
        )


@pytest.fixture
def registered():
    """Register a backend and a unit system in this process only, for one test."""
    units = UnitSystem(definitions=("widget = [widgets]",))
    registry.register(
        name="test-delegating", implementation=Delegating(), fingerprint="stated"
    )
    unit_systems.register(name="test-widgets", implementation=units)
    yield units
    del registry._registered["test-delegating"]
    del unit_systems._registered["test-widgets"]


def test_extensions_of_this_process_reach_each_worker(started, registered):
    batch = rates()
    settings = {"backend": "test-delegating", "units": registered}
    alone = solve(specification=batch, config=ExecutionConfig(workers=1, **settings))
    together = solve(specification=batch, config=ExecutionConfig(workers=2, **settings))
    assert started
    assert comparable(together) == comparable(alone)
    found = {
        (item.name, item.version)
        for case in together.cases
        for item in case.run.report.runtime.implementations
    }
    assert ("rangekeeper.backends:test-delegating", "stated") in found
    assert "rangekeeper.unit_systems:test-widgets" in {name for name, _ in found}


def _refuse():
    raise LookupError("this backend stays in the calling process")


class Refuses(Delegating):
    """A backend that can be written but that no worker process can read."""

    def __reduce__(self):
        return _refuse, ()


def test_a_backend_that_a_worker_cannot_read_stays_here(started):
    with pytest.warns(RuntimeWarning, match="stays in the calling process"):
        outcome = solve(
            specification=rates(), config=ExecutionConfig(workers=2, backend=Refuses())
        )
    assert started
    assert statuses(outcome) == ["feasible"] * 6


def test_a_backend_that_cannot_move_stays_here(started):
    class Local(Delegating):
        """A local class cannot be pickled."""

    with pytest.warns(RuntimeWarning, match="cannot move between processes"):
        outcome = solve(
            specification=rates(), config=ExecutionConfig(workers=2, backend=Local())
        )
    assert started == []
    assert statuses(outcome) == ["feasible"] * 6


def test_a_solve_in_a_worker_process_starts_no_process(started, monkeypatch):
    monkeypatch.setattr(_parallel, "_in_worker", True)
    assert _parallel.worker_count(ExecutionConfig(workers=8)) == 1
    outcome = solve(specification=rates(), config=ExecutionConfig(workers=8))
    assert started == []
    assert statuses(outcome) == ["feasible"] * 6


@pytest.mark.parametrize("count", [1, 2, 3])
def test_a_small_batch_uses_no_process(started, count):
    outcome = solve(specification=rates(count), config=ExecutionConfig(workers=8))
    assert started == []
    assert statuses(outcome) == ["feasible"] * count


def test_one_worker_uses_no_process(started):
    solve(specification=rates(), config=ExecutionConfig(workers=1))
    assert started == []


def test_the_defaults_use_all_cores():
    assert ExecutionConfig().workers is None
    cores = getattr(os, "process_cpu_count", os.cpu_count)()
    assert _parallel.worker_count(ExecutionConfig()) == cores


@pytest.mark.parametrize(
    ("remaining", "seconds", "workers", "expected"),
    [
        (1, 1000.0, 8, False),  # one process gains nothing
        (2, 1.0, 8, False),  # saves 1 s of a 2 s start
        (2, 5.0, 8, True),
        (100, 0.01, 8, False),  # a batch of small cases: 1 s in all
        (100, 0.1, 8, True),
        (100, 1.0, 1, False),
    ],
)
def test_processes_must_repay_their_start(remaining, seconds, workers, expected):
    assert (
        _parallel.gains(remaining=remaining, seconds=seconds, workers=workers)
        is expected
    )


def test_a_script_with_no_guard_runs_once(tmp_path):
    """A worker process does not import the script, unlike multiprocessing's spawn."""
    runs = tmp_path / "runs.txt"
    script = tmp_path / "unguarded.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(ROOT)!r})
            with open({str(runs)!r}, "a") as file:
                file.write("run\\n")
            from rangekeeper.execution import ExecutionConfig, _parallel, solve
            from tests.execution.test_parallel import rates, statuses
            _parallel.START_SECONDS = 0.0
            outcome = solve(specification=rates(), config=ExecutionConfig(workers=2))
            assert statuses(outcome) == ["feasible"] * 6
            """
        )
    )
    done = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    assert "RuntimeWarning" not in done.stderr
    assert runs.read_text() == "run\n"


def test_a_backend_in_main_stays_here_with_a_warning(tmp_path):
    """An object of a script or a notebook has no module that a worker can import."""
    script = tmp_path / "local_backend.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(ROOT)!r})
            from rangekeeper.execution import ExecutionConfig, _parallel, solve
            from tests.execution.test_parallel import Delegating, rates, statuses
            class Local(Delegating):
                pass
            if __name__ == "__main__":
                _parallel.START_SECONDS = 0.0
                config = ExecutionConfig(workers=2, backend=Local())
                outcome = solve(specification=rates(), config=config)
                assert statuses(outcome) == ["feasible"] * 6
            """
        )
    )
    done = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    assert "RuntimeWarning" in done.stderr
    assert "calling process" in done.stderr


def test_workers_is_checked():
    with pytest.raises(ContractError):
        ExecutionConfig(workers=0)
    for wrong in (True, 2.0, "2"):
        with pytest.raises(TypeError):
            ExecutionConfig(workers=wrong)


def test_a_store_resolver_stays_in_the_calling_process(started):
    """A leaf solves with the documents of the case graph; a store does not move."""
    batch, resolver = mixed()
    store = MemoryStore()
    for document in resolver:
        store.put(document)
    outcome = solve(
        specification=store.load_specification(batch.id),
        resolver=store,
        config=ExecutionConfig(workers=2),
    )
    assert started
    assert statuses(outcome)[:3] == ["feasible", "feasible", "limited"]
