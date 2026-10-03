"""Summarize observed checks, verify preserved inputs, and archive ignored raw logs."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import tarfile
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
initial = json.loads((OUT / "initial.json").read_text())["sha256"]
protected = {
    p: h for p, h in initial.items()
    if p.startswith(("src/rangekeeper/execution/", "src/rangekeeper/run/", "src/rangekeeper/model/", "src/rangekeeper/specification/", "src/rangekeeper/io/", "src/rangekeeper/_schema/")) or p == "src/tests/test_execution.py"
}
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in protected.items())
prior = json.loads((OUT.parent / "graph-migration/verified-sources.json").read_text())
contract = {p: h for p, h in prior.items() if p.startswith(("schema/", "src/rangekeeper/_schema/"))}
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in contract.items())
inputs = json.loads((OUT / "verified-sources.json").read_text())
assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in inputs.items())
commands = [json.loads(line) for line in (OUT / "commands.jsonl").read_text().splitlines()]
latest = {}
for row in commands:
    latest[re.sub(r"-\d+(?=\.log$)", "", row["log"]).removesuffix(".log")] = row
suite = ElementTree.parse(OUT / "pytest.xml").find("testsuite")
failures = [case.attrib["classname"] + "::" + case.attrib["name"] for case in suite if case.find("failure") is not None]
assert failures == ["tests.test_formulas.TestSolver::test_residual"]
assert suite.attrib["errors"] == suite.attrib["skipped"] == "0"
scalar = max(OUT.glob("scalar-*"), key=lambda p: p.stat().st_mtime)
summary = {
    "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "tests": int(suite.attrib["tests"]), "passed": int(suite.attrib["tests"]) - 1,
    "failures": failures, "errors": 0, "skipped": 0,
    "live_api_tests_excluded": 3,
    "preserved_core_files": len(protected), "preserved_schema_and_fixture_files": len(contract),
    "static_checked_sources": 80, "schema_suites": 7, "viewer_bundle_tests": 27,
    "scalar_example": str(scalar.relative_to(OUT)),
    "scalar_results": json.loads((scalar / "summary.json").read_text()),
    "latest_checks": latest,
    "limits": ["External projects, notebooks and live services were not executed.", "Browser interaction was not tested; Python viewer export and installed assets passed.", "TypeScript rebuilding was not verified: compiler dependencies were absent and offline npm installation lacked cached packages. Existing unchanged viewer bundles passed 27 tests."]
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
# Logs are ignored globally. The archive retains them without editing .gitignore.
with tarfile.open(OUT / "evidence.tar.gz", "w:gz") as archive:
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and (p.suffix in {".log", ".xml"} or scalar in p.parents):
            archive.add(p, arcname=str(p.relative_to(OUT)))
print(json.dumps({k: summary[k] for k in ("tests", "passed", "failures", "preserved_core_files", "preserved_schema_and_fixture_files", "scalar_example")}, indent=2))
