"""The handle of a named Formulation in a ModelDraft.

``add_formulation(name=)`` and ``formulation(name=)`` on an entity handle return
a ``FormulationHandle``. Its ``equations(...)`` adds equations to that
Formulation, with the rules of ``equations(...)`` on the entity handle.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.model.expression.terms import Term
from rangekeeper.schema.records import Expression

if TYPE_CHECKING:
    # The draft makes handles and imports this module.
    from rangekeeper.model.draft import ModelDraft


@dataclass(frozen=True, slots=True, init=False)
class FormulationHandle:
    """A named Formulation of an entity in a draft, which adds equations to it.

    A named Formulation groups equations, such as "Funding", for displays and
    traces; it changes nothing in a solve. ``id`` is the UUID of the
    Formulation, ``name`` its name and ``owner`` the UUID of its entity. Two
    handles of one Formulation are equal. The display names the Formulation and
    its entity, for example ``<formulation 'Funding' on project>``.
    """

    id: UUID
    name: str
    owner: UUID
    _draft: "ModelDraft" = field(repr=False, compare=False)
    # The name or code of the owner, for the display only.
    _entity: str = field(repr=False, compare=False)

    def __init__(self) -> None:
        raise TypeError(
            "a draft makes FormulationHandles; call add_formulation() on an "
            "entity handle"
        )

    @classmethod
    def _of(
        cls,
        draft: "ModelDraft",
        *,
        id: UUID,
        name: str,
        owner: UUID,
        entity: str,
    ) -> "FormulationHandle":
        """Return the handle of a Formulation of the entity ``owner`` in ``draft``."""
        handle = object.__new__(cls)
        fields = {
            "id": id,
            "name": name,
            "owner": owner,
            "_draft": draft,
            "_entity": entity,
        }
        for key, item in fields.items():
            object.__setattr__(handle, key, item)
        return handle

    def __repr__(self) -> str:
        return f"<formulation {self.name!r} on {self._entity}>"

    def equations(self, *equations: str | Term | Expression) -> None:
        """Add one equation or several to this Formulation.

        The equations follow the rules of ``equations`` on the entity handle:
        text names the keys of the entity, and ``code.key`` names a key of
        another entity. A call that fails adds no equation.
        """
        self._draft._add_to(self.id, owner=self.owner, equations=equations)


__all__ = ["FormulationHandle"]
