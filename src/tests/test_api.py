from __future__ import annotations

# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.
import os
import pprint as pp

# In addition, in order to enable pytest to find all modules,
# run tests via a 'python -m pytest tests/<test_file>.py' command from the root directory of this project
import pandas as pd

pd.set_option("display.max_columns", None)

import rangekeeper as rk


# class TestApi:
#     stream_id = "c0f66c35e3"
#     speckle = rk.api.Speckle(token=os.getenv("SPECKLE_TOKEN"))
#     model = speckle.get_commit(stream_id=stream_id)
#
#     def test_connection(self):
#         latest_commit_id = TestApi.speckle.get_latest_commit_id(
#             stream_id=TestApi.stream_id
#         )
#         print("Latest Commit: {0}".format(latest_commit_id))
#
#         metadata = TestApi.speckle.get_metadata(stream_id=TestApi.stream_id)
#         print(metadata)
#
#         assert metadata.name == "RangekeeperDemo"
#
#         roots = TestApi.model.get_dynamic_member_names()
#
#         assert len(roots) == 2
#         assert "@property" in roots
#
#     def test_conversion(self):
#         parsed = rk.api.Speckle.parse(base=TestApi.model["@property"])
#         root_base = list(parsed.values())[0]
#         print("Root Base:\n {0}".format(root_base))
#         assert root_base.speckle_type == "Rangekeeper.Entity:Rangekeeper.Assembly"
#
#         root_entity = rk.graph.Entity.from_base(root_base)
#         assert root_entity.name == "property"
#         assert len(root_entity.graph.nodes) == 5
#         assert type(root_entity) == rk.graph.Assembly
#         print("Root Entity:\n {0}".format(root_entity))
#
#         buildingA = [
#             node for node in root_entity.graph.nodes if node.name == "buildingA"
#         ][0]
#         print("BuildingA:\n {0}".format(buildingA))
#         buildingA_containment = buildingA.get_relatives(
#             outgoing=True, relationship_type="contains"
#         )
#         print("BuildingA Containment: \n {0}\n".format(buildingA_containment))
#
#         buildingAresidential = [
#             node
#             for node in buildingA.graph.nodes
#             if node.name == "buildingAresidential"
#         ][0]
#         print("BuildingAresidential:\n {0}".format(buildingAresidential))
#
#     def test_develop(self):
#         parsed = rk.api.Speckle.parse(base=TestApi.model["@property"])
#         # print('\nParsed: \n{0}'.format(pp.pprint([base['name'] for base in parsed.values()])))
#         # print('\nCount Parsed: \n{0}'.format(len(parsed)))
#
#         property = rk.api.Speckle.to_rk(
#             bases=list(parsed.values()), name="property", type="property"
#         )
#         # print('\nScenario: \n{0}'.format(scenario))
#         # print('\nCount Scenario: \n{0}'.format(len(scenario.graph.nodes())))
#
#         spatial_containment = rk.graph.Assembly.from_graph(
#             graph=property.graph.edge_subgraph(
#                 [
#                     edge
#                     for edge in property.graph.edges(keys=True)
#                     if edge[2] == "spatiallyContains"
#                 ]
#             ),
#             name="spatial_containment",
#             type="subgraph",
#         )
#         # print('\nSpatial Containment: \n{0}'.format(spatial_containment))
#
#         roots = property.get_roots()  # ['spatiallyContains']
#         # print('\nRoots: \n{0}'.format(roots))
#
#         subassemblies = property.get_subassemblies()
#         # print('\nSubassemblies: \n{0}'.format(pp.pprint(list(subassemblies.values()))))
#
#         buildingA = [
#             assembly
#             for assembly in subassemblies.values()
#             if assembly["name"] == "buildingA"
#         ][0]
#         # print('\nBuildingA: \n{0}'.format(buildingA))
#
#         subentities = buildingA.get_subentities()
#         # print('\nSubentities: \n{0}'.format(pp.pprint(list(subentities.values()))))
#
#         scenario_dict = property.to_dict()
#         # print('\nDicts: \n{0}'.format(pp.pprint(scenario_dict)))
#
#         property.plot(
#             hierarchical_layout=False,
#             display=False,
#             height=1600,
#         )
#
#         spatial_containment_dict = spatial_containment.to_dict()
#         # print('\nSpatial Containment Dict: \n{0}'.format(pp.pprint(spatial_containment_dict)))
#
#         spatial_containment.aggregate(property="gfa", label="subtotal_gfa")
#
#         print(
#             "\nGFA Aggregation: \n{0}".format(pp.pprint(spatial_containment.to_dict()))
#         )
#         #
#         df = pd.DataFrame.from_dict(spatial_containment.to_dict(), orient="index")
#         print(df)
#
#         foo = spatial_containment.to_DataFrame()
#         #
#
#         fig = spatial_containment.sunburst("subtotal_gfa")
#         fig.show()
#
#         #
#
#         #
#         # nodes = list(spatial_containment_dict.values())
#         #
#         # data = dict(
#         #     entities=[node['name'] for node in nodes],
#         #     parent=[
#         #         spatial_containment.get_entity(node['parent'])[1]['name'] if node['parent'] is not None else None
#         #         for node in nodes],
#         #     value=[node['gfa'] if 'gfa' in node else 0 for node in nodes]
#         #     )
#         #
#         #
#         # fig = px.sunburst(
#         #     data,
#         #     names='entities',
#         #     parents='parent',
#         #     values='value',
#         #     )
#         # fig.show()
#
#         # print(pp.pprint(data))
#
#         # print(pp.pp(data))
#         # spatial_containment.sunburst()
#
#         # pos = nx.nx_agraph.graphviz_layout(develop, prog="sfdp")
#         # nx.draw(develop, pos)
#         # plt.show()
#
#         #
#         #
#         #
#         # entities = rk.api.Speckle.parse(scenario)
#         #
#         # foo = rk.api.Speckle.parse(entities[0])
#         # print(foo)
#         #
#         # bar = rk.api.Speckle.to_entity(entities[0])
#         # bar_child = bar.entities[2]
#         # print(bar_child)
#         #
#         # bar_grandchild = bar_child.entities[3]
#         # # print(bar_grandchild)
#         #
#         # barfoo = bar_child.descedants()
#         # print(barfoo)
#         # nx.draw(barfoo, with_labels=True)
#
#         # plt.show()
#         # print(
#         # print(bar.relationships[0])
#         # print(bar.relationships[0][2])
#         # print(bar.edges(data=True))
#         # print(bar.get_relatives())
#
#         # foo = rk.api.Speckle.to_entity(entities[0])
#
#         #
#         #
