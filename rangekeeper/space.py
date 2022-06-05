from __future__ import annotations
from typing import Dict, List, Union
from decimal import Decimal
from pint import Quantity

from . import graph
from . import measure


class Space(graph.Element):
    def __init__(
            self,
            name: str,
            type: str,
            measurements: Dict[measure.Measure, Quantity] = None,
            events: List[graph.Event] = None,
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
            measurements: Dict[measure.Measure, Quantity] = None,
            attributes: Dict = None):
        super().__init__(name, type, measurements, attributes)
        self.num_bed = num_bed
        self.num_bath = num_bath
        self.num_balcony = num_balcony
