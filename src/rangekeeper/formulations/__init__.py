"""Pure declaration builders. Each submodule owns one mathematical responsibility."""

from . import account, expression, financial, flow, growth

__all__ = ["account", "expression", "financial", "flow", "growth", "build_formulation"]


from collections.abc import Sequence
from uuid import UUID
from .._schema.records import Expression, Formulation


def build_formulation(
    *,
    id: UUID,
    name: str,
    equations: Sequence[tuple[str, Expression]],
    values: Sequence[UUID]
) -> Formulation:
    """Own named predicates with stable IDs and whole-Value bindings.

    Equation keys must be unique. The supplied Expressions are detached and given
    occurrence-specific identities so trees can reuse symbols without duplicate
    ownership. This declares constraints only; no Model, solver or store is read.
    """
    from ._construction import construct

    if len({key for key, _ in equations}) != len(equations):
        raise ValueError("duplicate equation key")
    return construct(id, name, equations, values)
