"""Check the shared stock LinkML bundle, separate from immutable runtime records."""

import importlib.util
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from linkml_runtime.dumpers import json_dumper
from linkml_runtime.loaders import json_loader

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools/schema"))
from generate import generate  # noqa: E402

from rangekeeper.schema.validation import validate  # noqa: E402

# The stock LinkML module is generated out of tree; the package does not ship it.
with TemporaryDirectory(prefix="rk-native-") as temp:
    path = Path(temp) / "native.py"
    path.write_text(generate(native_module=True)["native.py"])
    spec = importlib.util.spec_from_file_location("rk_native", path)
    native = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = native
    spec.loader.exec_module(native)


def normalized(value, key=None):
    # Stock LinkML omits empty/null fields and canonicalizes datetimes. Immutable
    # runtime records instead have exact-presence acceptance tests in test_records.
    if isinstance(value, dict):
        return {
            k: normalized(v, k) for k, v in value.items() if v not in (None, [], {})
        }
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if key == "magnitude" and type(value) in (int, float, str):
        # Stock LinkML types the Amount-or-double union as its default range,
        # string, so it writes every magnitude as text (ADR-023).
        return Decimal(str(value))
    if key in ("at", "started_at", "finished_at"):
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    return value


count = 0
for path in sorted((ROOT / "examples/schema").glob("*.yaml")):
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
