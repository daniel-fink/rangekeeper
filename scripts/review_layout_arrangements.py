"""Compare explicit presentation profiles over the same frozen graph and scores.

Constructive tree layouts only; no solver or global optimality claim. Project
profiles, source hashes and focus IDs are supplied in a separate input document.
"""

import argparse
import json
from dataclasses import asdict
from hashlib import sha256
from html import escape
from pathlib import Path
from time import perf_counter
from xml.etree import ElementTree as ET

from rangekeeper.graph.adapter.cytoscape.layout import model
from rangekeeper.graph.adapter.cytoscape.layout.check import check, metrics
from rangekeeper.graph.adapter.cytoscape.layout.model import Rect, from_document
from rangekeeper.graph.adapter.cytoscape.layout.render import svg, verify_svg
from rangekeeper.graph.adapter.cytoscape.layout.result import Result
from rangekeeper.graph.adapter.cytoscape.layout.seed import grid_seed


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.input.read_text())
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    write(output / "inputs.json", source)
    write(
        output / "implementation.json",
        {
            "files": {
                f.name: sha256(f.read_bytes()).hexdigest()
                for f in Path(model.__file__).parent.iterdir()
                if f.suffix in {".py", ".mzn"}
            },
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "input_sha256": sha256(args.input.read_bytes()).hexdigest(),
        },
    )
    bundle = Path(source["source_bundle"])
    assert all(
        sha256((bundle / n).read_bytes()).hexdigest() == h
        for n, h in source["source_hashes"].items()
    )
    common = None
    rows, sections = [], []
    for case in source["cases"]:
        name = case["id"]
        if not name.replace("-", "").isalnum():
            raise ValueError("Case ID must be alphanumeric with optional hyphens")
        p = from_document(case["problem"])
        contract = p.document()
        contract.pop("arrangements")
        if common is None:
            common = contract
        if contract != common:
            raise ValueError("Only arrangements may vary in this comparison")
        start = perf_counter()
        if "initial" in case:
            value = dict(case["initial"])
            value["rectangles"] = {i: Rect(**r) for i, r in value["rectangles"].items()}
            result = Result(**value)
            result.problem_fingerprint = p.fingerprint
            result.measurements = metrics(p, result.rectangles, result.grids)
            method = "Previous geometry, rescored under v3"
        else:
            result = grid_seed(p)
            if result is None:
                raise ValueError(f"{name}: no constructive layout; no silent fallback")
            method = "Checked constructive layout; no solver optimization"
        elapsed = perf_counter() - start
        assert not check(p, result.rectangles)
        assert metrics(p, result.rectangles, result.grids) == result.measurements
        # Rebuild new candidates to verify determinism, outside the recorded timing.
        if "initial" not in case:
            repeated = grid_seed(p)
            assert (
                repeated is not None
                and repeated.geometry_document() == result.geometry_document()
            )
        result.elapsed_seconds = elapsed
        write(output / f"{name}.problem.json", p.document())
        write(output / f"{name}.geometry.json", result.geometry_document())
        write(output / f"{name}.run.json", asdict(result))
        full = svg(p, result)
        (output / f"{name}.svg").write_text(full)
        # Crop only the viewport: every canonical object and coordinate remains.
        boxes = [result.rectangles[i] for i in source["focus_ids"]]
        x = min(r.x for r in boxes) - 20
        y = min(r.y for r in boxes) - 20
        w = max(r.right for r in boxes) + 20 - x
        h = max(r.bottom for r in boxes) + 20 - y
        el = ET.fromstring(full)
        el.set("viewBox", f"{x} {y} {w} {h}")
        el.set("width", str(w))
        el.set("height", str(h))
        background = el[0]
        for key, value in zip(("x", "y", "width", "height"), (x, y, w, h)):
            background.set(key, str(value))
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        crop = ET.tostring(el, encoding="unicode")
        verify_svg(p, crop, result.rectangles)
        (output / f"{name}-focus.svg").write_text(crop)
        m = result.measurements
        rows.append(
            {
                "id": name,
                "title": case["title"],
                "method": method,
                "elapsed_seconds": elapsed,
                "width": m["width"],
                "height": m["height"],
                "style_cost": m["style_cost"],
                "order_score": m["order_score"],
                "similarity_score": m["similarity_score"],
                "grid_displacement": m["grid_displacement"],
                "geometry_findings": 0,
            }
        )
        sections.append(
            f'<section id="{name}"><h2>{escape(case["title"])}</h2><p>{escape(case["description"])}</p><p>{escape(method)}. Canvas extent {m["width"]:,} × {m["height"]:,}px. <a href="{name}.svg">Open complete graph</a> · <a href="{name}.geometry.json">Geometry and scores</a> · <a href="{name}.problem.json">Presentation profile</a></p><h3>Selected groups · same display scale</h3><div class="crop"><img src="{name}-focus.svg" alt="Selected groups" style="width:{w}px;height:{h}px"></div><details><summary>Complete graph overview · scaled to fit</summary><a href="{name}.svg"><img class="overview" src="{name}.svg" alt="Complete graph"></a></details></section>'
        )
        print(
            name,
            m["width"],
            m["height"],
            m["style_cost"],
            round(elapsed, 2),
            flush=True,
        )
    write(output / "summary.json", rows)
    headings = [
        "Layout",
        "Width × height",
        "Order penalty",
        "Similarity penalty",
        "Style score",
    ]
    table = (
        "<table><thead><tr>"
        + "".join(f"<th>{h}</th>" for h in headings)
        + "</tr></thead><tbody>"
    )
    for r in rows:
        table += f"<tr><td>{escape(r['title'])}</td><td>{r['width']:,} × {r['height']:,}</td><td>{r['order_score']}</td><td>{r['similarity_score']:,}</td><td>{r['style_cost']:,}</td></tr>"
    table += "</tbody></table>"
    html = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Assembly flow review</title><style>body{font:16px/1.5 system-ui;color:#172536;background:#f5f7fa;margin:0;padding:32px}main{max-width:1300px;margin:auto}h1{font-size:32px}nav{display:flex;gap:20px;flex-wrap:wrap;margin:24px 0}a{color:#175da8}section{background:white;padding:24px;margin:32px 0;border:1px solid #d3dce5;border-radius:12px}table{border-collapse:collapse;width:100%;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #d3dce5}.crop{overflow:auto;max-height:720px;border:1px solid #d3dce5;background:white}.crop img{max-width:none;display:block}.overview{width:100%;height:auto;display:block}summary{cursor:pointer;margin-top:20px}small{color:#526174}</style><main><h1>How should assemblies flow?</h1><p>Alternative presentations of the same supplied objects and direct memberships. No workbook, graph assertion or membership changes. Positions are schematic, not a physical plan.</p><p>Row and column profiles prohibit wrapping and use start alignment. Assembly boundaries fit their contents; they are not stretched to a common width. Existing declared ordering and similarity preferences are unchanged.</p><p>All scores use v3, which rounds positive mean ordering deficits upward. Lower scores reflect experimental weights, not a verdict on readability. The old geometry is rescored, so its number differs from the historical benchmark.</p>"""
    html += (
        "<nav>"
        + "".join(f'<a href="#{r["id"]}">{escape(r["title"])}</a>' for r in rows)
        + "</nav>"
        + table
        + "".join(sections)
    )
    html += '<p><a href="inputs.json">Inputs and source hashes</a> · <a href="implementation.json">Implementation hashes</a> · <a href="summary.json">Results</a></p><small>Saved review; no live monitoring. Construction is deterministic for these inputs; neither a global optimum nor production viewer acceptance is claimed.</small></main></html>'
    (output / "index.html").write_text(html)


if __name__ == "__main__":
    main()
