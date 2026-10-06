"""Check final retirement evidence without modifying runtime or private inputs.

This is an acceptance helper for the recorded local checkout and wheel. It reads
private source hashes, not payload contents, into its report. It never stages,
commits, pushes, publishes or changes the user's environments.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
WHEEL = Path("/private/tmp/rk-turn4-wheel/wheel/rangekeeper-0.8.71-py3-none-any.whl")
SITE = WHEEL.parent.parent / "site"
BASELINE = json.loads((OUT / "baseline.json").read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


for name, expected in BASELINE["protected"].items():
    assert digest(Path(name)) == expected, name
removed = json.loads((OUT / "removed-files.json").read_text())
allowed_inputs = {item["path"] for item in removed} | {
    "src/rangekeeper/__init__.py", "src/tests/models/__init__.py",
    "src/tests/test_immutable_graph.py", "src/tests/test_calculation_equivalence.py",
    "src/tests/test_projections.py", "src/tests/test_dynamics.py",
    "src/tests/test_modules.py", "tools/schema/verify_install.py",
}
changed_inputs = {}
for name, expected in BASELINE["inputs"].items():
    path = ROOT / name
    actual = digest(path) if path.exists() else None
    if actual != expected:
        assert name in allowed_inputs, name
        changed_inputs[name] = {"before": expected, "after": actual}

repositories = {}
for name, before in BASELINE["repositories"].items():
    root = Path(before["root"])
    head = git(root, "rev-parse", "HEAD")
    assert head == before["head"], name
    assert not git(root, "diff", "--cached", "--name-only"), name
    if name == "layout":
        assert not git(root, "status", "--porcelain"), name
    else:
        assert git(root, "rev-parse", "@{upstream}") == head, name
    repositories[name] = {
        "head": head,
        "branch": git(root, "branch", "--show-current"),
        "status": git(root, "status", "--short"),
        "index_empty": True,
    }

for item in removed:
    assert not (ROOT / item["path"]).exists(), item["path"]
allowed_runtime = {item["path"] for item in removed} | {"src/rangekeeper/__init__.py"}
runtime_changes = set(git(ROOT, "diff", "--name-only", "HEAD", "--", "src/rangekeeper").splitlines())
assert runtime_changes <= allowed_runtime, runtime_changes - allowed_runtime
assert not git(ROOT, "diff", "--name-only", "HEAD", "--", "grasshopper", "schema", ":(glob)walkthrough/*.ipynb")

with zipfile.ZipFile(WHEEL) as archive:
    packaged = [name for name in archive.namelist() if name.startswith("rangekeeper/") and not name.endswith("/")]
    for name in packaged:
        assert (ROOT / "src" / name).read_bytes() == archive.read(name), name
for name in ("README.md", "pyproject.toml"):
    assert (ROOT / "src" / name).read_bytes() == (WHEEL.parent.parent / "stage" / name).read_bytes(), name

notebooks = []
for source in sorted((ROOT / "walkthrough").glob("*.ipynb")):
    executed = ROOT / "walkthrough/_build/jupyter_execute" / source.name
    original = json.loads(source.read_text())
    document = json.loads(executed.read_text())
    assert [c["source"] for c in original["cells"]] == [c["source"] for c in document["cells"]], source.name
    assert not any(output.get("output_type") == "error" for c in document["cells"] for output in c.get("outputs", [])), source.name
    assert all(c.get("execution_count") is not None for c in document["cells"] if c["cell_type"] == "code" and "".join(c["source"]).strip()), source.name
    notebooks.append({"name": source.name, "source_sha256": digest(source), "executed_sha256": digest(executed)})

bootstrap = Path("/private/tmp/rk-turn4-project-bootstrap")
for name, expected in json.loads((bootstrap / "source-hashes.json").read_text()).items():
    assert digest(bootstrap / name) == expected, name
mandarin = json.loads((bootstrap / "mandarin-review.ipynb").read_text())
assert not any(o.get("output_type") == "error" for c in mandarin["cells"] for o in c.get("outputs", []))
assert sum(c["cell_type"] == "code" and c.get("execution_count") is not None for c in mandarin["cells"]) == 5

ledger = json.loads((OUT / "ledger.json").read_text())
for consumer in ledger["consumers"]:
    root = ROOT if consumer["scope"] == "repository" else Path(BASELINE["repositories"]["projects"]["root"])
    path = root / consumer["path"]
    assert (digest(path) if path.exists() else None) == consumer["current_sha256"], path

# Validate only the new report's relative file links; old historical references
# remain historical and are not silently rewritten by this evidence check.
for document in [ROOT / "docs/FULL_MIGRATION_TURN4.md", *OUT.glob("*.md")]:
    for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
        if not target.startswith(("https:", "http:", "#")):
            assert (document.parent / target.split("#")[0]).exists(), (document, target)

environment_code = """import importlib.metadata as m, importlib.util, json, sys
spec = importlib.util.find_spec('rangekeeper')
print(json.dumps({'python': sys.version, 'executable': sys.executable,
'rangekeeper': None if spec is None else spec.origin,
'packages': {d.metadata['Name']: d.version for d in m.distributions()}}))
"""
environments = {}
for name, executable in (
    ("runtime", "/private/tmp/rk-full-runtime/bin/python"),
    ("schema", "/private/tmp/rk-probe-audit-venv/bin/python"),
    ("core", "/private/tmp/rk-turn4-core-venv/bin/python"),
    ("projects", "/private/tmp/rk-turn4-project-venv/bin/python"),
):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    if name == "runtime":
        env["PYTHONPATH"] = str(SITE)
    environments[name] = json.loads(subprocess.check_output([executable, "-c", environment_code], cwd="/private/tmp", env=env, text=True))
(OUT / "environment-final.json").write_text(json.dumps(environments, indent=2) + "\n")

suite = ET.parse(OUT / "full-suite.xml").find("testsuite")
assert suite is not None
counts = {key: int(suite.attrib[key]) for key in ("tests", "failures", "errors", "skipped")}
assert counts == {"tests": 1082, "failures": 0, "errors": 0, "skipped": 24}, counts
report = {
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "repositories": repositories,
    "protected_files_unchanged": len(BASELINE["protected"]),
    "verification_inputs_unchanged": len(BASELINE["inputs"]) - len(changed_inputs),
    "intentionally_changed_verification_inputs": changed_inputs,
    "wheel": str(WHEEL), "wheel_sha256": digest(WHEEL),
    "packaged_files_equal_to_source": len(packaged),
    "canonical_runtime_csharp_and_source_notebooks_unchanged": True,
    "removed_files": len(removed), "notebooks": notebooks,
    "mandarin_code_cells_executed": 5,
    "suite": counts,
    "symbols": dict(Counter(row["status"] for row in ledger["symbols"])),
    "consumers": len(ledger["consumers"]),
    "open_gate": "Official Windows connector acceptance; predecessor dependency group retained",
    "publication": "Only the earlier authorised paired Turn 3 checkpoint was committed and pushed; Turn 4 is uncommitted",
}
(OUT / "final-state.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: value for key, value in report.items() if key not in {"repositories", "notebooks", "intentionally_changed_verification_inputs"}}, indent=2))
