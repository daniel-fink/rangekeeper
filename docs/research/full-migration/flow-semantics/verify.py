"""Reproduce Flow semantic-kind removal checks and retain commands and logs.

Run from the repository root. Existing temporary environments contain the pinned
schema tools and complete local runtime; use a fresh wheel directory for notebook
verification. Prior checkpoint evidence is never overwritten by this runner.
"""

from pathlib import Path
import argparse
import importlib.util
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SCHEMA = Path("/private/tmp/rk-probe-audit-venv/bin/python")
RUNTIME = Path("/private/tmp/rk-full-runtime/bin/python")
spec = importlib.util.spec_from_file_location(
    "baseline", ROOT / "docs/research/domain-migration/evidence/run_baseline.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.OUT = OUT
os.environ["MPLCONFIGDIR"] = "/private/tmp/rk-mpl-cache"
parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=("focused", "checks", "tests", "install", "notebook"))
parser.add_argument("--wheel-dir", type=Path, default=Path("/private/tmp/rk-flow-semantics-wheel"))
args = parser.parse_args()
failed = []


def run(name, argv, cwd=ROOT, timeout=600):
    if runner.run(name, argv, cwd, timeout):
        failed.append(name)


if args.phase == "focused":
    run("focused", [RUNTIME, "-m", "pytest", "tests/test_flow_operations.py",
        "tests/test_calculations.py", "tests/test_calculation_equivalence.py",
        "tests/test_flow_dates.py", "tests/test_financial_library.py", "tests/test_formulas.py",
        "tests/test_models.py", "-q", "--tb=short", "-o", "cache_dir=/private/tmp/rk-flow-pytest-cache"], ROOT / "src")
elif args.phase == "checks":
    for name in ("validate", "native_roundtrip", "expressions", "formulations", "models", "specifications", "runs"):
        run("schema-" + name, [SCHEMA, ROOT / "schema/checks" / (name + ".py")])
    run("generation", [SCHEMA, ROOT / "tools/schema/generate.py", "--check"])
    run("native-flow", [SCHEMA, OUT / "native_flow.py"])
    os.environ["PYTHONPATH"] = "/private/tmp/rk-record-typecheck"
    run("typecheck", [RUNTIME, ROOT / "tools/schema/typecheck.py"])
elif args.phase == "tests":
    run("pytest-local", [RUNTIME, "-m", "pytest", "tests", "-q", "--tb=short", "--ignore=tests/test_api.py",
        "-o", "cache_dir=/private/tmp/rk-flow-pytest-cache", "--junitxml=" + str(OUT / "pytest-local.xml")], ROOT / "src", 900)
elif args.phase == "install":
    run("installed", [SCHEMA, ROOT / "tools/schema/verify_install.py", "--runtime-python", RUNTIME,
        "--financial-python", RUNTIME, "--execution-python", RUNTIME, "--workflow-python", RUNTIME])
else:
    run("wheel", [SCHEMA, ROOT / "docs/research/full-migration/turn1/build_notebook_environment.py",
        "--output", args.wheel_dir])
    if failed:
        raise SystemExit(1)
    os.environ["PYTHONPATH"] = str(args.wheel_dir / "site")
    run("notebook", [RUNTIME, ROOT / "docs/research/full-migration/turn1/run_notebook.py",
        ROOT / "walkthrough/basic_dcf.ipynb", OUT / "basic_dcf.ipynb", "--cwd", args.wheel_dir], Path("/private/tmp"))
    guide = (ROOT / "docs/LEGACY_UPGRADE_GUIDE.md").read_text()
    import re
    blocks = re.findall(r"```python\n(.*?)```", guide, re.S)
    (OUT / "guide_example.py").write_text("\n\n".join(blocks))
    run("guide", [RUNTIME, OUT / "guide_example.py"], Path("/private/tmp"))

raise SystemExit(bool(failed))
