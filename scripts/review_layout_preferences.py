"""Run explicit preference variants with identical footprints and common scoring."""

import argparse
import json
from dataclasses import asdict
from hashlib import sha256
from html import escape
from pathlib import Path
from time import monotonic

from rangekeeper.graph.adapter.cytoscape.layout import model
from rangekeeper.graph.adapter.cytoscape.layout.check import metrics
from rangekeeper.graph.adapter.cytoscape.layout.model import from_document
from rangekeeper.graph.adapter.cytoscape.layout.render import svg
from rangekeeper.graph.adapter.cytoscape.layout.seed import grid_seed
from rangekeeper.graph.adapter.cytoscape.layout.z3_solver import solve


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()
    source = json.loads(args.cases.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output / "cases.json", source)
    write(
        args.output / "implementation.json",
        {
            "seconds_per_solve": args.seconds,
            "cases_sha256": sha256(args.cases.read_bytes()).hexdigest(),
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "files": {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in sorted(Path(model.__file__).parent.glob("*.py"))
            },
        },
    )
    summaries, sections = [], []
    for case in source["cases"]:
        evaluation = from_document(case["evaluation"])
        cards = []
        for variant in case["variants"]:
            problem = from_document(variant["problem"])
            # Comparison may vary presentation only, never footprints/membership/bounds.
            left = problem.document()
            right = evaluation.document()
            for document in (left, right):
                document.pop("weights")
                document.pop("preferences")
            if left != right:
                raise ValueError("Comparison variants changed geometry inputs")
            name = case["id"] + "-" + variant["id"]
            if not name or any(
                c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name
            ):
                raise ValueError("Case and variant IDs must be safe lowercase names")
            start = monotonic()
            seed = grid_seed(problem)
            seed_seconds = monotonic() - start
            result = solve(problem, time_limit=args.seconds, initial=seed)
            common = (
                metrics(evaluation, result.rectangles, result.grids)
                if result.rectangles
                else None
            )
            write(args.output / f"{name}.problem.json", problem.document())
            write(args.output / f"{name}.geometry.json", result.geometry_document())
            record = {
                "result": asdict(result),
                "common_evaluation": common,
                "seed_seconds": seed_seconds,
                "seed": seed.geometry_document() if seed else None,
            }
            write(args.output / f"{name}.run.json", record)
            picture = svg(problem, result, node_colors=case.get("node_colors"))
            (args.output / f"{name}.svg").write_text(picture)
            summary = {
                "case": case["id"],
                "variant": variant["id"],
                "status": result.status,
                "solver_seconds": result.elapsed_seconds,
                "seed_seconds": seed_seconds,
                "common": common,
                "optimized": result.measurements,
                "seed_style_cost": seed.measurements["style_cost"] if seed else None,
            }
            summaries.append(summary)
            print(json.dumps(summary), flush=True)
            fields = (
                "grid_score",
                "direction_score",
                "order_score",
                "similarity_score",
                "extent",
                "style_cost",
            )
            scores = "".join(
                f"<tr><td>{key.replace('_', ' ')}</td><td>{common[key] if common else '—'}</td></tr>"
                for key in fields
            )
            seed_text = (
                f"Seed style cost {seed.measurements['style_cost']}; final optimized cost {result.measurements.get('style_cost', '—')}. "
                if seed
                else "No tree seed: shared memberships solved directly. "
            )
            cards.append(f'''<article><h3>{escape(variant["title"])}</h3><p>{escape(variant["note"])}</p>
<p class="status">{result.status} · {result.elapsed_seconds:.2f}s solver · {seed_seconds:.2f}s seed · {len(result.findings)} geometry findings</p>
<div class="canvas">{picture}</div><p><a href="{name}.svg" target="_blank">Full-size SVG</a></p>
<details><summary>Common scores and solve evidence</summary><table>{scores}</table><p>{escape(seed_text)}</p>
<p>Optimized objective differs by profile; the table evaluates every picture under the same full preference model for this case. Scores are not comparable across different cases.</p>
<pre>{escape(json.dumps(result.phases, indent=2))}</pre><p>{escape(result.reason)}</p>
<a href="{name}.problem.json">Input</a> · <a href="{name}.geometry.json">Geometry</a> · <a href="{name}.run.json">Run and seed</a></details></article>''')
        sections.append(
            f'<section id="{escape(case["id"])}"><h2>{escape(case["title"])}</h2><p>{escape(case["note"])}</p><div class="cards">'
            + "".join(cards)
            + "</div></section>"
        )
    write(args.output / "summary.json", summaries)
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Layout preference comparisons</title><style>
body{font:15px/1.5 system-ui,sans-serif;color:#203044;background:#f4f7fb;margin:0}main{max-width:1500px;margin:auto;padding:32px 24px}h1{font-size:34px}h2{font-size:25px}h3{margin-top:0}.cards{display:grid;grid-template-columns:1fr;gap:18px}article{background:white;border:1px solid #d6dfea;border-radius:8px;padding:20px;min-width:0}section{margin:40px 0}.canvas{overflow:auto;max-height:650px;background:white;border:1px solid #e3e9f1}.canvas svg{display:block;max-width:100%;height:auto}.status{color:#586c84;font-size:13px}a{color:#185ca5}nav a{display:inline-block;margin-right:18px}pre{white-space:pre-wrap;font-size:12px}table{border-collapse:collapse;width:100%}td{padding:5px;border-bottom:1px solid #e3e9f1}summary{cursor:pointer}.note{padding:16px;border-left:4px solid #a7770c;background:#fff4d9}details{margin:12px 0}
</style><main><p>RANGEKEEPER · LAYOUT SPIKE · PREFERENCE REVIEW</p><h1>Direction, similarity and space</h1>
<p>Identical graph objects, memberships, footprints and canvas within each comparison. Direction, ordering and affinity are soft preferences. All displayed SVG coordinates pass the independent geometry checker.</p>
<p class="note">Experimental weights: grid 4, direction 3, ordering 6, similarity 3, compactness 1. Grid positions can permute. Tree examples start from a checked recursive grid; shared examples have no tree seed. A feasible result is not a proved optimum. These are selected input subgraphs and synthetic examples, not a complete input solve or a solver comparison.</p>
<p>Colors encode the displayed bedroom count or classification, consistently across variants. Similarity uses explicitly selected fields only; values are normalized within each assembly, missing values do not match, and constant fields are excluded. No physical apartment order or scaled elevation is inferred.</p><nav>"""
    page += "".join(
        f'<a href="#{escape(c["id"])}">{escape(c["title"])}</a>'
        for c in source["cases"]
    )
    page += (
        "</nav>"
        + "".join(sections)
        + '<p><a href="cases.json">All inputs, signal explanations and source hashes</a> · <a href="summary.json">Comparison scores</a> · <a href="implementation.json">Implementation hashes</a></p></main></html>'
    )
    (args.output / "index.html").write_text(page)


if __name__ == "__main__":
    main()
