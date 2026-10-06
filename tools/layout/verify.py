"""Run all layout tests with pinned solvers and retain strict acceptance evidence.

Run with the development Python environment. The output directory must be new;
each attempt retains its own toolchain, command, stdout and JUnit results. Missing
tools, a version mismatch, empty selection or any skipped test causes failure.
No solver is installed and no dependency or profile is changed by this command.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--minizinc", type=Path, help="override RK_MINIZINC and PATH for this run"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    if args.minizinc:
        environment["RK_MINIZINC"] = str(args.minizinc.expanduser().resolve())
    # Import this checkout consistently in the probe and the test process.
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["MPLBACKEND"] = "Agg"
    cache = tempfile.TemporaryDirectory(prefix="rk-layout-matplotlib-")
    environment["MPLCONFIGDIR"] = cache.name
    # Acceptance must not inherit selection or skip options from a shell profile.
    environment.pop("PYTEST_ADDOPTS", None)
    pins = json.loads(Path(__file__).with_name("toolchain.json").read_text())
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from tests.layout_support import inspect_solver; "
            "print(json.dumps({k:inspect_solver(k) for k in ('minizinc','z3')}))",
        ],
        cwd=ROOT / "src",
        env=environment,
        capture_output=True,
        text=True,
    )
    (output / "preflight.txt").write_text(probe.stdout + probe.stderr)
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "pins": pins,
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "environment": {
            key: environment.get(key)
            for key in ("RK_MINIZINC", "PYTHONPATH", "LD_LIBRARY_PATH")
        },
    }
    try:
        if probe.returncode:
            raise RuntimeError("Solver preflight failed; see preflight.txt")
        report["toolchain"] = tools = json.loads(probe.stdout)
        match = re.search(r"version (\d+\.\d+\.\d+)", tools["minizinc"]["compiler"])
        if not match or match[1] != pins["minizinc"]:
            raise RuntimeError("MiniZinc version differs from toolchain.json")
        if tools["minizinc"]["version"] != pins["cp-sat"]:
            raise RuntimeError("CP-SAT version differs from toolchain.json")
        if tools["z3"]["package"] != pins["z3-solver"]:
            raise RuntimeError("Z3 version differs from toolchain.json")
        report["pytest"] = importlib.metadata.version("pytest")
        tests = sorted((ROOT / "src/tests").glob("test_layout*.py"))
        inputs = [
            *tests,
            ROOT / "src/tests/layout_support.py",
            ROOT / "src/tests/conftest.py",
            ROOT / "src/pyproject.toml",
            *Path(__file__).parent.glob("*.py"),
            Path(__file__).with_name("toolchain.json"),
            *(ROOT / "src/rangekeeper/adapters/cytoscape/layout").glob("*.py"),
            ROOT / "src/rangekeeper/adapters/cytoscape/layout/assembly.mzn",
        ]
        report["input_sha256"] = {
            str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
            for path in inputs
        }
        command = [
            sys.executable,
            "-m",
            "pytest",
            "--require-layout-solvers",
            "--strict-markers",
            "-q",
            "-rs",
            "-p",
            "no:cacheprovider",
            f"--junitxml={output / 'results.xml'}",
            *[str(p) for p in tests],
        ]
        report.update(
            command=command, cwd=str(ROOT / "src"), tests=[p.name for p in tests]
        )
        start = time.monotonic()
        with (output / "pytest.txt").open("w") as log:
            process = subprocess.Popen(
                command,
                cwd=ROOT / "src",
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
            code = process.wait()
        report.update(exit_code=code, seconds=time.monotonic() - start)
        tree = ET.parse(output / "results.xml")
        cases = tree.findall(".//testcase")
        report["counts"] = {
            "tests": len(cases),
            "skipped": len(tree.findall(".//skipped")),
            "failures": len(tree.findall(".//failure")),
            "errors": len(tree.findall(".//error")),
        }
        if (
            code
            or not cases
            or any(report["counts"][k] for k in ("skipped", "failures", "errors"))
        ):
            raise RuntimeError(
                "Layout acceptance failed; see pytest.txt and results.xml"
            )
        report["accepted"] = True
        return 0
    except Exception as error:
        report.update(accepted=False, error=str(error))
        print(error, file=sys.stderr)
        return 1
    finally:
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        cache.cleanup()


if __name__ == "__main__":
    sys.exit(main())
