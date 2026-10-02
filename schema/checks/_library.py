"""Locate this checkout for standalone conformance commands."""

import json
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rangekeeper._schema.validation import schema_for

root = Path(__file__).resolve().parents[2]
manifest = json.loads((root / "src/rangekeeper/_schema/manifest.json").read_text())
for source, expected in manifest["sources"].items():
    if hashlib.sha256((root / source).read_bytes()).hexdigest() != expected:
        raise RuntimeError(
            "Generated artifacts are stale; run tools/schema/generate.py"
        )


def schema_json(kind):
    return json.dumps(schema_for(kind))
