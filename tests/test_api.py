from __future__ import annotations

# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.
import os
import locale
import multiprocess as mp
from typing import List, Callable, Dict

import matplotlib
import matplotlib.pyplot as plt
import networkx as nx
from pyvis.network import Network
# In addition, in order to enable pytest to find all modules,
# run tests via a 'python -m pytest tests/<test_file>.py' command from the root directory of this project
import pandas as pd
import numpy as np
import scipy.stats as ss
import pint

import rangekeeper as rk


class TestApi:
    def test_speckle(self):
        speckle = rk.api.Speckle(
            host="speckle.xyz",
            token=os.getenv('SPECKLE_TOKEN'))

        model = speckle.get_commit(
            stream_id="3f40d86240",
            commit_id="d5930913d6")

        roots = model.get_dynamic_member_names()
        print('Roots: {0}'.format(roots))

        # scenario_entities = rk.api.Speckle.parse(model['@scenario'])
        # print('Speckle Entities: \n {0}'.format(scenario_entities))

        root_assembly = rk.api.Speckle.to_entity(rk.api.Speckle.parse(model['@scenario'])[0])
        print('Root Assembly: {0}'.format(root_assembly))
        #
        buildingA = [node for node in root_assembly.nodes if node.name == 'BuildingA'][0]
        # buildingA = root_assembly.entities.where(lambda entity: entity.name == 'BuildingA').first()
        print('BuildingA: {0}'.format(type(buildingA)))

        root_assembly_nodes = root_assembly.nodes
        print('Root Assembly Nodes: {0}'.format(root_assembly_nodes))

        # buildingA_edges = buildingA.edges(data=True)
        # print('BuildingA Edges: \n {0}\n'.format(buildingA_edges))
        #
        buildingA_containment = buildingA.get_relatives(outgoing=True, relationship_type='spatiallyContains')
        print('BuildingA Containment: \n {0}\n'.format(buildingA_containment))
        # #
        # buildingA_resi = buildingA.entities.where(lambda entity: entity.name == 'BuildingA.Residential').first()
        # print('BuildingA Residential: \n {0}'.format(buildingA_resi))
        #
        # buildingBlinq = root_assembly.entities.where(lambda entity: entity.name == 'BuildingB').first_or_default()
        buildingB = [node for node in root_assembly.nodes if node.name == 'BuildingB']
        print('BuildingB: {0}'.format(buildingB))
        #
        # buildingB_edges = buildingB.edges(data=True)
        # print('BuildingB Edges: \n {0}\n'.format(buildingB_edges))
        #
        # buildingB_containment = buildingB.get_relatives()
        # print('BuildingB Containment: \n {0}\n'.format(buildingB_containment))
        #
        # buildingB_resi = buildingB.entities.where(lambda entity: entity.name == 'BuildingB.Residential').first()
        # print('BuildingB Residential: \n {0}'.format(buildingB_resi))

        # join = root_assembly.join(
        #     other=buildingA,
        #     name='Join',
        #     type='foo')
        # print('Join: \n {0}'.format(join))

        subassemblies = root_assembly.get_subassemblies()
        print('Subassemblies: \n {0}'.format(subassemblies))

        develop = root_assembly.develop(
            name='Develop',
            type='foo')
        # develop.nodes(data=True)
        print('Develop: \n {0}'.format(develop.nodes(data=True)))

        develop.plot()

        # pos = nx.nx_agraph.graphviz_layout(develop, prog="sfdp")
        # nx.draw(develop, pos)
        # plt.show()



        #
        #
        #
        # entities = rk.api.Speckle.parse(scenario)
        #
        # foo = rk.api.Speckle.parse(entities[0])
        # print(foo)
        #
        # bar = rk.api.Speckle.to_entity(entities[0])
        # bar_child = bar.entities[2]
        # print(bar_child)
        #
        # bar_grandchild = bar_child.entities[3]
        # # print(bar_grandchild)
        #
        # barfoo = bar_child.descedants()
        # print(barfoo)
        # nx.draw(barfoo, with_labels=True)

        # plt.show()
        # print(
        # print(bar.relationships[0])
        # print(bar.relationships[0][2])
        # print(bar.edges(data=True))
        # print(bar.get_relatives())



            # foo = rk.api.Speckle.to_entity(entities[0])

            #
            #
