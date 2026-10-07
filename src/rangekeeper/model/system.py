"""Schema-derived system records; fields and constructors are generated from LinkML."""

from .._schema.records import System as System
from uuid import UUID
from .._validation import require, require_acyclic


__all__ = ["System"]


def check_system(system, *, scope, locations):
    """Check system references, code scopes and Assembly membership."""
    entities = {str(identity): record for identity, record in scope.entities.items()}
    relationships = {r["id"]: r for r in system.get("relationships") or []}
    assemblies = {r["id"]: r for r in system.get("assemblies") or []}
    codes = set()
    for identity, record in entities.items():
        code = record.get("code")
        if code is not None:
            require(
                code not in codes,
                f"duplicate Entity/Assembly code: {code}",
                code="semantic.unique",
                path=locations[identity] + "/code",
            )
            codes.add(code)
    targets = dict(
        entities,
        **relationships,
        **{str(identity): record for identity, record in scope.values.items()},
    )
    for obj in list(entities.values()) + list(relationships.values()):
        if obj.get("classification") is not None:
            require(
                UUID(obj["classification"]) in scope.classifications,
                "unknown Classification",
                path=locations[obj["id"]] + "/classification",
            )
        for label in (obj.get("characteristics") or {}).get("labels") or []:
            targets[label["id"]] = label
            refs = label.get("classifications") or []
            require(
                len(refs) == len(set(refs)),
                "duplicate Label Classification",
                path=locations[label["id"]] + "/classifications",
            )
            require(
                all(UUID(r) in scope.classifications for r in refs),
                "unknown Label Classification",
                path=locations[label["id"]] + "/classifications",
            )
    for relationship in relationships.values():
        require(
            relationship["source"] in entities and relationship["target"] in entities,
            "unknown or non-Entity Relationship endpoint",
            path=locations[relationship["id"]],
        )
    for assembly in assemblies.values():
        members = assembly.get("entities") or []
        links = assembly.get("relationships") or []
        require(
            len(members) == len(set(members)) and len(links) == len(set(links)),
            "duplicate Assembly membership",
            path=locations[assembly["id"]],
        )
        require(
            all(m in entities for m in members),
            "unknown Assembly Entity",
            path=locations[assembly["id"]] + "/entities",
        )
        require(
            all(r in relationships for r in links),
            "unknown Assembly Relationship",
            path=locations[assembly["id"]] + "/relationships",
        )
        endpoints = set(members) | {assembly["id"]}
        for link in links:
            relation = relationships[link]
            require(
                relation["source"] in endpoints and relation["target"] in endpoints,
                "Assembly Relationship endpoint outside membership",
                path=locations[assembly["id"]] + "/relationships",
            )
    require_acyclic(
        {
            a["id"]: [i for i in a.get("entities") or [] if i in assemblies]
            for a in assemblies.values()
        },
        "Assembly membership",
        path="/system/assemblies",
    )

    return targets
