"""Check native LinkML date serialization against the immutable public boundary."""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from rangekeeper._schema.native import Flow as NativeFlow
from rangekeeper._schema.records import Flow
from linkml_runtime.loaders import json_loader
from linkml_runtime.dumpers import json_dumper

for coordinate in (
    {"date": "2026-02-05"},
    {"period": {"start": "2026-01-01", "end": "2026-02-01"}},
    {"period": {"start": "2026-01-01", "end": "2026-02-01"}, "date": "2026-02-05"},
):
    data = {"units": "AUD", "basis": "movement",
            "samples": [{"key": "sample", "magnitude": 100, **coordinate}]}
    native = json_loader.loads(json.dumps(data), target_class=NativeFlow)
    assert json_dumper.to_dict(native) == data
    assert Flow.from_data(json_dumper.to_dict(native)).to_data() == data
print("Three native/public date-coordinate round trips passed")
