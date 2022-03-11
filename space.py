from __future__ import annotations
from typing import Dict, List, Union
from decimal import Decimal
from pint import Quantity

try:
    from measure import Measure
except:
    from modules.rangekeeper.measure import Measure


class Type:
    name: str
    parent: Type
    children: [Type]

    def __init__(
            self,
            name: str,
            parent: Type = None,
            children: List[Type] = None):
        self.name = name
        if parent is not None:
            self.set_parent(parent)
        if children is not None:
            self.set_children(children)
        else:
            self.children = []

    def __str__(self):
        result = self.name
        try:
            result = self.parent.__str__() + '.' + result
        except AttributeError:
            pass
        return result

    def set_parent(
            self,
            parent: Type):
        try:
            self.parent.children.remove(self)
        except AttributeError:
            pass
        self.parent = parent
        parent.children.append(self)

    def set_children(
            self,
            children: List[Type]):
        for child in children:
            child.set_parent(self)


class Space:
    name: str
    type: Type
    attributes: Dict
    measurements: Dict[Measure, Quantity]

    def __init__(
            self,
            name: str,
            type: Type,
            measurements: Dict[Measure, Quantity] = None,
            attributes: Dict = None):
        self.name = name
        self.type = type
        self.attributes = attributes
        self.measurements = measurements


class Apartment(Space):
    num_bed: int
    num_bath: Decimal
    num_balcony: int

    def __init__(self,
                 name: str,
                 type: Type,
                 num_bed: int,
                 num_bath: Decimal,
                 num_balcony: int,
                 measurements: Dict[Measure, Quantity] = None,
                 attributes: Dict = None):
        super().__init__(name, type, measurements, attributes)
        self.num_bed = num_bed
        self.num_bath = num_bath
        self.num_balcony = num_balcony
