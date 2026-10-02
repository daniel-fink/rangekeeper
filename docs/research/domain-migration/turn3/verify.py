"""Reproduce Turn 3 checks without changing the repository's Python environment."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--schema-python", default="/private/tmp/rk-probe-audit-venv/bin/python")
parser.add_argument("--runtime-python", default="/private/tmp/rk-domain-runtime/bin/python")
parser.add_argument("--typecheck-path", default="/private/tmp/rk-record-typecheck")
args = parser.parse_args()
env = dict(os.environ, PYSTOW_HOME="/private/tmp/rk-domain-migration-pystow",
           MPLBACKEND="Agg", MPLCONFIGDIR="/private/tmp/rk-mpl-cache", PYTHONDONTWRITEBYTECODE="1")


def run(name, argv, cwd=ROOT, extra=None, expected=0):
    current = {**env, **(extra or {})}
    path = OUT / (name + ".log")
    if path.exists():
        path = OUT / (name + "-" + str(time.time_ns()) + ".log")
    start = time.monotonic()
    with path.open("w") as stream:
        result = subprocess.run([str(arg) for arg in argv], cwd=cwd, env=current,
                                stdout=stream, stderr=subprocess.STDOUT, timeout=900)
    record = dict(argv=argv, cwd=str(cwd), exit_code=result.returncode,
                  elapsed_seconds=round(time.monotonic()-start, 3), log=path.name,
                  environment={key:current.get(key) for key in
                  ("PYSTOW_HOME", "MPLBACKEND", "MPLCONFIGDIR", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH")})
    with (OUT / "verification-commands.jsonl").open("a") as stream:
        stream.write(json.dumps(record) + "\n")
    print(name, result.returncode, path.name, flush=True)
    assert result.returncode == expected, path.read_text()[-5000:]


run("environment-final", [args.schema_python, "-c", "import sys,importlib.metadata as m,json;print(sys.version);print(json.dumps({d.metadata['Name']:d.version for d in m.distributions()},sort_keys=True))"])
run("runtime-environment-final", [args.runtime_python, "-c", "import sys,platform,importlib.metadata as m,json,rangekeeper;print(sys.version);print(platform.platform());print(rangekeeper.__file__);print(json.dumps({d.metadata['Name']:d.version for d in m.distributions()},sort_keys=True))"], ROOT / "src")
run("regenerate-check", [args.schema_python, "tools/schema/generate.py", "--check"])
run("typing-verified", [args.schema_python, "tools/schema/typecheck.py"], extra={"PYTHONPATH": args.typecheck_path})
run("native-verified", [args.schema_python, "tools/schema/verify_native.py"])
run("installed-verified", [args.schema_python, "tools/schema/verify_install.py", "--runtime-python=" + args.runtime_python])
for suite in ("validate", "native_roundtrip", "expressions", "formulations", "models", "specifications", "runs"):
    run("schema-" + suite + "-final", [args.schema_python, "schema/checks/" + suite + ".py"])
run("pytest-final", [args.runtime_python, "-m", "pytest", "tests", "-q", "--tb=short",
    "--ignore=tests/test_api.py", "-o", "cache_dir=/private/tmp/rk-record-pytest-cache",
    "--junitxml=" + str(OUT / "pytest-final.xml")], ROOT / "src", expected=1)
import xml.etree.ElementTree as ET
tree = ET.parse(OUT / "pytest-final.xml")
failures = sorted((case.attrib["classname"], case.attrib["name"])
                  for case in tree.findall(".//testcase") if case.find("failure") is not None)
assert failures == [
    ("tests.test_adapters", "test_supported_adapter_and_table_surfaces_are_explicit"),
    ("tests.test_formulas.TestSolver", "test_residual"),
], failures
sources = [*ROOT.glob("schema/*.yaml"), *ROOT.glob("schema/examples/*"),
           *ROOT.glob("src/rangekeeper/_schema/*"), *ROOT.glob("src/rangekeeper/**/*.py"),
           *ROOT.glob("schema/checks/*.py"), *ROOT.glob("tools/schema/*"),
           ROOT / "src/tests/test_records.py", ROOT / "src/tests/test_domain_model.py",
           ROOT / "src/tests/test_domain_specification.py", ROOT / "src/tests/test_validation_composition.py", ROOT / "src/tests/test_domain_run.py", ROOT / "src/tests/test_domain_io.py", ROOT / "src/rangekeeper/_currencies.json", ROOT / ".github/workflows/schema-records.yml",
           ROOT / "src/pyproject.toml", ROOT / "src/uv.lock"]
(OUT / "final-fingerprints.json").write_text(json.dumps({str(path.relative_to(ROOT)):
    hashlib.sha256(path.read_bytes()).hexdigest() for path in sources if path.is_file()}, indent=2) + "\n")
print("All Turn 3 checks passed, with precisely the two known baseline failures")
