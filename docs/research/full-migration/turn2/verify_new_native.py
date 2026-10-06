"""Round-trip actual new temporal/scenario/policy documents through stock LinkML.

Use the pinned schema interpreter and pass a temporal-proof artifact directory.
Runtime immutable records, not stock LinkML serializers, preserve field presence.
"""

from pathlib import Path
import json
import sys
from datetime import date, datetime
from linkml_runtime.loaders import json_loader
from linkml_runtime.dumpers import json_dumper

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from rangekeeper._schema import native
from rangekeeper._schema.validation import validate


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items() if v not in (None, [], {})}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


results = []
from rangekeeper._schema import records

for path in sorted(Path(sys.argv[1]).glob("*.json")):
    if path.name == "summary.json":
        continue
    kind = (
        "Run"
        if "run" in path.stem
        else "Specification" if "specification" in path.stem else "Model"
    )
    data = json.loads(path.read_text())
    # The generated immutable boundary is the production path. Raw stock LinkML
    # normalization is an additional tooling probe, never the storage codec.
    assert getattr(records, kind).from_data(data).to_data() == data, path
    result = dict(file=path.name, immutable_roundtrip=True)
    try:
        record = json_loader.loads(json.dumps(data), target_class=getattr(native, kind))
        output = json.loads(json_dumper.dumps(record, inject_type=False))
        validate(kind, output).raise_if_invalid()
        assert normalize(output) == normalize(data), path
        result["stock_native_roundtrip"] = True
    except (ValueError, AssertionError) as error:
        result.update(stock_native_roundtrip=False, error=str(error))
    results.append(result)
summary = dict(
    immutable_passed=len(results),
    stock_native_passed=sum(r["stock_native_roundtrip"] for r in results),
    results=results,
)
Path(sys.argv[1]).parent.joinpath("native-boundary.json").write_text(
    json.dumps(summary, indent=2) + "\n"
)
print(json.dumps(summary, indent=2))
raise SystemExit(any(not r["stock_native_roundtrip"] for r in results))
