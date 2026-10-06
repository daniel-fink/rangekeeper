"""Optional MiniZinc/CP-SAT comparison backend; temporary files only.

Each lexicographic phase is compiled separately. The whole budget includes data
preparation, compilation and solving. Complete streamed incumbents survive a
process timeout; every returned incumbent passes independent arithmetic checks.
"""

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

from .check import check, metrics
from .model import Problem, Rect
from .reduction import collision_pairs
from .result import Result

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


def _data(p, initial):
    nodes = sorted(p.nodes, key=lambda n: n.id)
    groups = sorted(p.assemblies, key=lambda a: a.id)
    objects = [*nodes, *groups]
    ids = {o.id: i for i, o in enumerate(objects, 1)}
    prefs = {v.assembly: v for v in p.preferences}
    arrangements = {v.assembly: v for v in p.arrangements}
    pairs = collision_pairs(p)
    descendants = {a.id: p.descendants(a.id) for a in groups}
    membership = [
        (g, ids[i], rank)
        for g, a in enumerate(groups, 1)
        for rank, i in enumerate(sorted(a.members))
    ]
    exclusions = [
        (ids[n.id], ids[a.id])
        for a in groups
        for n in nodes
        if n.id not in descendants[a.id]
    ]
    enclosures = [
        (ids[b.id], ids[a.id])
        for a in groups
        for b in groups
        if b.id != a.id and b.id not in descendants[a.id]
    ]
    orders = [
        (g, ids[b], ids[e], 0 if axis == "x" else 1)
        for g, a in enumerate(groups, 1)
        if a.id in prefs
        for b, e, axis in prefs[a.id].orders
    ]
    affinities = [
        (g, ids[l], ids[r], weight)
        for g, a in enumerate(groups, 1)
        if a.id in prefs
        for l, r, weight in prefs[a.id].affinities
    ]
    data = {
        "ceil_order": p.schema_version >= 3,
        "packed": [
            a.id in arrangements and arrangements[a.id].spacing == "packed"
            for a in groups
        ],
        "flow": [
            (
                ("grid", "row", "column").index(arrangements[a.id].flow)
                if a.id in arrangements
                else 0
            )
            for a in groups
        ],
        "alignment": [
            (
                ("start", "center", "end").index(arrangements[a.id].alignment)
                if a.id in arrangements
                else 0
            )
            for a in groups
        ],
        "neighborhood": False,
        "free_object": [True] * len(objects),
        "free_grid": [True] * len(groups),
        "nc": len(pairs),
        "ci": [ids[i] for i, j in pairs],
        "cj": [ids[j] for i, j in pairs],
        "hinted": initial is not None,
        "nn": len(nodes),
        "ng": len(groups),
        "nm": len(membership),
        "canvas_w": p.width,
        "canvas_h": p.height,
        "padding": p.padding,
        "header": p.header,
        "gap": p.gap,
        "minimum_w": [n.width for n in nodes] + [a.min_width for a in groups],
        "node_h": [n.height for n in nodes],
        "mg": [t[0] for t in membership],
        "mo": [t[1] for t in membership],
        "rank": [t[2] for t in membership],
        "count": [len(a.members) for a in groups],
        "ne": len(exclusions),
        "en": [t[0] for t in exclusions],
        "eg": [t[1] for t in exclusions],
        "na": len(enclosures),
        "ai": [t[0] for t in enclosures],
        "ao": [t[1] for t in enclosures],
        "np": len(p.pins),
        "pi": [ids[i] for i, x, y in p.pins],
        "px": [x for i, x, y in p.pins],
        "py": [y for i, x, y in p.pins],
        "flexible": p.weights is not None,
        "strict": True,
        "fixed": initial is not None,
        "direction": [
            (
                ("unspecified", "horizontal", "vertical", "balanced").index(
                    prefs[a.id].direction
                )
                if a.id in prefs
                else 0
            )
            for a in groups
        ],
        "strength": [prefs[a.id].strength if a.id in prefs else 1 for a in groups],
        "style_unit": p.style_unit,
        "weights": list(asdict(p.weights).values()) if p.weights else [0] * 5,
        "no": len(orders),
        "og": [t[0] for t in orders],
        "ob": [t[1] for t in orders],
        "oe": [t[2] for t in orders],
        "axis": [t[3] for t in orders],
        "nf": len(affinities),
        "fg": [t[0] for t in affinities],
        "fl": [t[1] for t in affinities],
        "fr": [t[2] for t in affinities],
        "fw": [t[3] for t in affinities],
        "phase": 0,
        "proved": [-1] * 9,
        "incumbent_bound": 0,
    }
    for key, attr in (("sx", "x"), ("sy", "y"), ("sw", "width"), ("sh", "height")):
        data[key] = [
            getattr(initial.rectangles[o.id], attr) if initial else 0 for o in objects
        ]
    for key, attr, default in (("sgx", "x", 0), ("sgy", "y", 0), ("sc", "columns", 1)):
        data[key] = [
            initial.grids[a.id][attr] if initial and a.members else default
            for a in groups
        ]
    data["ss"] = [
        (
            initial.grids[groups[g - 1].id]["slots"][objects[i - 1].id]
            if initial and p.weights
            else rank
        )
        for g, i, rank in membership
    ]
    return data, objects, groups


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
        if initial.problem_fingerprint != problem.fingerprint or check(
            problem, initial.rectangles
        ):
            raise ValueError(
                "Initial geometry must match the problem and pass strict checking"
            )
        metrics(problem, initial.rectangles, initial.grids)
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
    data, objects, groups = _data(problem, initial)
    result = Result(
        "unknown",
        "unknown",
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
        findings = check(problem, rectangles)
        if any(f.code != "exclusion" or result.mode == "strict" for f in findings):
            raise RuntimeError(
                f"Solver result failed independent geometry check: {findings}"
            )
        measured = metrics(problem, rectangles, grids)
        for i, name in enumerate(SCORES):
            if name in measured and solution["scores"][i] != measured[name]:
                raise RuntimeError(f"Solver/checker objective disagreement: {name}")
        result.rectangles = rectangles
        result.grids = grids
        result.measurements = measured
        result.findings = [asdict(f) for f in findings]
        result.status = "feasible"
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
            result.measurements = metrics(problem, result.rectangles, result.grids)
            result.status = "feasible"
            result.strict_status = "sat"
            result.incumbent_source = "checked_seed"
            state = "SATISFIED"
        else:
            state = run()
            result.strict_status = (
                "sat"
                if result.rectangles
                else "unsat" if state == "UNSATISFIABLE" else "unknown"
            )
            if initial is not None and state == "UNSATISFIABLE":
                raise RuntimeError(
                    "Checked initial geometry disagrees with solver constraints"
                )
        data["fixed"] = False
        if state == "UNSATISFIABLE" and allow_relaxed:
            result.mode = "diagnostic"
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
            result.status = "infeasible" if state == "UNSATISFIABLE" else "unknown"
            if state == "UNSATISFIABLE":
                result.reason = "Infeasible within the supplied canvas, dimensions, spacing and pins"
        elif optimize:
            for index in indices:
                name = SCORES[index - 1]
                upper = result.measurements[name]
                lower = 1 if index == 1 and result.strict_status == "unsat" else 0
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
                result.status = "optimal"
                result.reason = ""
    if neighborhood is not None and result.rectangles:
        result.status = "feasible"
        result.reason = "Bounded neighborhood refinement; no global optimum claimed"
        for phase in result.phases:
            phase["neighborhood_proven"] = phase["proven"]
            phase["neighborhood_lower_bound"] = phase["lower_bound"]
            phase["proven"] = phase["value"] == 0
            phase["lower_bound"] = 0
    result.elapsed_seconds = monotonic() - start
    return result
