from __future__ import annotations
import os
import locale
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import networkx as nx

import specklepy.objects as objects

# import rangekeeper as rk
#
# # Pytests file.
# # Note: gathers tests according to a naming convention.
# # By default any file that is to contain tests must be named starting with 'test_',
# # classes that hold tests must be named starting with 'Test',
# # and any function in a file that should be treated as a test must also start with 'test_'.
#
# # matplotlib.use('TkAgg')
# plt.style.use("seaborn-v0_8")  # pretty matplotlib plots
# plt.rcParams["figure.figsize"] = (12, 8)
#
# locale = locale.setlocale(locale.LC_ALL, "en_AU")
# units = rk.measure.Index.registry
# currency = rk.measure.register_currency(registry=units)
# scope = dict(globals(), **locals())
#
#
# element_root = rk.graph.Entity(name="root", type="root_type")
# element_child = rk.graph.Entity(name="child", type="child_type")
# element_grandchild01 = rk.graph.Entity(name="grandchild01", type="grandchild_type")
# element_grandchild02 = rk.graph.Entity(name="grandchild02", type="grandchild_type")
# assembly = rk.graph.Assembly(name="assembly", type="assembly_type")
# relationships = [
#     (element_root, element_child, "is_parent_of"),
#     (element_child, element_grandchild01, "is_parent_of"),
#     (element_child, element_grandchild02, "is_parent_of"),
# ]
# [assembly.add_relationship(relationship) for relationship in relationships]
#

# class TestGraph:
#     def test_graph(self):
#         assert assembly.graph.size() == 3
#         assert assembly.graph.has_predecessor(element_child.entityId, element_root.entityId)
#
#         assert issubclass(type(assembly), rk.graph.Entity)
#         assert issubclass(type(assembly), objects.Base)
#         assembly['new_property'] = 'foo'
#         assert assembly.new_property == 'foo'
#
#         # Test Querying:
#         # Check retrieval of first Entity in query:
#         assert [entity for entity in assembly.get_entities().values() if entity.name == 'grandchild01'][
#                    0].type == 'grandchild_type'
#
#         # Check count of query response:
#         assert len([entity for entity in assembly.get_entities().values() if entity.type == 'grandchild_type']) == 2
#
#         # Check retrieval of Element Relatives:
#         assert [element.name for element in element_root.get_relatives(
#             assembly=assembly,
#             relationship_type='is_parent_of')] == ['child']
#
#         # # # Check retrieval of Element Relatives in chained query:
#         # assert [element.name for element in assembly.elements.where(
#         #     lambda element: element.type == 'grandchild_type').select_many(
#         #     lambda element: element.get_relatives(
#         #         assembly=assembly,
#         #         relationship_type='is_parent_of',
#         #         outgoing=False)
#         #     ).distinct(
#         #     lambda element: element.id)] == ['child']
#
#     # def test_aggregation(self):
#     #     element_root._aggregate(
#     #         property='name',
#     #         label='children',
#     #         relationship_type='is_parent_of',
#     #         assembly=assembly)
#     #
#     #     assert element_root['children'] == {element_child.entityId: 'child'}
#     #     assert element_child['children'] == {
#     #         element_grandchild01.entityId: 'grandchild01',
#     #         element_grandchild02.entityId: 'grandchild02'
#     #         }
#     #     assert element_grandchild01['children'] == {}
#     #     assert element_grandchild02['children'] == {}
#
