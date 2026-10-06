"""Capture final verification inputs, protected hashes and installed source equality."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
WHEEL = Path("/private/tmp/rk-turn2-final-wheel/site/rangekeeper")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


baseline = json.loads((OUT / "baseline/state.json").read_text())
protected = (".gitignore", "src/uv.sync-conflict-20261005-170953-H3RQGJU.lock")
assert all(digest(ROOT / name) == baseline["sha256"][name] for name in protected)
assert (
    subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    == baseline["head"]
)
assert not subprocess.check_output(
    ["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True
).strip()
paths = subprocess.check_output(
    [
        "rg",
        "--files",
        "schema",
        "src/rangekeeper",
        "src/tests",
        "tools",
        "walkthrough",
        "-g",
        "*.py",
        "-g",
        "*.yaml",
        "-g",
        "*.json",
        "-g",
        "*.ipynb",
        "-g",
        "*.toml",
        "-g",
        "!**/node_modules/**",
        "-g",
        "!**/client/**",
    ],
    cwd=ROOT,
    text=True,
).splitlines()
paths += ["src/pyproject.toml", "src/uv.lock", *protected]
sha = {
    name: digest(ROOT / name) for name in sorted(set(paths)) if (ROOT / name).is_file()
}
checked = []
for name in sha:
    if name.startswith("src/rangekeeper/"):
        target = WHEEL / Path(name).relative_to("src/rangekeeper")
        if name.endswith(".py") or "/_schema/" in name:
            assert target.is_file() and digest(target) == sha[name], name
            checked.append(name)
suite = ET.parse(OUT / "acceptance/pytest-local.xml").getroot().find("testsuite")
assert int(suite.attrib["failures"]) == 0 and int(suite.attrib["errors"]) == 0
state = dict(
    captured_at=datetime.now(timezone.utc).isoformat(),
    branch=subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip(),
    head=baseline["head"],
    status=subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
    protected={p: sha[p] for p in protected},
    sha256=sha,
    installed_files_identical=len(checked),
    installed_site=str(WHEEL),
    pytest=suite.attrib,
    instructions="User-supplied AGENTS.md instructions: follow ASD-STE100 principles in replies; no on-disk repository AGENTS.md was found.",
    schema_environment="LinkML 1.11.1 / linkml-runtime 1.11.1 / jsonschema 4.26.0; see environments.json",
    notebook_overrides=dict(
        PYTHONPATH=str(WHEEL.parent),
        RK_SCENARIO_COUNT="4",
        RK_SCENARIO_WORKERS="1",
        MPLCONFIGDIR="/private/tmp/rk-mpl-cache",
    ),
)
(OUT / "final-state.json").write_text(json.dumps(state, indent=2) + "\n")
print(
    json.dumps(
        dict(
            tests=suite.attrib["tests"],
            failures=suite.attrib["failures"],
            protected_unchanged=True,
            installed_files_identical=len(checked),
            input_hashes=len(sha),
        )
    )
)
