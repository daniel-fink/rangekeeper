"""Browser conflict arithmetic agrees with the independent Python checker."""

import json
import shutil
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from rangekeeper.adapters.cytoscape.layout.check import check
from rangekeeper.adapters.cytoscape.layout.model import Assembly, Node, Problem, Rect

CLIENT = Path(__file__).parents[1] / "rangekeeper/adapters/cytoscape/client"


@pytest.mark.skipif(
    not shutil.which("node") or not (CLIENT / "node_modules/esbuild").exists(),
    reason="Requires viewer development dependencies",
)
def test_browser_conflicts_match_independent_arithmetic():
    problem = Problem(
        (
            Node("left", "Left", 40, 30),
            Node("shared", "Shared", 40, 30),
            Node("right", "Right", 40, 30),
        ),
        (
            Assembly("A", "A", ("left", "shared"), 100),
            Assembly("B", "B", ("shared", "right"), 100),
        ),
        width=1000,
        height=1000,
        padding=10,
        header=30,
        gap=5,
    )
    # Crossing rectangles with a shared node; headers occupy different heights.
    rects = {
        "left": Rect(20, 60, 40, 30),
        "shared": Rect(100, 120, 40, 30),
        "right": Rect(180, 120, 40, 30),
        "A": Rect(10, 10, 140, 150),
        "B": Rect(90, 75, 140, 85),
    }
    fixtures = [
        rects,
        {**rects, "left": replace(rects["left"], x=180, y=120)},
        {**rects, "B": Rect(90, 10, 140, 150)},
        {**rects, "B": Rect(20, 50, 100, 100)},
    ]
    expected = []
    payload = []
    for rs in fixtures:
        expected.append(
            sorted(
                (f.code, list(f.objects))
                for f in check(replace(problem, gap=0), rs)
                if f.code in {"collision", "exclusion"}
            )
        )
        payload.append(
            {
                "graph": {
                    "assemblies": {
                        a.id: {"entities": a.members} for a in problem.assemblies
                    },
                    "savedLayout": {"problem": {"header": 30, "gap": 5}},
                },
                "boxes": {i: asdict(r) for i, r in rs.items()},
            }
        )
    assert expected[0] == []
    script = """const {visibleConflicts}=require('./test/load-presentation.js');let data='';process.stdin.on('data',s=>data+=s);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(data).map(f=>visibleConflicts(f.graph,f.boxes,new Set(Object.keys(f.boxes))).map(c=>[c.code,c.objects])))));"""
    actual = json.loads(
        subprocess.run(
            ["node", "-e", script],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=CLIENT,
            check=True,
            timeout=20,
        ).stdout
    )
    assert [
        sorted((code, ids) for code, ids in findings) for findings in actual
    ] == expected
