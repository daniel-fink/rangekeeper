"""Check the packaged Geometry viewer assets against their manifest hashes.

The manifest records the SHA-256 of each packaged asset (`files`) and of each
viewer source file it was built from (`sources`). Run from any directory; it
needs only the standard library.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "src/rangekeeper/visualisation/assets/geometry"
SOURCES = ROOT / "tools/geometry"


def mismatches(folder: Path, expected: dict[str, str]) -> list[str]:
    """Return the names whose file is missing or has a different hash."""
    found = []
    for name, digest in sorted(expected.items()):
        path = folder / name
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            found.append(str(path.relative_to(ROOT)))
    return found


def main() -> int:
    """Print the result and return a nonzero status on any mismatch."""
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    unlisted = sorted(
        path.name
        for path in ASSETS.iterdir()
        if path.name != "manifest.json" and path.name not in manifest["files"]
    )
    failed = mismatches(ASSETS, manifest["files"]) + mismatches(
        SOURCES, manifest["sources"]
    )
    for name in unlisted:
        print(f"Asset not in the manifest: {name}", file=sys.stderr)
    for name in failed:
        print(f"Hash differs from the manifest: {name}", file=sys.stderr)
    if failed or unlisted:
        return 1
    print(
        f"Geometry manifest: {len(manifest['files'])} assets and "
        f"{len(manifest['sources'])} sources match"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
