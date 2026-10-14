"""Prove explicit legacy access and canonical conversion from the same wheel."""

from pathlib import Path
import importlib.util
import sys

import rangekeeper
from rangekeeper.migration import convert_graph
from rangekeeper.graph import View

ROOT = Path(__file__).resolve().parents[4]
assert "rk-legacy-isolation-wheel/site" in rangekeeper.__file__, rangekeeper.__file__
text = (ROOT / "src/tests/fixtures/migration/graph-v1.json").read_text()
model = convert_graph(text).model
assert model is not None and len(View(model).entities) == 2
assert not any(name.startswith("rangekeeper.legacy") for name in sys.modules)
assert importlib.util.find_spec("rangekeeper.api") is None
assert importlib.util.find_spec("rangekeeper.measure") is None

from rangekeeper.legacy import graph, measure, api
from rangekeeper.legacy.graph.adapter import json

old = json.loads(text)
assert len(old.entities) == 2
assert old.entities[1].measurements["length"].quantity == 0 * measure.Index.registry.meter
assert json.dumps(json.loads(json.dumps(old))) == json.dumps(old)
table = graph.table.Table.from_view(old.view(), fields=("name",))
assert len(table.rows) == 2
assert api.Speckle.__module__ == "rangekeeper.legacy.api"
assert graph.Graph.__module__ == "rangekeeper.legacy.graph.graph"
assert not hasattr(rangekeeper.graph, "Graph")
print("Installed canonical conversion, explicit legacy Graph/Measure/API import, old wire roundtrip and table passed")
print("No service call or Windows connector acceptance was performed")
