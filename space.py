from __future__ import annotations
from typing import Dict, List, Union
import pint
import decimal


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


class Measurement:
    name: str
    definition: str
    value: Union[int, float]
    units: pint.Unit

    def __init__(
            self,
            name: str,
            value: Union[int, float],
            units: pint.Unit,
            definition: str = None):
        self.name = name
        self.value = value
        self.units = units
        self.definition = definition


class Space:
    name: str
    type: Type
    attributes: Dict
    measurements: List[Measurement]

    def __init__(
            self,
            name: str,
            type: Type,
            measurements: List[Measurement] = None,
            attributes: Dict = None):
        self.name = name
        self.type = type
        self.attributes = attributes
        self.measurements = measurements


class Apartment(Space):
    num_bed: int
    num_bathrooms: decimal.Decimal
    num_balcony: int
    measurements: List[Measurement]

    def __init__(self,
                 name: str,
                 type: Type,
                 num_bed: int,
                 num_bath: decimal.Decimal,
                 num_balcony: int,
                 measurements: List[Measurement] = None,
                 attributes: Dict = None):
        super().__init__(name, type, measurements, attributes)
        self.num_bed = num_bed
        self.num_bath = num_bath
        self.num_balcony = num_balcony
