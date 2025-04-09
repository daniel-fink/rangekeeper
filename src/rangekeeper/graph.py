from __future__ import annotations

import os
import uuid
from typing import List, Dict, Union, Optional, Callable, Any
import pprint

import networkx as nx
import numpy as np
import pandas as pd
from pyvis import network, options
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import plotly.offline as py

from pint import Quantity
from IPython.display import IFrame
import matplotlib as mpl

import specklepy.objects as objects

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


def is_entity(base: objects.Base, exclusive: bool = False) -> bool:
    if "Rangekeeper" in base.speckle_type:
        if exclusive:
            return ("Entity" in base.speckle_type) and (
                "Assembly" not in base.speckle_type
            )
        else:
            return ("Entity" in base.speckle_type) or ("Assembly" in base.speckle_type)
    else:
        return False


def is_assembly(base: objects.Base) -> bool:
    if "Rangekeeper" in base.speckle_type:
        return "Assembly" in base.speckle_type
    else:
        return False


class Entity(objects.Base):
    entityId: str

    def __str__(self):
        return (
            "Entity: {1}{0}" + "Type: {2}{0}" + "Entity Id: {3}{0}" + "Members: {4}"
        ).format(
            os.linesep,
            self["name"] if hasattr(self, "name") else "[Unnamed]",
            self["type"] if hasattr(self, "type") else "[Unknown]",
            self["entityId"],
            self.get_dynamic_member_names(),
        )

    def __repr__(self):
        return "Entity: {0} (Type: {1})".format(
            self["name"] if hasattr(self, "name") else "[Unnamed]",
            self["type"] if hasattr(self, "type") else "[Unknown]",
        )

    def __eq__(self, other):
        return self.entityId == other.entityId

    def __hash__(self):
        return hash(self.entityId)

    def __init__(self, entityId: str = None, name: str = None, type: str = None):
        super().__init__(
            entityId=str(uuid.uuid4()) if entityId is None else entityId,
            name=name if name is not None else "[Unnamed]",
            type=type if type is not None else "[Unknown]",
        )

    def try_get_attribute(self, key):
        try:
            return self[key]
        except KeyError:
            return None

    @classmethod
    def from_base(cls, base: objects.Base, name: str = None, type: str = None):
        if rk.graph.is_assembly(base):
            return Assembly.from_assemblybase(base)
        elif rk.graph.is_entity(base, True):
            return cls.from_entitybase(base)
        else:
            entity = cls(
                entityId=str(uuid.uuid4()),
                name=base["name"] if base["name"] is not None else "[Unnamed]",
                type=base["type"] if base["type"] is not None else "[Unknown]",
            )
            for member_name in base.get_member_names():
                entity.__setattr__(member_name, base[member_name])
            return entity

    @classmethod
    def from_entitybase(
        cls, base: objects.Base, name: str = None, type: str = None
    ) -> Entity:
        if not rk.graph.is_entity(base, True):
            raise TypeError("Base is not an Entity")
        entity = cls(
            entityId=base["entityId"],
            name=base["name"] if base["name"] is not None else "[Unnamed]",
            type=base["type"] if base["type"] is not None else "[Unknown]",
        )
        for member_name in base.get_member_names():
            if member_name == "units":  # This is tripping something? Weird..
                continue
            else:
                entity.__setattr__(member_name, base[member_name])
        return entity

    def get_relationships(
        self, assembly: Assembly = None
    ) -> list[tuple[str, str, str]]:
        incoming = [
            (edge[2], "incoming", edge[0])
            for edge in assembly.graph.in_edges(nbunch=self["entityId"], keys=True)
        ]
        outgoing = [
            (edge[2], "outgoing", edge[1])
            for edge in assembly.graph.out_edges(nbunch=self["entityId"], keys=True)
        ]
        return incoming + outgoing

    def get_relatives(
        self,
        relationship_type: Union[str, None] = None,
        outgoing: Optional[bool] = True,
        assembly: Assembly = None,
    ) -> List[Entity]:

        relationships = self.get_relationships(assembly)
        if relationship_type is not None:
            relationships = [
                relationship
                for relationship in relationships
                if relationship[0] == relationship_type
            ]

        if outgoing:
            relationships = [
                relationship
                for relationship in relationships
                if relationship[1] == "outgoing"
            ]

        elif not outgoing:
            relationships = [
                relationship
                for relationship in relationships
                if relationship[1] == "incoming"
            ]

        return [assembly.get_entity(relationship[2]) for relationship in relationships]

    def _aggregate(
        self,
        assembly: rk.graph.Assembly,
        property: str,
        label: str,
        relationship_type: str = None,
        function: Optional[Callable] = None,
        outgoing: bool = True,
    ) -> dict[str, Any]:

        aggregation = {
            (self.entityId, self["name"]): (
                self[property] if hasattr(self, property) else None
            )
        }
        # print('Added {0} of {1} to partial in {3}'.format(property_name, self.name, aggregation_name, self.name))

        relatives = self.get_relatives(
            relationship_type=relationship_type, outgoing=outgoing, assembly=assembly
        )

        # print('Found {0} relatives: {1}'.format(len(relatives), [relative.name for relative in relatives]))
        for relative in relatives:
            aggregation.update(
                relative._aggregate(
                    assembly=assembly,
                    function=function,
                    property=property,
                    label=label,
                    relationship_type=relationship_type,
                    outgoing=outgoing,
                )
            )

        # print('State of partial for {0}: {1}'.format(self.name, partial))
        if hasattr(self, label):
            if function is None:
                self[label] += sum(filter(None, aggregation.values()))
            else:
                self[label] += function(aggregation=aggregation, entity=self)
        else:
            if function is None:
                self[label] = sum(filter(None, aggregation.values()))
            else:
                self[label] = function(aggregation=aggregation, entity=self)
        # print('State of {0} for {1}: {2}'.format(aggregation_name, self.name, self[aggregation_name]))
        return aggregation

    @staticmethod
    def aggregate_flows(
        name: str,
        aggregation: dict[str, Union[rk.flux.Stream, rk.flux.Flow]],
        entity: rk.graph.Entity,
        frequency: rk.duration.Type,
    ) -> Optional[rk.flux.Stream]:
        flows = []

        for (aggregand_id, aggregand_name), flux in aggregation.items():
            if flux is not None:
                flow_name = "{0} for {1} [{2}]".format(
                    flux.name, aggregand_id, aggregand_name
                )
                if isinstance(flux, rk.flux.Stream):
                    flow = flux.sum(name=flow_name)
                else:
                    flow = flux.duplicate(name=flow_name)
                flows.append(flow)

        if len(flows) > 0:
            return rk.flux.Stream(
                name="{0} for {1} [{2}] Aggregation".format(
                    name, entity["entityId"], entity["name"]
                ),
                flows=flows,
                frequency=frequency,
            )
        else:
            return None

    def to_kvps(
        self,
        assembly: Assembly,
        arborescence: bool = False,
        properties: List[str] = None,
    ) -> dict:
        filtered = [
            "applicationId",
            "graph",
            "speckle_type",
            "totalChildrenCount",
            "units",
            "@displayValue",
            "renderMaterial",
        ]
        keys = properties
        if properties is None:
            keys = list(
                filter(lambda key: key not in filtered, self.get_member_names())
            )
        attributes = {key: self.try_get_attribute(key) for key in keys}
        relationships = self.get_relationships(assembly=assembly)
        if arborescence is False:
            attributes["relationships"] = relationships
        else:
            parents = self.get_relatives(assembly=assembly, outgoing=False)
            if len(parents) > 1:
                raise ValueError(
                    "Multiple parents found for {0} in {1}".format(
                        self["entityId"], arborescence
                    )
                )
            children = self.get_relatives(assembly=assembly, outgoing=True)

            attributes.update(
                {
                    "parent": None if len(parents) == 0 else parents[0]["entityId"],
                    "children": [child["entityId"] for child in children],
                }
            )

        return attributes

    def get_ancestors(
        self, relationship_type: str = None, assembly: Assembly = None
    ) -> dict[str, Entity]:
        assembly = self if assembly is None else assembly

        if relationship_type is None:
            tree = assembly
        else:
            tree = assembly.filter_by_type(relationship_type=relationship_type)
        if not nx.is_arborescence(tree.graph):
            raise Exception("The Assembly is not a tree. Cannot calculate ancestors.")

        ancestors = {}
        parents = self.get_relatives(
            outgoing=False, relationship_type=relationship_type, assembly=tree
        )
        if len(parents) > 0:
            parent = parents[0]
            ancestors[parent["entityId"]] = parent
            ancestors.update(
                parent.get_ancestors(relationship_type=relationship_type, assembly=tree)
            )
        return ancestors


class Assembly(Entity):
    graph: nx.MultiDiGraph

    def __repr__(self):
        return "Assembly: {0} (Type: {1})".format(
            self.name if hasattr(self, "name") else "[Unnamed]",
            self.type if hasattr(self, "type") else "[Unknown]",
        )

    def __str__(self):
        return (
            "Assembly: {1}{0}"
            + "Type: {2}{0}"
            + "Members: {3}{0}"
            + "Entities: {4}{0}"
            + "Relationships: {5}{0}"
        ).format(
            os.linesep,
            self.name if hasattr(self, "name") else "[Unnamed]",
            self.type if hasattr(self, "type") else "[Unknown]",
            self.get_dynamic_member_names(),
            self.graph.nodes(data=True),
            self.graph.edges(keys=True),
        )

    def __init__(self, entityId: str = None, name: str = None, type: str = None):
        super().__init__(entityId, name, type)
        self.graph = nx.MultiDiGraph()

    @classmethod
    def from_graph(cls, graph: nx.MultiDiGraph, name: str = None, type: str = None):
        assembly = cls(
            entityId=str(uuid.uuid4()),
            name=name if name is not None else "[Unnamed]",
            type=type if type is not None else "[Unknown]",
        )
        assembly.graph = graph
        return assembly

    def filter_by_type(
        self,
        name: str = None,
        type: str = None,
        relationship_type: str = None,
        entity_type: str = None,
        is_assembly: bool = None,
    ) -> Assembly:
        if relationship_type is None and entity_type is None:
            raise ValueError(
                "Either relationship_type or entity_type must be provided."
            )
        name = "{0} by {1} and {2}".format(self["name"], relationship_type, entity_type)
        type = "subgraph" if type is None else type

        if relationship_type is not None:
            graph = self.graph.edge_subgraph(
                [
                    edge
                    for edge in self.graph.edges(keys=True)
                    if edge[2] == relationship_type
                ]
            )
        else:
            graph = self.graph

        if entity_type is not None:
            graph = graph.subgraph(
                [
                    entityId
                    for (entityId, entity) in nx.get_node_attributes(
                        graph, "entity"
                    ).items()
                    if entity["type"] == entity_type
                ]
            )

        if is_assembly is not None:
            if is_assembly is True:
                graph = graph.subgraph(
                    [
                        entityId
                        for (entityId, entity) in nx.get_node_attributes(
                            graph, "entity"
                        ).items()
                        if rk.graph.is_assembly(entity)
                    ]
                )
            else:
                graph = graph.subgraph(
                    [
                        entityId
                        for (entityId, entity) in nx.get_node_attributes(
                            graph, "entity"
                        ).items()
                        if rk.graph.is_entity(entity, True)
                    ]
                )

        return Assembly.from_graph(graph=graph, name=name, type=type)

    @classmethod
    def from_assemblybase(
        cls, base: objects.Base, relatives: dict[str, objects.Base] = None
    ):
        if not rk.graph.is_assembly(base):
            raise TypeError("The provided Base is not an Assembly.")
        assembly = cls(
            entityId=base["entityId"],
            name=base["name"] if base["name"] is not None else "[Unnamed]",
            type=base["type"] if base["type"] is not None else "[Unknown]",
        )

        for member_name in base.get_member_names():
            if member_name in ["relationships"]:
                continue
            elif member_name == "units":  # This is tripping something? Weird..
                continue
            else:
                value = base[member_name]
                assembly.__setattr__(member_name, value)

        if relatives is not None:
            for relationship in base["relationships"]:
                source = (
                    relatives[relationship["source"]["entityId"]]
                    if relationship["source"] is not None
                    else assembly
                )
                # This seems to happen bc of Speckle's serialization?
                target = (
                    relatives[relationship["target"]["entityId"]]
                    if relationship["target"] is not None
                    else assembly
                )
                # This seems to happen bc of Speckle's serialization?
                assembly.add_relationship(
                    (
                        source,
                        target,
                        relationship["type"],
                    )
                )
        return assembly

    def add_entities(self, entities: List[Entity]):
        self.graph.add_nodes_from(entities)
        nx.set_node_attributes(self.graph, entities, "entity")

    def get_entities(self, entityIds: list[str] = None) -> dict[str, Entity]:
        entities = nx.get_node_attributes(self.graph, "entity")
        if entityIds is None:
            return entities
        else:
            return {entityId: entities[entityId] for entityId in entityIds}

    def get_entity(self, entityId: str) -> Entity:
        return self.get_entities([entityId])[entityId]

    def add_relationship(self, relationship: tuple[Entity, Entity, str]):
        self.graph.add_edge(
            relationship[0]["entityId"],
            relationship[1]["entityId"],
            key=relationship[2],
        )
        nx.set_node_attributes(
            G=self.graph,
            values={
                relationship[0]["entityId"]: relationship[0],
                relationship[1]["entityId"]: relationship[1],
            },
            name="entity",
        )

    def add_relationships(self, relationships: List[tuple[Entity, Entity, str]]):
        for relationship in relationships:
            self.add_relationship(relationship)

    def get_roots(self) -> dict[str, list[Entity]]:
        types = set(edge[2] for edge in self.graph.edges(keys=True))
        roots = {}
        for type in types:
            subgraph = self.filter_by_type(relationship_type=type).graph
            roots[type] = [
                self.get_entity(node)
                for node in subgraph.nodes()
                if subgraph.in_degree(node) == 0
            ]
        return roots

    def get_leaves(self) -> dict[str, list[Entity]]:
        types = set(edge[2] for edge in self.graph.edges(keys=True))
        leaves = {}
        for type in types:
            subgraph = self.filter_by_type(relationship_type=type).graph
            leaves[type] = [
                self.get_entity(node)
                for node in subgraph.nodes()
                if subgraph.out_degree(node) == 0
            ]
        return leaves

    def get_subassemblies(self) -> dict[str, Assembly]:
        subassemblies = {}
        for entity in self.get_entities().values():
            if isinstance(entity, Assembly):
                if entity is not self:
                    if entity not in subassemblies.values():
                        subassemblies[entity.entityId] = entity
                        subassemblies.update(entity.get_subassemblies())
        return subassemblies

    def get_subentities(self) -> dict[str, Entity]:
        subentities = {}
        for entity in self.get_entities().values():
            if entity is not self:
                if isinstance(entity, Assembly):
                    if entity not in subentities.values():
                        subentities[entity.entityId] = entity
                        subentities.update(entity.get_subentities())
                else:
                    if isinstance(entity, Entity):
                        if entity.entityId not in subentities:
                            subentities[entity.entityId] = entity
        return subentities

    def aggregate(
        self,
        property: str,
        label: str,
        relationship_type: str = None,
        function: Optional[Callable] = None,
        outgoing: bool = True,
    ):

        if relationship_type is not None:
            assembly = self.filter_by_type(relationship_type=relationship_type)
        else:
            assembly = self

        if nx.is_arborescence(assembly.graph):
            root = next(nx.topological_sort(assembly.graph))
        else:
            raise NotImplementedError(
                "Aggregation is only implemented for arborescent graphs."
            )

        self.get_entity(root)._aggregate(
            assembly=assembly,
            property=property,
            label=label,
            relationship_type=relationship_type,
            function=function,
            outgoing=outgoing,
        )

    def to_dict(self, properties: Optional[List[str]] = None) -> dict[str, dict]:
        arborecence = False
        if nx.is_arborescence(self.graph):
            arborecence = True
        results = {}
        for entity in self.get_entities().values():
            if entity["entityId"] not in results:
                results[entity.entityId] = entity.to_kvps(
                    assembly=self, properties=properties, arborescence=arborecence
                )
            else:
                raise ValueError("Duplicate Entity found: {0}".format(entity.entityId))
        return results

    def to_DataFrame(self, properties: Optional[List[str]] = None) -> pd.DataFrame:
        return pd.DataFrame.from_dict(
            self.to_dict(properties=properties), orient="index"
        )

    def _get_trunk_index(self, entityId: str) -> int:
        root = list(self.get_roots().values())[0][0]
        trunks = root.get_relatives(assembly=self)
        entity = self.get_entity(entityId)
        ancestors = entity.get_ancestors(assembly=self)
        for i in range(len(trunks)):
            if trunks[i]["entityId"] == entityId:
                return i
            elif trunks[i]["entityId"] in ancestors:
                return i
            # else:
            #     return -1

    def sunburst(self, property: str):
        if not nx.is_arborescence(self.graph):
            raise NotImplementedError(
                "Sunburst is only implemented for arborescent (hierarchical) graphs."
            )
        df = self.to_DataFrame()

        df["property_total"] = [
            (
                item.total()
                if isinstance(item, rk.flux.Flow) or isinstance(item, rk.flux.Stream)
                else item
            )
            for item in df[property]
        ]

        df["property_total"] = df["property_total"].fillna(0)

        if (df["property_total"].values <= 0).all():
            df["property_total"] = df["property_total"].abs()

        df["trunk_idx"] = df["entityId"].apply(
            lambda entityId: self._get_trunk_index(entityId)
        )
        df["color_norm"] = (df["property_total"] - df["property_total"].min()) / (
            df["property_total"].max() - df["property_total"].min()
        )
        df["color"] = df["color_norm"] + (df["trunk_idx"] + 2)

        trace = go.Sunburst(
            ids=df["entityId"],
            labels=df["name"],
            parents=df["parent"],
            values=df["property_total"],
            branchvalues="total",
            insidetextorientation="radial",
            marker=dict(
                colors=df["color"],
                colorscale="Sunset",
                cmin=df["color"].min(),
                cmax=df["color"].max(),
            ),
            hovertemplate="%{label}<br>" + property + ": %{value:,.2f}<br>",
            sort=False,
        )
        return trace

    def treemap(self, property, title: str = None):
        if not nx.is_arborescence(self.graph):
            raise NotImplementedError(
                "Sunburst is only implemented for arborescent (hierarchical) graphs."
            )
        df = self.to_DataFrame()

        df["property_total"] = [
            (
                item.total()
                if isinstance(item, rk.flux.Flow) or isinstance(item, rk.flux.Stream)
                else item
            )
            for item in df[property]
        ]

        df["property_total"] = df["property_total"].fillna(0)

        if (df["property_total"].values <= 0).all():
            df["property_total"] = df["property_total"].abs()

        df["trunk_idx"] = df["entityId"].apply(
            lambda entityId: self._get_trunk_index(entityId)
        )
        df["color_norm"] = (df["property_total"] - df["property_total"].min()) / (
            df["property_total"].max() - df["property_total"].min()
        )
        df["color"] = df["color_norm"] + (df["trunk_idx"] + 2)

        trace = go.Treemap(
            ids=df["entityId"],
            labels=df["name"],
            parents=df["parent"],
            values=df["property_total"],
            branchvalues="total",
            marker=dict(
                cornerradius=3,
                colors=df["color"],
                colorscale="Sunset",
                cmin=df["color"].min(),
                cmax=df["color"].max(),
            ),
            pathbar=dict(side="bottom", thickness=24),
            tiling=dict(packing="squarify", squarifyratio=1),
            hovertemplate="%{label}<br>" + property + ": %{value:,.2f}<br>",
            sort=False,
        )
        return trace

    def _to_network(
        self,
        node_sizes: dict[Entity, Any] = None,
        hierarchical_layout: bool = True,
        notebook: bool = True,
    ) -> network.Network:
        nt = network.Network(
            directed=True,
            filter_menu=True,
            layout=hierarchical_layout,
            notebook=notebook,
            cdn_resources="in_line",
        )

        nodes = self.to_dict()
        node_types = set([node["type"] for node in nodes.values()])

        node_colors = {
            type: rk.rgba_from_cmap(
                cmap_name="twilight_shifted",
                start_val=0,
                stop_val=len(node_types),
                val=i,
            )
            for i, type in enumerate(node_types)
        }

        edges = self.graph.edges(keys=True)
        edge_keys = set([edge[2] for edge in edges])
        edge_colors = {
            key: rk.rgba_from_cmap(
                cmap_name="inferno", start_val=0, stop_val=len(edge_keys), val=i
            )
            for i, key in enumerate(edge_keys)
        }

        node_sizes = (
            nx.harmonic_centrality(self.graph) if node_sizes is None else node_sizes
        )

        for entityId, properties in nodes.items():
            nt.add_node(
                n_id=entityId,
                label=properties["name"] if "name" in properties else "[Unnamed]",
                title=properties["type"] if "type" in properties else "[Unknown]",
                shape="dot",
                size=(1 / (node_sizes[entityId] + 1)) * 50,
                font="12px arial black",
                level=node_sizes[entityId],
                color=mpl.colors.rgb2hex(node_colors[properties["type"]]),
            )
        for edge in edges:
            nt.add_edge(
                source=edge[0],  # .entityId,
                to=edge[1],  # .entityId,
                title=edge[2],
                label=edge[2],
                arrows="to",
                font={"color": "grey", "size": 8, "align": "middle"},
                arrowStrikethrough=False,
                color=mpl.colors.rgb2hex(edge_colors[edge[2]]),
            )
        nt.set_edge_smooth("dynamic")
        return nt

    def plot(
        self,
        name: str = None,
        hierarchical_layout: bool = False,
        node_sizes: dict[Entity, Any] = None,
        height: int = 800,
        width: Union[int, str] = "100%",
        notebook: bool = True,
        display: bool = False,
    ):
        nt = self._to_network(
            hierarchical_layout=hierarchical_layout,
            node_sizes=node_sizes,
            notebook=notebook,
        )
        filename = (self["name"] + ".html") if name is None else (name + ".html")
        # print(filename)
        nt.show(name=filename, local=False, notebook=notebook)
        if notebook & display:
            return IFrame(self["name"] + ".html", width=width, height=height)
