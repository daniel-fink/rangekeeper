"""Exercise a normally installed core wheel with no optional numerical libraries."""

from datetime import date
import importlib.metadata
import importlib.util
import json
from uuid import uuid4
import rangekeeper
from rangekeeper import Model
from rangekeeper.model import Metadata, Definitions, Measure, System, Entity, Characteristics, Value
from rangekeeper.model.flow import from_events
from rangekeeper.graph import View
from rangekeeper.graph.projection import ValueColumn, to_table
from rangekeeper.io import MemoryStore, json as codec
from rangekeeper.model.measure import Quantity

assert "rk-turn4-core-venv" in rangekeeper.__file__, rangekeeper.__file__
optional = (
    "numpy", "scipy", "pandas", "polars", "matplotlib", "plotly", "pyvis",
    "specklepy", "networkx", "moneyed", "pyomo", "highspy", "pyxirr", "numba",
    "multiprocess", "pytest", "black", "linkml", "linkml_runtime",
)
for name in optional:
    assert importlib.util.find_spec(name) is None, name
measure = Measure(id=uuid4(), code="length", name="Length", units="meter")
value = Value(id=uuid4(), key="length", kind="measurement", measure=measure.id,
              quantity=Quantity(magnitude=100, units="centimeter"))
flow = Value(id=uuid4(), key="deliveries", kind="flow", measure=measure.id,
             flow=from_events((date(2026, 1, 1),), (0,), units="meter"))
owner = Entity(id=uuid4(), characteristics=Characteristics(values=(value, flow)))
model = Model.create(metadata=Metadata(id=uuid4(), schema_version="0.5.0"),
                     definitions=Definitions(measures=(measure,)), system=System(entities=(owner,)))
store = MemoryStore()
store.put(model)
assert codec.loads(codec.dumps(model), kind=Model).to_data() == model.to_data()
assert store.load_model(model.id).value(flow.id).flow.movements[0].magnitude == 0
projected = to_table(View(model), columns=(ValueColumn("length", "length", units="meter"),))
assert projected.rows[0].values["length"] == 1
for name in optional:
    assert importlib.util.find_spec(name) is None, name
print(json.dumps({
    "status": "passed", "import": rangekeeper.__file__, "absent_optional": optional,
    "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
}, indent=2))
