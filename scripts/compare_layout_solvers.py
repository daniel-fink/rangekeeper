"""Reproducible, process-isolated Z3 versus MiniZinc/CP-SAT spike comparison."""

import argparse
import json
import os
import signal
import subprocess
import sys
from dataclasses import asdict
from hashlib import sha256
from html import escape
from pathlib import Path
from time import monotonic

from rangekeeper.graph.adapter.cytoscape.layout import model
from rangekeeper.graph.adapter.cytoscape.layout.check import check, metrics
from rangekeeper.graph.adapter.cytoscape.layout.model import Rect, from_document
from rangekeeper.graph.adapter.cytoscape.layout.render import svg
from rangekeeper.graph.adapter.cytoscape.layout.result import Result
from rangekeeper.graph.adapter.cytoscape.layout.seed import grid_seed


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def restore(record):
    values = dict(record)
    values["rectangles"] = {i: Rect(**r) for i, r in record["rectangles"].items()}
    return Result(**values)


def worker(args):
    payload = json.loads(args.worker.read_text())
    problem = from_document(payload["problem"])
    initial = restore(payload["seed"]) if payload["seed"] else None
    if args.engine == "z3":
        from rangekeeper.graph.adapter.cytoscape.layout.z3_solver import solve
    else:
        from rangekeeper.graph.adapter.cytoscape.layout.minizinc_solver import solve
    result = solve(
        problem,
        time_limit=payload["seconds"],
        allow_relaxed=payload.get("allow_relaxed", False),
        initial=initial,
    )
    write(args.result, asdict(result))


def main(args):
    source = json.loads(args.cases.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output / "cases.json", source)
    import z3

    from rangekeeper.graph.adapter.cytoscape.layout.minizinc_solver import toolchain

    write(
        args.output / "implementation.json",
        {
            "minizinc": toolchain(),
            "z3": z3.get_version_string(),
            "seconds": args.seconds,
            "full_seconds": args.full_seconds,
            "repeats": args.repeats,
            "process_grace_seconds": 5,
            "cases_sha256": sha256(args.cases.read_bytes()).hexdigest(),
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "files": {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in sorted(Path(model.__file__).parent.iterdir())
                if p.suffix in {".py", ".mzn"}
            },
            "note": "Seed preparation and process startup reported separately. Per-engine budget includes model construction/compilation. CP-SAT recompiles each lexicographic phase; Z3 uses incremental binary search. One worker and random seed 0. CP-SAT reuses the independently checked seed and receives native warm-start hints, with native presolve disabled for seeded optimization; Z3 verifies it through temporary assumptions. first_solution_seconds means the first native solver model, not external seed availability.",
        },
    )
    sections = []
    summaries = []
    for case in source["cases"]:
        name = case["id"]
        if (
            any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name)
            or not name
        ):
            raise ValueError("Unsafe case name")
        print(f"Preparing {name}", flush=True)
        problem = from_document(case["problem"])
        start = monotonic()
        seed = grid_seed(problem)
        seed_seconds = monotonic() - start
        budget = args.full_seconds if name in args.full_case else args.seconds
        request = {
            "problem": problem.document(),
            "seed": asdict(seed) if seed else None,
            "seconds": budget,
            "allow_relaxed": case.get("allow_relaxed", False),
        }
        requestfile = args.output / f"{name}.input.json"
        write(requestfile, request)
        cards = []
        if seed:
            picture = svg(problem, seed, node_colors=case.get("node_colors"))
            (args.output / f"{name}.seed.svg").write_text(picture)
            cards.append(
                f'<article><h3>Shared recursive-grid seed</h3><p>{seed_seconds:.3f}s preparation · independently checked · no optimality claim</p><p>Style cost: {seed.measurements.get("style_cost")}</p><a href="{name}.seed.svg">Full-size seed SVG</a><div class="canvas">{picture}</div></article>'
            )
        for repeat in range(args.repeats):
            for engine in ("z3", "cp-sat") if repeat % 2 == 0 else ("cp-sat", "z3"):
                slug = f"{name}-{engine}-{repeat + 1}"
                target = args.output / f"{slug}.run.json"
                start = monotonic()
                process = subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--worker",
                        str(requestfile.resolve()),
                        "--engine",
                        engine,
                        "--result",
                        str(target.resolve()),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                )
                killed = False
                try:
                    _stdout, stderr = process.communicate(timeout=budget + 5)
                except subprocess.TimeoutExpired:
                    killed = True
                    os.killpg(process.pid, signal.SIGKILL)
                    __stdout, stderr = process.communicate()
                wall = monotonic() - start
                if target.exists() and process.returncode == 0:
                    result = restore(json.loads(target.read_text()))
                    if result.rectangles:
                        findings = check(problem, result.rectangles)
                        if any(
                            f.code != "exclusion" or result.mode == "strict"
                            for f in findings
                        ):
                            raise RuntimeError("Benchmark rejected geometry")
                        if (
                            metrics(problem, result.rectangles, result.grids)
                            != result.measurements
                        ):
                            raise RuntimeError("Benchmark rejected scores")
                else:
                    result = Result(
                        "unknown" if killed else "error",
                        "unknown",
                        reason="Outer process deadline: no completed solver result"
                        if killed
                        else stderr[-5000:],
                        problem_fingerprint=problem.fingerprint,
                    )
                    write(target, asdict(result))
                picture = svg(problem, result, node_colors=case.get("node_colors"))
                (args.output / f"{slug}.svg").write_text(picture)
                write(args.output / f"{slug}.geometry.json", result.geometry_document())
                summary = {
                    "case": name,
                    "engine": engine,
                    "repeat": repeat + 1,
                    "status": result.status,
                    "strict_status": result.strict_status,
                    "mode": result.mode,
                    "seed_seconds": seed_seconds,
                    "seed_metrics": seed.measurements if seed else None,
                    "incumbent_source": result.incumbent_source,
                    "seed_retained": result.rectangles == seed.rectangles
                    and result.grids == seed.grids
                    if seed
                    else None,
                    "budget_seconds": budget,
                    "process_wall_seconds": wall,
                    "solver_seconds": result.elapsed_seconds,
                    "build_seconds": result.build_seconds,
                    "first_solution_seconds": result.first_solution_seconds,
                    "metrics": result.measurements,
                    "phases": result.phases,
                    "findings": len(result.findings),
                    "reason": result.reason,
                }
                summaries.append(summary)
                write(args.output / "summary.json", summaries)
                print(
                    json.dumps(
                        {
                            k: summary[k]
                            for k in (
                                "case",
                                "engine",
                                "repeat",
                                "status",
                                "process_wall_seconds",
                                "seed_retained",
                            )
                        }
                    ),
                    flush=True,
                )
                cards.append(
                    f'<article><h3>{engine} · run {repeat + 1}</h3><p><strong>{result.status}</strong> · {result.mode} · {wall:.2f}s process wall · {len(result.findings)} findings</p><p>Incumbent source: {escape(result.incumbent_source)} · Seed retained: {summary["seed_retained"]}</p><div class="canvas">{picture}</div><p><a href="{slug}.svg">Full-size SVG</a> · <a href="{slug}.run.json">Run evidence</a></p><details><summary>Scores, bounds and timings</summary><pre>{escape(json.dumps(summary, indent=2))}</pre></details></article>'
                )
        sections.append(
            f'<section id="{name}"><h2>{escape(case.get("title", name))}</h2><p>{escape(case.get("note", ""))}</p><p><a href="{name}.input.json">Identical inputs and shared seed</a></p>'
            + "".join(cards)
            + "</section>"
        )
        page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Layout solver comparison</title><style>
body{font:15px/1.5 system-ui;color:#203044;background:#f4f7fb;margin:0}main{max-width:1450px;margin:auto;padding:30px}article{background:white;border:1px solid #ccd6e2;border-radius:8px;padding:18px;margin:16px 0}.canvas{max-height:600px;overflow:auto}.canvas svg{display:block;max-width:100%;height:auto}pre{white-space:pre-wrap}a{color:#185ca5}nav a{display:inline-block;margin-right:18px}.note{background:#fff3d5;padding:16px}section{margin:45px 0}summary{cursor:pointer}</style><main><p>RANGEKEEPER · LAYOUT SPIKE</p><h1>Z3 and MiniZinc / CP-SAT</h1><p>Identical geometry, preferences, canvas and checked seed per case. Compilation and model construction count against each solve budget. Seed preparation is separate. Repeated runs alternate engine order.</p><p class="note">Feasible does not mean optimal. Timeout does not mean impossible. Diagnostic geometry has explicitly reported membership conflicts. A seed picture remains a heuristic result even if neither solver completes. Style scores are comparable only within the same case. Profiles describe schematic geometry; they do not establish physical placement.</p><nav>"""
        page += "".join(
            f'<a href="#{c["id"]}">{escape(c.get("title", c["id"]))}</a>'
            for c in source["cases"]
        )
        page += (
            "</nav>"
            + "".join(sections)
            + '<p><a href="summary.json">All measurements</a> · <a href="implementation.json">Toolchain and implementation hashes</a> · <a href="cases.json">Source evidence and inputs</a></p></main></html>'
        )
        (args.output / "index.html").write_text(page)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--full-seconds", type=float, default=20)
    parser.add_argument(
        "--full-case",
        action="append",
        default=[],
        help="Case ID receiving the full-seconds budget; repeatable",
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--engine", choices=["z3", "cp-sat"])
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args)
    else:
        if not args.cases or not args.output or args.repeats < 1:
            parser.error("--cases, --output and positive --repeats required")
        main(args)
