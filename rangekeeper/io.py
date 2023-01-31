import specklepy
import specklepy.api.credentials
import specklepy.api.client
from specklepy.transports.server import ServerTransport
from specklepy.api import operations
from specklepy import objects
from specklepy.api.wrapper import StreamWrapper


class Speckle:
    def __init__(
            self,
            host="speckle.xyz",
            token=None):

        print("Connecting to {} with {}".format(host, token))
        self.client = specklepy.api.client.SpeckleClient(host=host)
        account = specklepy.api.credentials.get_account_from_token(token, host)
        self.client.authenticate_with_account(account)
        print(self.client)

    def get_item(
            self,
            stream_id: str,
            commit_id: str):
        stream = self.client.stream.get(id=stream_id)
        transport = ServerTransport(client=self.client, stream_id=stream_id)
        # latest_commit = stream.branches.items[0].commits.items[0]

        commit = self.client.commit.get(stream_id, commit_id)
        received_base = operations.receive(obj_id=commit.referencedObject, remote_transport=transport)
        data = received_base
        return data


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
