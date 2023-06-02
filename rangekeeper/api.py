import os
from typing import Optional, Union, List, Type

import rangekeeper as rk
from graph import Assembly, Entity
from rangekeeper import graph

from specklepy import objects
from specklepy.api import client, credentials, operations
from specklepy.transports.server import ServerTransport


class Speckle:
    def __init__(
            self,
            token: str,
            host: str = "speckle.xyz"):
        self.client = client.SpeckleClient(host=host)
        account = credentials.get_account_from_token(token, host)
        self.client.authenticate_with_account(account)
        print('{0} {1}'.format(os.linesep, self.client))

    def get_commit(
            self,
            stream_id: str,
            commit_id: str):
        stream = self.client.stream.get(id=stream_id)
        transport = ServerTransport(client=self.client, stream_id=stream_id)

        commit = self.client.commit.get(stream_id, commit_id)
        return operations.receive(obj_id=commit.referencedObject, remote_transport=transport)

    @staticmethod
    def parse(base: objects.Base,
              entities: Optional[List[objects.Base]] = None) -> List[objects.Base]:
        entities = [] if entities is None else entities
        if isinstance(base, objects.Base):
            if Speckle.is_entity(base):
                entities.append(base)
            member_names = base.get_dynamic_member_names()
            if len(member_names) > 0:
                for member_name in member_names:
                    members = base[member_name]
                    if isinstance(members, objects.Base):
                        Speckle.parse(members, entities)
                    elif isinstance(members, list):
                        for member in members:
                            Speckle.parse(member, entities)
        return entities

    @staticmethod
    def to_entity(base: objects.Base):# -> Union[Assembly, Entity]:
        if Speckle.is_entity(base):
            member_names = base.get_dynamic_member_names()
            if ('entities' in member_names) & ('relationships' in member_names):
                return Speckle.to_assembly(base)
            else:
                entity = rk.graph.Entity(
                    id=base['entityId'],
                    name=base['name'],
                    type=base['type'],
                    attributes=getattr(base, 'attributes', None),
                    events=getattr(base, 'events', None),
                    measurements=getattr(base, 'measurements', None))
                return entity

    @staticmethod
    def to_assembly(base: objects.Base) -> graph.Assembly:
        # entities: List[rk.graph.Entity]) -> List[tuple[rk.graph.Entity, rk.graph.Entity, str]]:
        entities = []
        for entity in base['entities']:
            entities.append(Speckle.to_entity(entity))
        entities = list(filter(None, entities))

        assembly = rk.graph.Assembly()
        assembly.id = base['entityId']
        assembly.name = base['name']
        assembly.type = base['type']
        assembly.attributes = getattr(base, 'attributes', {})
        assembly.events = getattr(base, 'events', [])
        assembly.measurements = getattr(base, 'measurements', {})
        entities.append(assembly)

        for relationship in base['relationships']:
            source = next((entity for entity in entities if entity.id == relationship['sourceId']), None)
            target = next((entity for entity in entities if entity.id == relationship['targetId']), None)
            if (source is not None) & (target is not None):
                assembly.add_relationship((source, target, relationship['type']))

        return assembly
        # return rk.graph.Assembly.from_relationships(
        #     id=assembly['entityId'],
        #     name=assembly['name'],
        #     type=assembly['type'],
        #     relationships=relationships,
        #     attributes=getattr(assembly, 'attributes', None),
        #     events=getattr(assembly, 'events', None),
        #     measurements=getattr(assembly, 'measurements', None))

    @staticmethod
    def is_entity(obj: object) -> bool:
        if isinstance(obj, objects.Base):
            return 'entityId' in obj.get_dynamic_member_names()
        else:
            return False

    # @staticmethod
    # def query(
    #         stream_id: str,
    #         commit_id: str,
    #         host: str = 'https://speckle.xyz/',
    #         account: specklepy.api.credentials.Account = None):
    #     foo = 1
    #     account = get_default_account() if account is None else account
    #     client = SpeckleClient(host=host)
    #     client.authenticate_with_account(account)
    #
    #     commit = client.commit.get(stream_id, commit_id)
    #     transport = ServerTransport(client=client, stream_id=stream_id)
    #
    #     obj = operations.receive(commit.referencedObject, transport)
    #
    #     data = obj['data']
    #
    #     return data
    #
    # @staticmethod
    # def query2(resource: str):
    #     wrapper = StreamWrapper(resource)
    #     client = wrapper.get_client()
    #     transport = wrapper.get_transport()
    #
    #     commit_id = wrapper.commit_id
    #
    #     commit = client.commit.get(wrapper.stream_id, commit_id)
    #
    #     obj = client.object.get(wrapper.stream_id, wrapper.object_id)
    #
    #     return client.object.get(wrapper.stream_id, obj.get_id())#[obj.get_dynamic_member_names()[0]].id
    #     # obj = operations.receive(commit.referencedObject, transport)
    #
    #
    #
    #
    #
    #
    #
    #
    #
    #     # or whatever your host is

#
# class Conversion:
#     @staticmethod
#     def from_speckle(
#             element: specklepy.objects.Base
#             ):
#         foo = specklepy.objects.base.Base()
#         foo.totalChildrenCount
