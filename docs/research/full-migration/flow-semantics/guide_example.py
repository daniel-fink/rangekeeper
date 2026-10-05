from datetime import date
from uuid import uuid4
from rangekeeper import Model
from rangekeeper.model import (
    Metadata, Definitions, Measure, System, Entity, Characteristics, Value,
)
from rangekeeper.model.content import encode, decode
from rangekeeper.model.flow import Stream, from_periods
from rangekeeper.temporal import make_periods
from rangekeeper.calculations import series

periods = make_periods(date(2026, 1, 1), frequency="month", count=3)
flow = from_periods(periods, (10, 0, None), units="meter")
measure = Measure(id=uuid4(), code="length", name="Length", units="meter")
reading = Value(id=uuid4(), key="delivered", kind="flow", measure=measure.id, flow=flow)
note = Value(id=uuid4(), key="source", kind="property", content=encode({"checked": False}))
owner = Entity(id=uuid4(), code="A", characteristics=Characteristics(values=(reading, note)))
model = Model.create(
    metadata=Metadata(id=uuid4(), schema_version="0.4.0"),
    definitions=Definitions(measures=(measure,)), system=System(entities=(owner,)),
)
stream = Stream.from_values(model, (reading.id,))
assert decode(model.value(note.id).content) == {"checked": False}
assert series.total(stream.flows[0], missing="skip").magnitude == 10


from rangekeeper.model.flow import resolve_date
from rangekeeper.calculations.financial import calculate_xnpv
assert flow.samples[0].date is None
assert resolve_date(flow.samples[0], timing="last_day") == date(2026, 1, 31)
paid = from_periods(periods[:1], (100,), units="AUD", dates=(date(2026, 2, 5),))
assert resolve_date(paid.samples[0], timing="start") == date(2026, 2, 5)
pv = calculate_xnpv(paid, rate=0.1, valuation_date=date(2026, 1, 1))


from rangekeeper.model.measure import Quantity
rates = from_periods(periods, (120, 120, 120), units="AUD/year")
amounts = series.integrate(rates, day_count="actual/365", units="AUD")
assert abs(series.total(amounts).magnitude - 120 * 90 / 365) < 1e-9


from rangekeeper.model.flow import from_events
from rangekeeper.calculations.financial import calculate_irr
investment = from_events([date(2026, 1, 1), date(2027, 1, 1)], (-100, 110), units="AUD")
result = calculate_irr(investment)  # optional guess=0.1
assert abs(result.rate - 0.1) < 1e-9
assert result.method == "pyxirr.xirr"


from rangekeeper.io import MemoryStore, json
from rangekeeper.model import Update
store = MemoryStore()
store.put(model)
loaded = json.loads(json.dumps(model), kind=Model)
assert loaded.to_data() == model.to_data()
reviewed_owner = Entity.from_data({**owner.to_data(), "name": "Reviewed delivery"})
revised = model.revise(Update(system=System(entities=(reviewed_owner,))))
assert revised.id != model.id and revised.metadata.previous == model.id
store.put(revised)
