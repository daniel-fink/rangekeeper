"""Reproduce Turn 2 checks and retain commands and logs.

Run from the repository root. Existing temporary environments contain the pinned
schema tools and complete local runtime; use a fresh wheel directory for notebook
verification. Prior checkpoint evidence is never overwritten by this runner.
"""

from pathlib import Path
import argparse
import importlib.util
import os
import json

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
parser.add_argument(
    "phase", choices=("focused", "checks", "tests", "install", "notebook")
)
parser.add_argument(
    "--wheel-dir", type=Path, default=Path("/private/tmp/rk-turn2-wheel")
)
parser.add_argument("--stage", default="verification")
args = parser.parse_args()
OUT = OUT / args.stage
OUT.mkdir(parents=True, exist_ok=True)
runner.OUT = OUT
failed = []
(OUT / (args.phase + "-environment.json")).write_text(
    json.dumps(
        {
            key: os.environ.get(key)
            for key in (
                "PYTHONPATH",
                "MPLBACKEND",
                "MPLCONFIGDIR",
                "RK_SCENARIO_COUNT",
                "RK_SCENARIO_WORKERS",
            )
        },
        indent=2,
    )
)


def run(name, argv, cwd=ROOT, timeout=600):
    if runner.run(name, argv, cwd, timeout):
        failed.append(name)


if args.phase == "focused":
    run(
        "focused",
        [
            RUNTIME,
            "-m",
            "pytest",
            "tests/test_flow_operations.py",
            "tests/test_calculations.py",
            "tests/test_calculation_equivalence.py",
            "tests/test_flow_dates.py",
            "tests/test_financial_library.py",
            "tests/test_formulas.py",
            "tests/test_models.py",
            "tests/test_temporal_execution.py",
            "tests/test_scenarios_policies.py",
            "-q",
            "--tb=short",
            "-o",
            "cache_dir=/private/tmp/rk-flow-pytest-cache",
        ],
        ROOT / "src",
    )
elif args.phase == "checks":
    for name in (
        "validate",
        "native_roundtrip",
        "expressions",
        "formulations",
        "models",
        "specifications",
        "runs",
    ):
        run("schema-" + name, [SCHEMA, ROOT / "schema/checks" / (name + ".py")])
    run("generation", [SCHEMA, ROOT / "tools/schema/generate.py", "--check"])

    os.environ["PYTHONPATH"] = "/private/tmp/rk-record-typecheck"
    run("typecheck", [RUNTIME, ROOT / "tools/schema/typecheck.py"])
elif args.phase == "tests":
    run(
        "pytest-local",
        [
            RUNTIME,
            "-m",
            "pytest",
            "tests",
            "-q",
            "--tb=short",
            "--ignore=tests/test_api.py",
            "-o",
            "cache_dir=/private/tmp/rk-flow-pytest-cache",
            "--junitxml=" + str(OUT / "pytest-local.xml"),
        ],
        ROOT / "src",
        900,
    )
elif args.phase == "install":
    run(
        "installed",
        [
            SCHEMA,
            ROOT / "tools/schema/verify_install.py",
            "--runtime-python",
            RUNTIME,
            "--financial-python",
            RUNTIME,
            "--execution-python",
            RUNTIME,
            "--workflow-python",
            RUNTIME,
        ],
    )
else:
    run(
        "wheel",
        [
            SCHEMA,
            ROOT / "docs/research/full-migration/turn1/build_notebook_environment.py",
            "--output",
            args.wheel_dir,
        ],
    )
    if failed:
        raise SystemExit(1)
    os.environ["PYTHONPATH"] = str(args.wheel_dir / "site")
    os.environ["RK_SCENARIO_COUNT"] = "4"
    os.environ["RK_SCENARIO_WORKERS"] = "1"
    for name in (
        "basic_dcf",
        "deterministic_scenarios",
        "market_dynamics",
        "flexibility_intro",
        "flexibility_under_uncertainty",
    ):
        run(
            "notebook-" + name,
            [
                RUNTIME,
                ROOT / "docs/research/full-migration/turn2/run_notebook.py",
                ROOT / "walkthrough" / (name + ".ipynb"),
                OUT / (name + ".ipynb"),
                "--cwd",
                args.wheel_dir,
            ],
            Path("/private/tmp"),
            1800,
        )
    run(
        "temporal-proof",
        [
            RUNTIME,
            ROOT / "docs/research/full-migration/turn2/temporal_proof.py",
            OUT / "temporal-proof",
        ],
        Path("/private/tmp"),
    )
    guide = (ROOT / "docs/LEGACY_UPGRADE_GUIDE.md").read_text()
    import re

    blocks = re.findall(r"```python\n(.*?)```", guide, re.S)
    (OUT / "guide_example.py").write_text("\n\n".join(blocks))
    run("guide", [RUNTIME, OUT / "guide_example.py"], Path("/private/tmp"))

raise SystemExit(bool(failed))
