"""Capture historical project results outside Git using the pinned legacy worktree.

Run from a project's Python 3.13 environment. This reads approved source files and
writes only the explicitly supplied output directory; it never executes archives.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
from rangekeeper.graph.workflow import load, run
from rangekeeper.graph.workflow.review import export

parser = argparse.ArgumentParser()
parser.add_argument("--projects", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
for project, spec, name in [
    ("mandarin", "spec", "mandarin"),
    ("east-whisman", "spec/december", "december"),
    ("east-whisman", "spec/november-r2", "november-r2"),
]:
    root = args.projects / project
    outcome = run(load(root / spec), input_root=root / "inputs")
    if outcome.output is None:
        raise RuntimeError(outcome.diagnostics)
    result = outcome.output
    export(result, args.output / name)
    print(
        json.dumps(
            {
                "project": name,
                "entities": len(result.graph.entities),
                "relationships": len(result.graph.relationships),
                "checks": dict(Counter(c.status for c in result.checks)),
            }
        ),
        flush=True,
    )
