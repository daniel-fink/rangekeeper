from __future__ import annotations
from typing import Dict, List, Union
from decimal import Decimal
from pint import Quantity

try:
    from graph import Element, Event
    from measure import Measure
except:
    from modules.rangekeeper.graph import Element, Event
    from modules.rangekeeper.measure import Measure


class Space(Element):
    def __init__(
            self,
            name: str,
            type: str,
            measurements: Dict[Measure, Quantity] = None,
            events: List[Event] = None,
            attributes: Dict = None):
        super().__init__(
            name=name,
            type=type,
            measurements=measurements,
            events=events,
            attributes=attributes)


class Apartment(Space):
    num_bed: int
    num_bath: Decimal
    num_balcony: int

    def __init__(
            self,
            name: str,
            type: str,
            num_bed: int,
            num_bath: Decimal,
            num_balcony: int,
            measurements: Dict[Measure, Quantity] = None,
            attributes: Dict = None):
        super().__init__(name, type, measurements, attributes)
        self.num_bed = num_bed
        self.num_bath = num_bath
        self.num_balcony = num_balcony
