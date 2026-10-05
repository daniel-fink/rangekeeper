"""Reproduce correction acceptance with retained command metadata and fresh outputs.

Run from the repository root with the full runtime interpreter. Notebook phase
needs local kernel sockets and a fresh wheel destination. Temporary interpreter
paths identify the recorded environment, not package requirements.
"""

from pathlib import Path
import argparse
import importlib.util
import os
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SCHEMA = Path("/private/tmp/rk-probe-audit-venv/bin/python")
RUNTIME = Path("/private/tmp/rk-full-runtime/bin/python")
spec = importlib.util.spec_from_file_location("baseline", ROOT / "docs/research/domain-migration/evidence/run_baseline.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.OUT = OUT
os.environ["MPLCONFIGDIR"] = "/private/tmp/rk-mpl-cache"
parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=("checks", "tests", "install", "notebook"))
parser.add_argument("--wheel-dir", type=Path, default=Path("/private/tmp/rk-date-only-final"))
args = parser.parse_args()
failed = []


def run(name, argv, cwd=ROOT, timeout=600):
    if runner.run(name, argv, cwd, timeout):
        failed.append(name)


if args.phase == "checks":
    for name in ("validate", "native_roundtrip", "expressions", "formulations", "models", "specifications", "runs"):
        run("final-schema-" + name, [SCHEMA, ROOT / "schema/checks" / (name + ".py")])
    run("final-native-dates", [SCHEMA, OUT / "native_dates.py"])
    run("final-generation", [SCHEMA, ROOT / "tools/schema/generate.py", "--check"])
    os.environ["PYTHONPATH"] = "/private/tmp/rk-record-typecheck"
    run("final-typecheck", [RUNTIME, ROOT / "tools/schema/typecheck.py"])
elif args.phase == "tests":
    run("pytest-final", [RUNTIME, "-m", "pytest", "tests", "-q", "--tb=short", "--ignore=tests/test_api.py",
        "-o", "cache_dir=/private/tmp/rk-date-pytest-cache", "--junitxml=" + str(OUT / "pytest-final.xml")], ROOT / "src", 900)
elif args.phase == "install":
    run("final-installed", [SCHEMA, ROOT / "tools/schema/verify_install.py", "--runtime-python", RUNTIME,
        "--execution-python", RUNTIME, "--workflow-python", RUNTIME])
else:
    run("final-wheel", [SCHEMA, ROOT / "docs/research/full-migration/turn1/build_notebook_environment.py",
        "--output", args.wheel_dir])
    if failed:
        raise SystemExit(1)
    os.environ["PYTHONPATH"] = str(args.wheel_dir / "site")
    run("final-notebook", [RUNTIME, ROOT / "docs/research/full-migration/turn1/run_notebook.py",
        ROOT / "walkthrough/basic_dcf.ipynb", OUT / "basic_dcf_final.ipynb", "--cwd", args.wheel_dir], Path("/private/tmp"))
    run("final-guide", [RUNTIME, OUT / "guide_example.py"], Path("/private/tmp"))

raise SystemExit(bool(failed))
