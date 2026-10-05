"""Verify native and immutable Movement records and the Flow.movements wire field."""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from rangekeeper._schema.native import Flow as NativeFlow
from rangekeeper._schema.records import Flow
from rangekeeper.errors import ValidationError
from linkml_runtime.loaders import json_loader
from linkml_runtime.dumpers import json_dumper

for coordinate in (
    {"date": "2026-02-05"},
    {"period": {"start": "2026-01-01", "end": "2026-02-01"}},
    {"period": {"start": "2026-01-01", "end": "2026-02-01"}, "date": "2026-02-05"},
):
    data = {"units": "AUD", "movements": [{"key": "movement", "magnitude": 100, **coordinate}]}
    native = json_loader.loads(json.dumps(data), target_class=NativeFlow)
    assert json_dumper.to_dict(native) == data
    assert Flow.from_data(json_dumper.to_dict(native)).to_data() == data
    for field in ("basis", "kind"):
        try:
            Flow.from_data({**data, field: "movement"})
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Flow unexpectedly accepted {field}")
print("Three native/public Flow round trips passed; basis/kind rejected")
