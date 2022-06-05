from __future__ import annotations

import json
import uuid
import enum
from typing import List, Dict

import networkx as nx
from pint import Quantity
from py_linq import Enumerable

try:
    import measure
except:
    import modules.rangekeeper.measure as measure


#
# class Type(enum.Enum):
#     name: str
#     parent: Type
#     children: [Type]
#
#     def __init__(
#             self,
#             name: str,
#             parent: Type = None,
#             children: List[Type] = None):
#         super().__init__()
#         self.name
#         if parent is not None:
#             self.set_parent(parent)
#         if children is not None:
#             self.set_children(children)
#         else:
#             self.children = []
#
#     def __str__(self):
#         result = self.name
#         try:
#             result = self.parent.__str__() + '.' + result
#         except AttributeError:
#             pass
#         return result
#
#     def set_parent(
#             self,
#             parent: Type):
#         try:
#             self.parent.children.remove(self)
#         except AttributeError:
#             pass
#         self.parent = parent
#         parent.children.append(self)
#
#     def set_children(
#             self,
#             children: List[Type]):
#         for child in children:
#             child.set_parent(self)
#

class Event:
    name: str
    type: str


class Element:
    id: str
    name: str
    type: str
    attributes: dict
    events: List[Event]
    measurements: Dict[measure.Measure, Quantity]
    relationships: List[tuple[Element, str]]

    def __str__(self):
        return 'Element: ' + self.name + '. Type: ' + self.type

    def __init__(
            self,
            name: str,
            type: str,
            id: str = None,
            attributes: dict = None,
            events: List[Event] = None,
            measurements: Dict[measure.Measure, Quantity] = None):
        self.name = name
        self.type = type

        if id is None:
            self.id = str(uuid.uuid4())
        else:
            self.id = id

        if attributes is not None:
            self.attributes = attributes
        else:
            self.attributes = {}

        if events is not None:
            self.events = events
        else:
            self.events = []

        if measurements is None:
            self.measurements = {}
        else:
            self.measurements = measurements

    def get_relatives(
            self,
            assembly: Assembly,
            relationship_type: str,
            outgoing: bool = True) -> List[Element]:

        if outgoing:
            edges = Enumerable(
                assembly.edges(
                    nbunch=[self],
                    data='type')
                ).where(
                lambda edge: edge[2] == relationship_type)
            return [edge[1] for edge in edges]

        else:
            edges = Enumerable(
                assembly.in_edges(
                    nbunch=[self],
                    data='type')
                ).where(
                lambda edge: edge[2] == relationship_type)
            return [edge[0] for edge in edges]


class Assembly(nx.MultiDiGraph, Element):
    elements: Enumerable
    relations: Enumerable

    def __init__(
            self,
            name: str,
            type: str,
            elements: List[Element],
            relationships: List[tuple[Element, Element, str]],
            id: str = None,
            attributes: dict = None,
            events: List[Event] = None,
            measurements: Dict[measure.Measure, Quantity] = None):
        super().__init__(
            name=name)
        if id is None:
            self.id = str(uuid.uuid4())
        else:
            self.id = id

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
        for relationship in relationships:
            self.add_edge(relationship[0], relationship[1], type=relationship[2])

        self.elements = Enumerable(self.nodes)
        self.relations = Enumerable(self.edges)
