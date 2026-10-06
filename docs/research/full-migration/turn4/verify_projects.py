"""Rebuild and check copied current sources using the normally installed wheel.

Private source payloads remain in the temporary workspace. Reports retain only
counts, status and source hashes. No archive or previous output is a build input.
The separate comparator reads the frozen historical baseline after each build.
"""

from collections import Counter
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import rangekeeper

ROOT = Path(__file__).resolve().parents[4]
parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=("build", "tests", "compare"))
parser.add_argument("--root", type=Path, default=Path("/private/tmp/rk-turn4-project-bootstrap"))
args = parser.parse_args()
base = args.root
assert "rk-turn4-project-venv" in rangekeeper.__file__, rangekeeper.__file__
assert "PYTHONPATH" not in os.environ
for module in ("pandas", "numpy", "polars", "networkx", "specklepy", "pyomo", "plotly"):
    assert importlib.util.find_spec(module) is None, module
print("Installed import:", rangekeeper.__file__, flush=True)
if args.phase == "build":
    from rangekeeper.workflow.workbench import build
    for project, spec, name in (
        ("mandarin", "spec", "mandarin"),
        ("east-whisman", "spec/december", "december"),
        ("east-whisman", "spec/november-r2", "november-r2"),
    ):
        attempt = build(base / project / spec, input_root=base / project / "inputs",
                        output_root=base / "results" / name)
        assert attempt.result is not None, attempt.diagnostics
        print(json.dumps({"name": name, "directory": str(attempt.directory),
            "objects": len(attempt.result.model.find_entities()),
            "relationships": len(attempt.result.model.system.relationships),
            "checks": dict(Counter(c.status for c in attempt.result.checks)),
        }), flush=True)
elif args.phase == "tests":
    for project in ("mandarin", "east-whisman"):
        for command in (
            [sys.executable, "-m", "pytest", "tests", "-q"],
            [str(Path(sys.executable).parent / "ruff"), "check", "tests"],
            [str(Path(sys.executable).parent / "ty"), "check", "tests", "--python", sys.executable, "--config", "environment.extra-paths=[]"],
        ):
            subprocess.run(command, cwd=base / project, check=True)
else:
    # Reuse the accepted strict comparator, never the historical implementation.
    spec = importlib.util.spec_from_file_location("comparison", ROOT / "docs/research/full-migration/turn3/compare_projects.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, namespace in (("mandarin", "urn:whirlwind:project:mandarin"),
                            ("december", "urn:whirlwind:project:east-whisman"),
                            ("november-r2", "urn:whirlwind:project:east-whisman")):
        latest = json.loads((base / "results" / name / "latest.json").read_text())
        result = module.compare(Path("/private/tmp/rk-turn3-private/baseline") / name,
                                base / "results" / name / latest["directory"], namespace)
        (base / f"{name}-comparison.json").write_text(json.dumps(result, indent=2))
        print(name, {k: v for k, v in result.items() if k not in ("identity_map", "retained_null_measurements")},
              "new_nulls", len(result["retained_null_measurements"]), flush=True)
for path, expected in json.loads((base / "source-hashes.json").read_text()).items():
    assert hashlib.sha256((base / path).read_bytes()).hexdigest() == expected, path
print("Original source bytes preserved")
