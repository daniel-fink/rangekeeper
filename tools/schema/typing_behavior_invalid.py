"""Each call must fail static checking; this file is never executed."""

from uuid import uuid4

from datetime import date
from rangekeeper.model.flux import Flow, Movement
from rangekeeper.model.distribution import Distribution

movement = Movement(id=uuid4(), key="event", date=date(2026, 1, 1))
movement.replace(magnitude="wrong")
movement.replace(unknown=1)
movement.replace(date="2026-01-01")
movement.number = 2
Flow.from_events([date(2026, 1, 1)], [1], units="m").replace(movements=(1,))
Distribution.pert(mode="wrong")
