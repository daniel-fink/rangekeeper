from __future__ import annotations

import os
import uuid
from typing import List, Dict, Union, Optional
import pprint

import networkx as nx
from pint import Quantity
# from py_linq import Enumerable

import rangekeeper as rk

# from . import measure


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


class Entity:
    id: str
    name: str
    type: str
    attributes: dict
    events: List[Event]
    measurements: Dict[rk.measure.Measure, Quantity]

    def __str__(self):
        return ('Entity: {1}{0}' +
                'Type: {2}{0}' +
                'Attributes: {3}{0}' +
                'Events: {4}{0}' +
                'Measurements: {5}{0}').format(
            os.linesep,
            self.name,
            self.type,
            pprint.pformat(self.attributes),
            pprint.pformat(self.events),
            pprint.pformat(self.measurements))

    def __repr__(self):
        return 'Entity: {0} (Type: {1})'.format(self.name, self.type)

    def __init__(
            self,
            name: str,
            type: str,
            id: str = None,
            attributes: dict = None,
            events: List[Event] = None,
            measurements: Dict[rk.measure.Measure, Quantity] = None):
        self.name = name
        self.type = type
        self.id = str(uuid.uuid4()) if id is None else id
        self.attributes = {} if attributes is None else attributes
        self.events = [] if events is None else events
        self.measurements = {} if measurements is None else measurements

    def get_relatives(
            self,
            relationship_type: Union[str, None] = None,
            outgoing: Optional[bool] = True,
            assembly: Assembly = None) -> List[Entity]:

        assembly = self if assembly is None else assembly

        relatives = []
        if outgoing:
            successors = list(assembly.successors(n=self))
            if relationship_type is None:
                relatives = successors
            else:
                for successor in successors:
                    if assembly.get_edge_data(self, successor)['type'] == relationship_type:
                        relatives.append(successor)
        elif not outgoing:
            predecessors = list(assembly.predecessors(n=self))
            if relationship_type is None:
                relatives = predecessors
            else:
                for predecessor in predecessors:
                    if assembly.get_edge_data(predecessor, self)['type'] == relationship_type:
                        relatives.append(predecessor)

        elif outgoing is None:
            outgoing_relatives = self.get_relatives(relationship_type, True, assembly)
            incoming_relatives = self.get_relatives(relationship_type, False, assembly)
            relatives = set(outgoing_relatives + incoming_relatives)

        return relatives


class Assembly(nx.MultiDiGraph, Entity):
    # entities: Enumerable
    # relationships: Enumerable

    def __init__(self):
        super().__init__()
        # self.entities = Enumerable(self.nodes())
        # self.relationships = Enumerable(self.edges(data=True))

    def __repr__(self):
        return 'Assembly: {0} (Type: {1})'.format(self.name, self.type)

    def __str__(self):
        return ('Assembly: {1}{0}' +
                'Type: {2}{0}' +
                'Entities: {3}{0}' +
                'Relationships: {4}{0}').format(
            os.linesep,
            self.name,
            self.type,
            self.nodes(data=True),
            self.edges(data=True))

    @classmethod
    def from_properties(
            cls,
            name: str,
            type: str,
            id: str = None,
            attributes: dict = None,
            events: List[Event] = None,
            measurements: Dict[rk.measure.Measure, Quantity] = None) -> Assembly:
        assembly = cls()

        assembly.name = name
        assembly.type = type
        assembly.id = str(uuid.uuid4()) if id is None else id
        assembly.attributes = {} if attributes is None else attributes
        assembly.events = [] if events is None else events
        assembly.measurements = {} if measurements is None else measurements
        return assembly

    def add_relationship(self, relationship: tuple[Entity, Entity, str]):
        self.add_edge(relationship[0], relationship[1], type=relationship[2])

    def add_relationships(self, relationships: List[tuple[Entity, Entity, str]]):
        for relationship in relationships:
            self.add_relationship(relationship)

    def join(
            self,
            others: List[Assembly],
            name: str,
            type: str):
        all = others.copy()
        all.append(self)
        composition = nx.compose_all(all)

        composition.name = name
        composition.type = type
        composition.id = str(uuid.uuid4())

        composition.attributes = self.attributes
        for other in others:
            composition.attributes.update(other.attributes)

        composition.events = self.events
        for other in others:
            composition.events.extend(other.events)

        composition.measurements = self.measurements
        for other in others:
            composition.measurements.update(other.measurements)

        return composition

    def get_subassemblies(self):
        subassemblies = []
        for entity in self.nodes():
            if isinstance(entity, Assembly):
                if entity is not self:
                    subassemblies.append(entity)
        return subassemblies

    def develop(
            self,
            name: str,
            type: str,
            # relationship_type: str = None,
            graph: Optional[Assembly] = None) -> Assembly:
        if graph is None:
            graph = self
        subassemblies = self.get_subassemblies()
        if len(subassemblies) > 0:
            graph = graph.join(
                others=subassemblies,
                name=name,
                type=type)
            for subassembly in subassemblies:
                subassembly.develop(
                    name=name,
                    type=type,
                    # relationship_type=relationship_type,
                    graph=graph)
        return graph


        # relatives = self.get_relatives(relationship_type=relationship_type)
        # if len(relatives) > 0:
        #     for relative in relatives:
        #         if (relative is not self) and (relative is not graph):
        #             if isinstance(relative, Assembly):
        #                 join = graph.join(
        #                     other=relative,
        #                     name=name,
        #                     type=type)
        #                 return relative.develop(
        #                     name=name,
        #                     type=type,
        #                     relationship_type=relationship_type,
        #                     graph=join)
        #             else:
        #                 return graph
        #         else:
        #             return graph
        # else:
        #     return graph






    # def descedants(
    #         self,
    #         entities: List[Entity] = None) -> List[Entity]:
    #     children = self.entities.to_list()
    #     if len(children) > 0:
    #         if entities is None:
    #             entities = [children]
    #         else:
    #             entities.extend(children)
    #         for child in children:
    #             if isinstance(child, Assembly):
    #                 child.descedants(entities=entities)
    #     return entities
