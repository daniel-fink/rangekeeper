from __future__ import annotations

import os
import uuid
from typing import List, Dict, Union, Optional
import pprint

import networkx as nx
from pyvis import network, options
from pint import Quantity
from IPython.display import IFrame
import matplotlib as mpl

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
                    if assembly.get_edge_data(self, successor, key=relationship_type) is not None:
                        relatives.append(successor)
        elif not outgoing:
            predecessors = list(assembly.predecessors(n=self))
            if relationship_type is None:
                relatives = predecessors
            else:
                for predecessor in predecessors:
                    if assembly.get_edge_data(predecessor, self, key=relationship_type) is not None:
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
            self.edges(keys=True))

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
        self.add_edge(relationship[0], relationship[1], key=relationship[2])

    def add_relationships(self, relationships: List[tuple[Entity, Entity, str]]):
        for relationship in relationships:
            self.add_relationship(relationship)

    def merge(
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
            graph: Optional[Assembly] = None) -> Assembly:
        if graph is None:
            graph = self
        subassemblies = self.get_subassemblies()
        if len(subassemblies) > 0:
            graph = graph.merge(
                others=subassemblies,
                name=name,
                type=type)
            for subassembly in subassemblies:
                subassembly.develop(
                    name=name,
                    type=type,
                    graph=graph)
        return graph

    def _to_network(
            self,
            hierarchical_layout: bool = True,
            notebook: bool = True) -> network.Network:
        nt = network.Network(
            directed=True,
            filter_menu=True,
            layout=hierarchical_layout,
            notebook=notebook,
            cdn_resources='in_line')
        node_types = set([node.type for node in self.nodes()])
        node_colors = {
            type: rk.rgba_from_cmap(
                cmap_name='twilight_shifted',
                start_val=0,
                stop_val=len(node_types),
                val=i) for i, type in enumerate(node_types)}

        edge_keys = set([edge[2] for edge in self.edges(keys=True)])
        edge_colors = {
            key: rk.rgba_from_cmap(
                cmap_name='inferno',
                start_val=0,
                stop_val=len(edge_keys),
                val=i) for i, key in enumerate(edge_keys)}

        for node in self.nodes():
            if isinstance(node, Assembly):
                nt.add_node(
                    n_id=node.id,
                    label=node.name,
                    title=node.type,
                    shape='circle',
                    borderWidth=2,
                    labelHighlightBold=True,
                    font='16px arial white',
                    level=len(self.in_edges(node)),
                    color=mpl.colors.rgb2hex(node_colors[node.type]))
            else:
                nt.add_node(
                    n_id=node.id,
                    label=node.name,
                    title=node.type,
                    shape='dot',
                    size=10,
                    font='12px arial black',
                    level=len(self.in_edges(node)) + 1,
                    color=mpl.colors.rgb2hex(node_colors[node.type]))
        for edge in self.edges(keys=True):
            nt.add_edge(
                source=edge[0].id,
                to=edge[1].id,
                title=edge[2],
                label=edge[2],
                arrows='to',
                font={
                    'color': 'grey',
                    'size': 8,
                    'align': 'middle'
                    },
                arrowStrikethrough=False,
                color=mpl.colors.rgb2hex(edge_colors[edge[2]]))
        nt.set_edge_smooth('dynamic')
        return nt

    def plot(
            self,
            hierarchical_layout: bool = True,
            height: int = 800,
            width: Union[int, str] = '100%',
            notebook: bool = True,
            display: bool = False):
        nt = self._to_network(
            hierarchical_layout=hierarchical_layout,
            notebook=notebook)
        nt.show(
            name=self.name + '.html',
            local=False,
            notebook=notebook)
        if notebook & display:
            return IFrame(self.name + '.html', width=width, height=height)
