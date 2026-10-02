"""Compare Turn 3 inputs without modifying Git or restoring working files."""

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
initial = json.loads((OUT / "initial.json").read_text())
backup = Path(initial["backup"])


def digest(path):
    """Represent removed files explicitly rather than silently skipping them."""
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


changed = sorted(
    name for name, before in initial["files"].items()
    if digest(ROOT / name) != before
)
allowed = {
    "src/rangekeeper/references.py", "src/rangekeeper/__init__.py",
    "src/rangekeeper/errors.py", "src/rangekeeper/specification/composition.py",
    "src/rangekeeper/specification/validation.py", "src/rangekeeper/run/__init__.py",
    "src/rangekeeper/run/_validation.py", "src/rangekeeper/run/validation.py",
    "tools/schema/typecheck.py", "tools/schema/verify_install.py",
    "src/tests/test_records.py", ".github/workflows/schema-records.yml",
    "src/pyproject.toml", "src/uv.lock", "README.md", "src/README.md", "schema/README.md",
}
unexpected = [name for name in changed if name not in allowed and not name.startswith("docs/")]
verified = json.loads((OUT / "final-fingerprints.json").read_text())
after_verification = [name for name, before in verified.items() if digest(ROOT / name) != before]


def locked_versions(path):
    """Compare package identities only; optional-extra metadata may change."""
    return sorted(re.findall(
        r'\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"', path.read_text()
    ))


before_versions = locked_versions(backup / "src/uv.lock")
after_versions = locked_versions(ROOT / "src/uv.lock")
before_test = (backup / "src/tests/test_records.py").read_text()
expected_test = before_test.replace(
    "from rangekeeper.run.validation import validate as validate_run",
    "from rangekeeper.run.validation import validate_records as validate_run",
)
test_import_only = (ROOT / "src/tests/test_records.py").read_text() == expected_test
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
index = subprocess.check_output(["git", "ls-files", "--stage"], cwd=ROOT, text=True)
before_index, after_index = set(initial["index"].splitlines()), set(index.splitlines())
report = {
    "head": head, "head_unchanged": head == initial["head"],
    "starting_files_checked": len(initial["files"]),
    "changed_starting_files": changed, "unexpected_changes": unexpected,
    "verified_source_files_checked": len(verified),
    "changes_after_verification": after_verification,
    "lock_package_versions_unchanged": before_versions == after_versions,
    "locked_packages": len(after_versions),
    "existing_test_change_is_import_only": test_import_only,
    "index_unchanged": index == initial["index"],
    "index_entries_removed": sorted(before_index - after_index),
    "index_entries_added": sorted(after_index - before_index),
    "note": "Index changes are observed only; no staging or restoration is performed.",
}
(OUT / "preservation.json").write_text(json.dumps(report, indent=2) + "\n")
assert report["head_unchanged"]
assert not unexpected, unexpected
assert not after_verification, after_verification
assert before_versions == after_versions
assert test_import_only
print(f"Preserved scope: {len(initial['files'])} starting files; {len(verified)} verified source files.")
print(f"Lock versions unchanged: {len(after_versions)} packages; existing assertions unchanged.")
print(f"Observed external index changes: {len(before_index - after_index)} removed, {len(after_index - before_index)} added.")
