from __future__ import annotations
from typing import List, Dict

import networkx as nx
from pint import Quantity
import py_linq

try:
    import measure
except:
    import modules.rangekeeper.measure


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


# class Relation(aenum.Enum):
#     contains = 'Contains'
#     services = 'Services'
#     connects_to = 'Connects To'


class Event:
    name: str
    type: Type


class Element:
    name: str
    type: Type
    attributes: dict
    events: List[Event]
    measurements: Dict[measure.Measure, Quantity]

    def __init__(
            self,
            name: str,
            type: Type,
            attributes: dict = None,
            events: List[Event] = None,
            measurements: Dict[measure.Measure, Quantity] = None):
        self.name = name
        self.type = type

        if attributes is not None:
            self.attributes = attributes
        else:
            self.attributes = {}

        if events is not None:
            self.events = events
        else:
            self.events = []

        if measurements is not None:
            self.measurements = measurements
        else:
            self.measurements = {}


class Assembly(nx.DiGraph, Element):
    elements: Enumerable
    relations: Enumerable

    def __init__(
            self,
            name: str,
            type: Type,
            elements: List[Element],
            relations: List[tuple[Element, Element, Type]],
            attributes: dict = None,
            events: List[Event] = None,
            measurements: Dict[measure.Measure, Quantity] = None):
        super().__init__(
            name=name)
            # type=type,
            # attributes=attributes,
            # events=events,
            # measurements=measurements)
        if attributes is not None:
            self.attributes = attributes
        else:
            self.attributes = {}

        if events is not None:
            self.events = events
        else:
            self.events = []

        if measurements is not None:
            self.measurements = measurements
        else:
            self.measurements = {}

        self.add_nodes_from(elements)
        for relation in relations:
            self.add_edge(relation[0], relation[1], type=relation[2])

        self.elements = py_linq.Enumerable(self.nodes)
        self.relations = py_linq.Enumerable(self.edges)

