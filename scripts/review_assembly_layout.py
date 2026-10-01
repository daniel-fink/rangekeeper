"""Produce synthetic Turn-1 review artifacts. Requires RK[layout-prototype]."""

import argparse
import hashlib
import json
import platform
from dataclasses import asdict
from html import escape
from pathlib import Path

from rangekeeper.graph.adapter.cytoscape.layout import model
from rangekeeper.graph.adapter.cytoscape.layout.examples import examples
from rangekeeper.graph.adapter.cytoscape.layout.render import svg
from rangekeeper.graph.adapter.cytoscape.layout.z3_solver import solve


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=15)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(
        args.output / "implementation.json",
        {
            "python": platform.python_version(),
            "files": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(Path(model.__file__).parent.glob("*.py"))
            },
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "seconds_per_solve": args.seconds,
        },
    )
    cards, summary = [], []
    for name, problem in examples().items():
        first = solve(problem, time_limit=args.seconds, optimize=False)
        result = solve(problem, time_limit=args.seconds, allow_relaxed=True)
        write_json(args.output / f"{name}.problem.json", problem.document())
        write_json(args.output / f"{name}.geometry.json", result.geometry_document())
        record = asdict(result)
        record["first_pass"] = {
            "status": first.status,
            "seconds": first.elapsed_seconds,
            "metrics": first.measurements,
        }
        write_json(args.output / f"{name}.run.json", record)
        picture = svg(problem, result)
        (args.output / f"{name}.svg").write_text(picture)
        if first.rectangles:
            (args.output / f"{name}.initial.svg").write_text(svg(problem, first))
        print(name, result.status, result.mode, result.measurements, flush=True)
        summary.append(
            {
                "case": name,
                "status": result.status,
                "strict_status": result.strict_status,
                "mode": result.mode,
                "seconds": result.elapsed_seconds,
                **result.measurements,
            }
        )
        valid = result.mode == "strict" and bool(result.rectangles)
        badge = (
            "VALID GEOMETRY"
            if valid
            else ("EXPLICIT CONFLICTS" if result.rectangles else "NO LAYOUT")
        )
        findings = "".join(
            f"<li>{escape(f['objects'][0])} / {escape(f['objects'][1])}: {escape(f['message'])}</li>"
            for f in result.findings
        )
        metric = result.measurements
        memberships = "".join(
            f"<li><b>{escape(a.label)}</b>: {escape(', '.join(a.members))}</li>"
            for a in problem.assemblies
        )
        before = escape(json.dumps(first.measurements))
        cards.append(f'''<section id="{name}"><div class="heading"><h2>{name.replace("-", " ").title()}</h2>
<span class="badge {"good" if valid else "warn"}">{badge}</span></div>
<p class="metrics">{result.status} · {result.elapsed_seconds:.2f}s · false enclosures {metric.get("false_enclosures", "—")}
· grid displacement {metric.get("grid_displacement", "—")}px · extent {metric.get("extent", "—")}px</p>
<div class="canvas">{picture}</div><ul class="conflicts">{findings}</ul>
<details><summary>Memberships, objectives and evidence</summary><ul>{memberships}</ul>
<p>Feasibility-only status: {first.status}. Initial measurements: <code>{before}</code></p>
<pre>{escape(json.dumps(result.phases, indent=2))}</pre>
<p>{escape(result.reason)}</p><a href="{name}.problem.json">Input</a> ·
<a href="{name}.geometry.json">Geometry + checks</a> · <a href="{name}.run.json">Solve record</a> ·
<a href="{name}.svg">Full-size SVG</a></details></section>''')
    write_json(args.output / "summary.json", summary)
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Assembly layout · constraint review</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#17283d;font:16px/1.55 system-ui,sans-serif}
main{max-width:1180px;margin:auto;padding:40px 28px}h1{font-size:34px;line-height:1.15;margin:8px 0 16px}
h2{font-size:23px;margin:0}.intro{max-width:850px}.eyebrow{font-size:12px;letter-spacing:2px;font-weight:700;color:#52667f}
section{background:white;border:1px solid #dbe2eb;border-radius:12px;padding:26px;margin:28px 0}
.heading{display:flex;gap:16px;align-items:center;justify-content:space-between}.badge{font-size:11px;font-weight:750;padding:5px 10px;border-radius:5px}
.good{background:#e0f3e9;color:#176241}.warn{background:#fff0d9;color:#93440c}.metrics{color:#52667f;font-size:14px}
.canvas{overflow:auto;border:1px solid #e2e8f0;border-radius:6px;background:white;padding:16px}.canvas svg{display:block;max-width:100%;height:auto;max-height:650px}
details{margin-top:18px}summary{cursor:pointer;color:#24538c}pre,code{font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere}
.conflicts{color:#a52727}a{color:#24538c}nav a{display:inline-block;margin:0 18px 8px 0}.note{border-left:3px solid #c69239;padding-left:16px}
</style><main><div class="eyebrow">RANGEKEEPER / LAYOUT RESEARCH / TURN 1</div>
<h1>Correct memberships first.<br>Grid preferences second.</h1>
<div class="intro"><p>One rectangle per assembly. One visual instance per node. All displayed coordinates are checked independently and rechecked from the exported SVG. These are synthetic review examples, separate from the production viewer.</p>
<p>Grid displacement measures distance from stable-ID row-major templates, with a choice of column count for every assembly. Cell pitch is the largest member footprint plus spacing. Zero means perfect template alignment; it does not guarantee the most pleasing arrangement.</p>
<p class="note">An <b>optimal</b> result is proven only for this bounded model and its stated objectives. A <b>feasible</b> result is checked but its aesthetic optimum is unproven. Diagnostic conflicts are explicit and never presented as valid membership geometry. No solver comparison has been performed yet.</p></div><nav>"""
    page += "".join(
        f'<a href="#{name}">{name.replace("-", " ")}</a>' for name in examples()
    )
    page += "</nav>" + "".join(cards) + "</main></html>"
    (args.output / "index.html").write_text(page)


if __name__ == "__main__":
    main()
