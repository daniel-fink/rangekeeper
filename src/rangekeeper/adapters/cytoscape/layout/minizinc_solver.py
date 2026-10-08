"""Optional MiniZinc/CP-SAT comparison backend; temporary files only.

Each lexicographic phase is compiled separately. The whole budget includes data
preparation, compilation and solving. Complete streamed incumbents survive a
process timeout; every returned incumbent passes independent arithmetic checks.
"""

from rangekeeper.adapters.cytoscape.layout.result import (
    ResultMode,
    ResultStatus,
    StrictStatus,
)
import json
import os
import shutil
import signal
import subprocess
from copy import deepcopy
from dataclasses import asdict
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from rangekeeper.adapters.cytoscape.layout.check import assess
from rangekeeper.adapters.cytoscape.layout.model import Problem, Rect
from rangekeeper.adapters.cytoscape.layout.minizinc_data import encode
from rangekeeper.adapters.cytoscape.layout.reduction import collision_pairs
from rangekeeper.adapters.cytoscape.layout.result import Result

SCORES = (
    "false_enclosures",
    "grid_displacement",
    "extent",
    "assembly_extent",
    "grid_score",
    "direction_score",
    "order_score",
    "similarity_score",
    "style_cost",
)


def toolchain(executable=None):
    """Inspect the requested executable; never silently choose another solver."""
    binary = executable or os.environ.get("RK_MINIZINC") or shutil.which("minizinc")
    if not binary:
        raise RuntimeError(
            "Set RK_MINIZINC to a MiniZinc executable with CP-SAT installed"
        )
    binary = str(Path(binary).resolve())
    version = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, check=True, timeout=10
    ).stdout.strip()
    solvers = json.loads(
        subprocess.run(
            [binary, "--solvers-json"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout
    )
    backend = next((s for s in solvers if s["id"] == "cp-sat"), None)
    if backend is None:
        raise RuntimeError("Requested MiniZinc installation has no CP-SAT backend")
    return {
        "executable": binary,
        "compiler": version,
        "backend": backend["name"],
        "version": backend["version"],
        "threads": 1,
        "random_seed": 0,
    }


def _invoke(binary, model, data, directory, deadline):
    datafile = Path(directory) / "data.json"
    datafile.write_text(json.dumps(data))
    remaining = deadline - monotonic()
    if remaining <= 0:
        return [], "UNKNOWN", [], "Time budget exhausted"
    # Leave a small part of the same wall budget for native shutdown/statistics.
    # Otherwise the outer watchdog can kill buffered output just before it flushes.
    command = [
        binary,
        "--solver",
        "cp-sat",
        "-p",
        "1",
        "-r",
        "0",
        "-f",
        "--json-stream",
        "--output-time",
        "--statistics",
        "--intermediate-solutions",
        "--time-limit",
        str(max(1, int((remaining - min(0.1, remaining / 10)) * 1000))),
    ]
    if data["hinted"] and not data["fixed"]:
        command.extend(["--params", "cp_model_presolve:false"])
    command.extend([str(model), str(datafile)])
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=remaining)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    solutions, statistics, errors = [], [], []
    state = "UNKNOWN"
    for line in stdout.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            if timed_out:
                continue
            raise RuntimeError("Invalid MiniZinc JSON stream") from None
        kind = message.get("type")
        if kind == "solution":
            solution = json.loads(message["output"]["default"])
            solution["reported_seconds"] = message["time"] / 1000
            solutions.append(solution)
        elif kind == "status":
            state = message["status"]
        elif kind == "statistics":
            statistics.append(message["statistics"])
        elif kind == "error":
            errors.append(message)
    if errors or (process.returncode and not timed_out):
        raise RuntimeError(f"MiniZinc execution failed: {errors or stderr}")
    if state not in {"UNKNOWN", "SATISFIED", "OPTIMAL_SOLUTION", "UNSATISFIABLE"}:
        raise RuntimeError(f"Unexpected MiniZinc status: {state}")
    return (
        solutions,
        state,
        statistics,
        "Time budget exhausted" if timed_out or state == "UNKNOWN" else "",
    )


def solve(
    problem: Problem,
    *,
    time_limit=10,
    optimize=True,
    allow_relaxed=False,
    initial=None,
    executable=None,
    neighborhood: tuple[str, ...] | None = None,
) -> Result:
    if not isfinite(time_limit) or time_limit <= 0:
        raise ValueError("time_limit must be positive and finite")
    if initial is not None:
        if initial.problem_fingerprint != problem.fingerprint:
            raise ValueError("Initial geometry must match the problem")
        findings, initial_measurements = assess(
            problem, initial.rectangles, initial.grids
        )
        if findings:
            raise ValueError(
                "Initial geometry must match the problem and pass strict checking"
            )
    if neighborhood is not None:
        known = {n.id for n in problem.nodes} | {a.id for a in problem.assemblies}
        if initial is None or not neighborhood or not set(neighborhood) <= known:
            raise ValueError(
                "A neighborhood needs a checked seed and known movable objects"
            )
    # Tool discovery is separate from the per-problem budget, recorded in metadata.
    info = toolchain(executable)
    start = monotonic()
    deadline = start + time_limit
    data, objects, groups = encode(problem, initial)
    result = Result(
        ResultStatus.UNKNOWN,
        StrictStatus.UNKNOWN,
        solver_version=f"{info['compiler']}; {info['backend']} {info['version']}",
        problem_fingerprint=problem.fingerprint,
    )
    if neighborhood is not None:
        movable = set(neighborhood)
        data["neighborhood"] = True
        data["free_object"] = [o.id in movable for o in objects]
        data["free_grid"] = [
            a.id in movable or bool(movable.intersection(a.members)) for a in groups
        ]
        result.search_scope = {
            "mode": "neighborhood",
            "movable_objects": sorted(movable),
        }
    result.build_seconds = monotonic() - start
    indices = [1, 9, 4] if problem.weights else [1, 2, 3, 4]
    model = Path(__file__).with_name("assembly.mzn")

    def accept(solution, phase_start):
        rectangles = {
            o.id: Rect(
                solution["x"][k], solution["y"][k], solution["w"][k], solution["h"][k]
            )
            for k, o in enumerate(objects)
        }
        grids = {
            a.id: {
                "x": solution["gx"][k],
                "y": solution["gy"][k],
                "columns": solution["cols"][k],
            }
            for k, a in enumerate(groups)
            if a.members
        }
        if problem.weights:
            for g, a in enumerate(groups, 1):
                if a.members:
                    grids[a.id]["slots"] = {
                        objects[i - 1].id: solution["slot"][k]
                        for k, (group, i) in enumerate(zip(data["mg"], data["mo"]))
                        if group == g
                    }
        findings, measured = assess(problem, rectangles, grids)
        if any(
            f.code != "exclusion" or result.mode == ResultMode.STRICT for f in findings
        ):
            raise RuntimeError(
                f"Solver result failed independent geometry check: {findings}"
            )
        for i, name in enumerate(SCORES):
            if name in measured and solution["scores"][i] != measured[name]:
                raise RuntimeError(f"Solver/checker objective disagreement: {name}")
        result.rectangles = rectangles
        result.grids = grids
        result.measurements = measured
        result.findings = [asdict(f) for f in findings]
        result.status = ResultStatus.FEASIBLE
        result.incumbent_source = "solver"
        # Keep subsequent phase hints consistent with proved earlier objectives.
        for key, column in (
            ("sx", "x"),
            ("sy", "y"),
            ("sw", "w"),
            ("sh", "h"),
            ("sgx", "gx"),
            ("sgy", "gy"),
            ("sc", "cols"),
            ("ss", "slot"),
        ):
            data[key] = solution[column]
        if result.first_solution_seconds is None:
            result.first_solution_seconds = (
                phase_start - start + solution["reported_seconds"]
            )

    with TemporaryDirectory(prefix="rk-minizinc-") as directory:

        def run():
            phase_start = monotonic()
            solutions, state, stats, reason = _invoke(
                info["executable"], model, data, directory, deadline
            )
            result.solver_statistics.append(
                {
                    "phase": data["phase"],
                    "fixed_seed": data["fixed"],
                    "presolve": not data["hinted"] or data["fixed"],
                    "status": state,
                    "statistics": stats,
                    "wall_seconds": monotonic() - phase_start,
                    "compilation_reported": any("flatTime" in s for s in stats),
                }
            )
            result.build_seconds += sum(float(s.get("flatTime", 0)) for s in stats)
            if reason:
                result.reason = reason
            for solution in solutions:
                accept(solution, phase_start)
            return state

        if initial is not None and optimize:
            # Arithmetic validation establishes feasibility without a duplicate
            # solver compilation. Keep its origin distinct from native solutions.
            result.rectangles = deepcopy(initial.rectangles)
            result.grids = deepcopy(initial.grids)
            result.measurements = deepcopy(initial_measurements)
            result.status = ResultStatus.FEASIBLE
            result.strict_status = StrictStatus.SAT
            result.incumbent_source = "checked_seed"
            state = "SATISFIED"
        else:
            state = run()
            result.strict_status = (
                StrictStatus.SAT
                if result.rectangles
                else (
                    StrictStatus.UNSAT
                    if state == "UNSATISFIABLE"
                    else StrictStatus.UNKNOWN
                )
            )
            if initial is not None and state == "UNSATISFIABLE":
                raise RuntimeError(
                    "Checked initial geometry disagrees with solver constraints"
                )
        data["fixed"] = False
        if state == "UNSATISFIABLE" and allow_relaxed:
            result.mode = ResultMode.DIAGNOSTIC
            data["strict"] = False
            ids = {o.id: i for i, o in enumerate(objects, 1)}
            pairs = collision_pairs(problem, strict=False)
            data.update(
                nc=len(pairs),
                ci=[ids[i] for i, j in pairs],
                cj=[ids[j] for i, j in pairs],
            )
            state = run()
        if not result.rectangles:
            result.status = (
                ResultStatus.INFEASIBLE
                if state == "UNSATISFIABLE"
                else ResultStatus.UNKNOWN
            )
            if state == "UNSATISFIABLE":
                result.reason = "Infeasible within the supplied canvas, dimensions, spacing and pins"
        elif optimize:
            for index in indices:
                name = SCORES[index - 1]
                upper = result.measurements[name]
                lower = (
                    1
                    if index == 1 and result.strict_status == StrictStatus.UNSAT
                    else 0
                )
                if upper > lower:
                    data["phase"] = index
                    data["incumbent_bound"] = upper
                    state = run()
                    if state == "UNSATISFIABLE":
                        raise RuntimeError("Optimization rejected a checked incumbent")
                    upper = result.measurements[name]
                    proven = state == "OPTIMAL_SOLUTION"
                else:
                    proven = True
                result.phases.append(
                    {
                        "objective": name,
                        "lower_bound": upper if proven else lower,
                        "value": upper,
                        "proven": proven,
                    }
                )
                if not proven:
                    break
                data["proved"][index - 1] = upper
            if len(result.phases) == len(indices) and all(
                p["proven"] for p in result.phases
            ):
                result.status = ResultStatus.OPTIMAL
                result.reason = ""
    if neighborhood is not None and result.rectangles:
        result.status = ResultStatus.FEASIBLE
        result.reason = "Bounded neighborhood refinement; no global optimum claimed"
        for phase in result.phases:
            phase["neighborhood_proven"] = phase["proven"]
            phase["neighborhood_lower_bound"] = phase["lower_bound"]
            phase["proven"] = phase["value"] == 0
            phase["lower_bound"] = 0
    result.elapsed_seconds = monotonic() - start
    return result
