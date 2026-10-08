"""Check the shared stock LinkML bundle, separate from immutable runtime records."""

from datetime import datetime
import json
from pathlib import Path
import sys

import yaml
from linkml_runtime.loaders import json_loader
from linkml_runtime.dumpers import json_dumper

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from rangekeeper.schema import native
from rangekeeper.schema.validation import validate


def normalized(value, key=None):
    # Stock LinkML omits empty/null fields and canonicalizes datetimes. Immutable
    # runtime records instead have exact-presence acceptance tests in test_records.
    if isinstance(value, dict):
        return {
            k: normalized(v, k) for k, v in value.items() if v not in (None, [], {})
        }
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if key in ("at", "started_at", "finished_at"):
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    return value


count = 0
for path in sorted((ROOT / "schema/examples").glob("*.yaml")):
    kind = path.stem.split("-")[0].capitalize()
    if kind not in ("Model", "Specification", "Run"):
        continue
    data = yaml.safe_load(path.read_text())
    record = json_loader.loads(json.dumps(data), target_class=getattr(native, kind))
    assert isinstance(record.metadata, native.Metadata)
    output = json.loads(json_dumper.dumps(record, inject_type=False))
    validate(kind, output).raise_if_invalid()
    assert normalized(output) == normalized(data), path
    count += 1
print(f"Shared native bundle: {count} fixture round trips passed")
