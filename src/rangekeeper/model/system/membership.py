"""Assembly membership in one Model; unrelated to Relationship direction."""

from uuid import UUID
from rangekeeper.model import Model, Entity, Assembly, Relationship
from rangekeeper.shared.errors import ReferenceTypeError


def _assembly(model: Model, id: UUID) -> Assembly:
    if not isinstance(model, Model):
        raise TypeError("model must be a Model")
    entity = model.entity(id)
    if not isinstance(entity, Assembly):
        raise ReferenceTypeError(f"{id} is not an Assembly")
    return entity


def entities_in(
    model: Model,
    assembly: UUID,
    *,
    recursive: bool = False,
) -> tuple[Entity, ...]:
    """Return unique members, excluding the root, in Model entity encounter order.

    Recursion includes nested Assemblies and deduplicates shared descendants.
    Membership neither follows Relationships nor implies physical containment.
    """
    root = _assembly(model, assembly)
    if not isinstance(recursive, bool):
        raise TypeError("recursive must be a bool")
    found = set(root.entities or ())
    pending = list(found) if recursive else []
    while pending:
        member = model.entity(pending.pop())
        if isinstance(member, Assembly):
            unseen = set(member.entities or ()) - found
            found.update(unseen)
            pending.extend(unseen)
    return tuple(entity for entity in model.find_entities() if entity.id in found)


def relationships_in(model: Model, assembly: UUID) -> tuple[Relationship, ...]:
    """Return direct declared Relationship members in System declaration order."""
    root = _assembly(model, assembly)
    members = set(root.relationships or ())
    return (
        tuple(item for item in (model.system.relationships or ()) if item.id in members)
        if model.system
        else ()
    )


def containing_assemblies(
    model: Model,
    entity: UUID,
    *,
    recursive: bool = False,
) -> tuple[Assembly, ...]:
    """Return direct containers or all ancestors once, in Assembly declaration order."""
    if not isinstance(model, Model):
        raise TypeError("model must be a Model")
    model.entity(entity)
    if not isinstance(recursive, bool):
        raise TypeError("recursive must be a bool")
    assemblies = (model.system.assemblies or ()) if model.system else ()
    found: set[UUID] = set()
    frontier = {entity}
    while frontier:
        parents = {
            item.id
            for item in assemblies
            if item.id not in found and frontier.intersection(item.entities or ())
        }
        found.update(parents)
        frontier = parents if recursive else set()
    return tuple(item for item in assemblies if item.id in found)


__all__ = ["entities_in", "relationships_in", "containing_assemblies"]
