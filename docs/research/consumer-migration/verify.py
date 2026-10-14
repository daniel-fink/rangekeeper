"""Reproduce the Model consumer checkpoint with explicit environments and retained output."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument(
    "--schema-python", default="/private/tmp/rk-probe-audit-venv/bin/python"
)
parser.add_argument(
    "--runtime-python", default="/private/tmp/rk-scalar-runtime/bin/python"
)
parser.add_argument("--typecheck-path", default="/private/tmp/rk-record-typecheck")
parser.add_argument("--only", action="append", help="Run selected checks after a recorded earlier pass")
args = parser.parse_args()
env = dict(
    os.environ,
    PYTHONDONTWRITEBYTECODE="1",
    PYSTOW_HOME="/private/tmp/rk-domain-migration-pystow",
    MPLBACKEND="Agg",
    MPLCONFIGDIR="/private/tmp/rk-mpl-cache",
)


def run(name, argv, *, cwd=ROOT, extra=None, expected=0):
    if args.only and name not in args.only:
        return
    path = OUT / f"{name}.log"
    if path.exists():
        path = OUT / f"{name}-{time.time_ns()}.log"
    current = {**env, **(extra or {})}
    started = time.monotonic()
    with path.open("w") as output:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=current,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=1200,
        )
    entry = dict(
        argv=argv,
        cwd=str(cwd),
        exit_code=result.returncode,
        log=path.name,
        elapsed_seconds=time.monotonic() - started,
        environment={
            key: current.get(key)
            for key in (
                "PYTHONPATH",
                "PYTHONDONTWRITEBYTECODE",
                "PYSTOW_HOME",
                "MPLBACKEND",
                "MPLCONFIGDIR",
            )
        },
    )
    with (OUT / "commands.jsonl").open("a") as output:
        output.write(json.dumps(entry) + "\n")
    print(name, result.returncode, path.name, flush=True)
    assert result.returncode == expected, path.read_text()[-6000:]


run(
    "environment",
    [
        args.runtime_python,
        "-c",
        "import sys,platform,importlib.metadata as m,json,rangekeeper;print(sys.version);print(platform.platform());print(rangekeeper.__file__);print(json.dumps({d.metadata['Name']:d.version for d in m.distributions()},sort_keys=True))",
    ],
    cwd=ROOT / "src",
)
run(
    "schema-environment",
    [
        args.schema_python,
        "-c",
        "import sys,importlib.metadata as m,json;print(sys.version);print(json.dumps({name:m.version(name) for name in ('linkml','linkml-runtime','jsonschema','PyYAML')},sort_keys=True))",
    ],
)
run("generation", [args.schema_python, "tools/schema/generate.py", "--check"])
run(
    "typing",
    [args.schema_python, "tools/schema/typecheck.py"],
    extra={"PYTHONPATH": args.typecheck_path},
)
run("native", [args.schema_python, "tools/schema/verify_native.py"])
for suite in (
    "validate",
    "native_roundtrip",
    "expressions",
    "formulations",
    "models",
    "specifications",
    "runs",
):
    run("schema-" + suite, [args.schema_python, "schema/checks/" + suite + ".py"])
run(
    "installed",
    [
        args.schema_python,
        "tools/schema/verify_install.py",
        "--runtime-python=" + args.runtime_python,
        "--execution-python=" + args.runtime_python,
        "--workflow-python=" + args.runtime_python,
    ],
)
run(
    "pytest-inventory",
    [
        args.runtime_python,
        "-m",
        "pytest",
        "tests",
        "--collect-only",
        "-q",
        "--ignore=tests/test_api.py",
    ],
    cwd=ROOT / "src",
)
run(
    "viewer-tests",
    ["npm", "test"],
    cwd=ROOT / "src/rangekeeper/adapters/cytoscape/client",
)
run(
    "workflow-scalar",
    [
        args.runtime_python,
        str(ROOT / "tools/workflow/scalar.py"),
        "--output",
        str(OUT / ("scalar-" + str(time.time_ns()))),
    ],
    cwd=ROOT / "src",
    extra={"PYTHONPATH": str(ROOT / "src")},
)
run(
    "pytest",
    [
        args.runtime_python,
        "-m",
        "pytest",
        "tests",
        "-q",
        "--tb=short",
        "--ignore=tests/test_api.py",
        "-o",
        "cache_dir=/private/tmp/rk-consumers-pytest-cache",
        "--junitxml=" + str(OUT / "pytest.xml"),
    ],
    cwd=ROOT / "src",
    expected=1,
)
xml = ElementTree.parse(OUT / "pytest.xml")
failures = sorted(
    (case.attrib["classname"], case.attrib["name"])
    for case in xml.findall(".//testcase")
    if case.find("failure") is not None
)
assert failures == [
    ("tests.test_formulas.TestSolver", "test_residual"),
], failures
assert not xml.findall(".//error") and not xml.findall(".//skipped")
sources = [
    *ROOT.glob("schema/*.yaml"),
    *ROOT.glob("schema/examples/*"),
    *ROOT.glob("schema/checks/*.py"),
    *ROOT.glob("src/rangekeeper/**/*.py"),
    *ROOT.glob("src/rangekeeper/_schema/*.json"),
    *ROOT.glob("tools/schema/*"),
    *ROOT.glob("tools/execution/*"),
    *ROOT.glob("tools/workflow/*"),
    *ROOT.glob("src/rangekeeper/adapters/cytoscape/assets/**/*"),
    *ROOT.glob("src/rangekeeper/adapters/cytoscape/client/**/*.ts"),
    *ROOT.glob("src/tests/*.py"),
    ROOT / "src/pyproject.toml",
    ROOT / "src/uv.lock",
    ROOT / ".github/workflows/schema-records.yml",
]
(OUT / "verified-sources.json").write_text(
    json.dumps(
        {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
            if path.is_file()
        },
        indent=2,
    )
    + "\n"
)
print(
    "Consumer checkpoint verified; precisely the known solver baseline failure remains. Evidence:",
    OUT,
)
