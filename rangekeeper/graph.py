from __future__ import annotations

import json
import uuid
import enum
from typing import List, Dict

import networkx as nx
from pint import Quantity
from py_linq import Enumerable

from . import measure


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
        self.id = str(uuid.uuid4()) if id is None else id
        self.attributes = {} if attributes is None else attributes
        self.events = [] if events is None else events
        self.measurements = {} if measurements is None else measurements

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
    relationships: Enumerable

    def __init__(
            self,
            name: str,
            type: str,
            elements: List[Element],
            relationships: List[tuple[Element, Element, str]],  # A list of tuples of the form [From, To, Type]
            id: str = None,
            attributes: dict = None,
            events: List[Event] = None,
            measurements: Dict[measure.Measure, Quantity] = None):
        super().__init__(
            name=name)
        self.name = name
        self.type = type
        self.id = str(uuid.uuid4()) if id is None else id
        self.attributes = {} if attributes is None else attributes
        self.events = [] if events is None else events
        self.measurements = {} if measurements is None else measurements

        self.add_nodes_from(elements)
        for relationship in relationships:
            self.add_edge(relationship[0], relationship[1], type=relationship[2])

        self.elements = Enumerable(self.nodes)
        self.relationships = Enumerable(self.edges)
