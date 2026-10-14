"""Verify protected inputs and the exact wheel against the current source tree.

Read-only except for detached hash reports in this evidence directory. Private
payloads are never copied. Invoke after code and consumer acceptance finish.
"""

from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
p = argparse.ArgumentParser()
p.add_argument(
    "--wheel",
    type=Path,
    default=Path(
        "/private/tmp/rk-turn3-complete-wheel/wheel/rangekeeper-0.8.71-py3-none-any.whl"
    ),
)
a = p.parse_args()
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
baseline = json.loads((OUT / "baseline.json").read_text())
protected = dict(baseline["preserved"])
for relative in (
    "grasshopper/Tests/exampleDesign.3dm",
    "grasshopper/Tests/exampleDesignConfig.ghx",
):
    protected[str(ROOT / relative)] = baseline["rk"]["tracked"][relative]
checks = [
    {"path": name, "unchanged": Path(name).is_file() and sha(Path(name)) == digest}
    for name, digest in protected.items()
]
assert all(item["unchanged"] for item in checks), [
    item for item in checks if not item["unchanged"]
]
(OUT / "preservation-final.json").write_text(
    json.dumps({"status": "passed", "files": len(checks), "checks": checks}, indent=2)
    + "\n"
)
with zipfile.ZipFile(a.wheel) as wheel:
    names = wheel.namelist()
    mismatches = [
        name
        for name in names
        if name.startswith("rangekeeper/")
        and (ROOT / "src" / name).is_file()
        and wheel.read(name) != (ROOT / "src" / name).read_bytes()
    ]
    assert not mismatches, mismatches
    for required in (
        "rangekeeper/adapters/cytoscape/assets/viewer.js",
        "rangekeeper/adapters/speckle/contract.json",
        "rangekeeper/workflow/workbench.py",
        "rangekeeper/migration/layout.py",
    ):
        assert required in names, required
(OUT / "artifact-final.json").write_text(
    json.dumps(
        {
            "wheel": a.wheel.name,
            "sha256": sha(a.wheel),
            "packaged_files": len(names),
            "source_matches": True,
        },
        indent=2,
    )
    + "\n"
)
repositories = {}
for name in ("rk", "projects", "layout"):
    folder = baseline[name]["root"]
    git = lambda *args: subprocess.check_output(
        ["git", "-C", folder, *args], text=True
    ).strip()
    assert git("rev-parse", "HEAD") == baseline[name]["head"]
    assert not git("diff", "--cached", "--name-only"), folder
    if name == "layout":
        assert git("status", "--short") == baseline[name]["status"]
        for relative, digest in baseline[name]["tracked"].items():
            assert sha(Path(folder) / relative) == digest, relative
    repositories[name] = {
        "head": git("rev-parse", "HEAD"),
        "status": git("status", "--short"),
    }
(OUT / "closing-state.json").write_text(json.dumps(repositories, indent=2) + "\n")
print(
    f"Protected {len(checks)} files; wheel content matches source; HEADs unchanged and indexes empty"
)
