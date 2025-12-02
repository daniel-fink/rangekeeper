import os

from specklepy import objects
from specklepy.api import client
from specklepy.api import operations

import rangekeeper as rk
from rangekeeper import graph


class Speckle:
    def __init__(
        self,
        token: str,
        host: str = None,
    ):
        host = "DEFAULT_HOST" if host is None else host
        self.client = client.SpeckleClient(host=host)
        self.client.authenticate_with_token(token)

        # # Check if authenticated
        # if self.client.account.token:
        #     print("✓ Authenticated")
        #
        #     # Get current user info
        #     user = self.client.active_user.get()
        #     print(f"Logged in as: {user.name}")
        #     print(f"Email: {user.email}")
        # else:
        #     print("✗ Not authenticated")

    # def get_project(self, stream_id: str, commit_id: Optional[str] = None):
    #     commit_id = (
    #         self.get_latest_commit_id(stream_id) if commit_id is None else commit_id
    #     )
    #     transport = ServerTransport(client=self.client, stream_id=stream_id)
    #     commit = self.client.commit.get(stream_id, commit_id)
    #     return operations.receive(
    #         obj_id=commit.referencedObject, remote_transport=transport
    #     )
    #
    # def get_latest_commit_id(self, stream_id: str, branch_name: Optional[str] = None):
    #     branch_name = "main" if branch_name is None else branch_name
    #     branch = self.client.branch.get(stream_id, branch_name, 1)
    #     return branch.commits.items[0].id

    # def get_metadata(self, stream_id: str):
    #     return self.client.stream.get(stream_id)

    @staticmethod
    def parse(
        base: objects.Base,
        parsed: dict[str, objects.Base] = None,
    ) -> dict[str, objects.Base]:
        parsed = {} if parsed is None else parsed

        if isinstance(base, objects.Base):
            if rk.graph.is_entity(base):
                if base["entityId"] not in parsed:
                    parsed[base["entityId"]] = base
                else:
                    existing = parsed[base["entityId"]]
                    if operations.serialize(existing) == operations.serialize(base):
                        pass
                    else:
                        print(
                            "Warning: Duplicate Entity {0} [{1}] found.".format(
                                base["entityId"], base["name"]
                            )
                        )
                        if rk.graph.is_assembly(existing) & rk.graph.is_entity(
                            base=base,
                            exclusive=True,
                        ):
                            print(
                                "Existing Entity is an Assembly while new Entity is not. Keeping Assembly."
                            )
                        elif rk.graph.is_assembly(base) & rk.graph.is_entity(
                            base=existing,
                            exclusive=True,
                        ):
                            print(
                                "New Entity is an Assembly while existing Entity is not. Replacing with Assembly."
                            )
                            parsed[base["entityId"]] = base
                        else:
                            raise Exception(
                                "Error: Hashes do not match. \n"
                                "{0}: {1}\n"
                                "{2}: {3}\n"
                                "Cannot recreate graph with dissimilar Entities".format(
                                    existing["entityId"],
                                    operations.serialize(existing),
                                    base["entityId"],
                                    operations.serialize(base),
                                )
                            )

            for member_name in base.get_dynamic_member_names():
                member = base[member_name]
                if isinstance(member, objects.Base):
                    parsed.update(Speckle.parse(base=member, parsed=parsed))
                elif isinstance(member, list):
                    for item in member:
                        parsed.update(Speckle.parse(base=item, parsed=parsed))
        return parsed

    @staticmethod
    def to_rk(bases: list[objects.Base], name: str, type: str) -> graph.Assembly:

        root = rk.graph.Assembly(name=name, type=type)
        entities = {base["entityId"]: rk.graph.Entity.from_base(base) for base in bases}

        assemblies = {}
        for assembly in [base for base in bases if rk.graph.is_assembly(base)]:
            subassembly = entities[assembly["entityId"]]
            edges = []
            for relationship in assembly["relationships"]:
                source = (
                    entities[relationship["source"]["entityId"]]
                    if relationship["source"] is not None
                    else subassembly
                )
                target = (
                    entities[relationship["target"]["entityId"]]
                    if relationship["target"] is not None
                    else subassembly
                )
                subassembly.add_relationship((source, target, relationship["type"]))
                root.add_relationship((source, target, relationship["type"]))

        return root
