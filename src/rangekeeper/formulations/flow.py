"""Finite Flow equations. Shapes are read; recorded magnitudes remain passive."""

from collections.abc import Sequence
from uuid import UUID
from ..model import Model
from .._schema.records import Formulation, Reference
from ._alignment import aligned, shape, target, owner
from ._construction import construct
from .expression import reference, equal, add, multiply, sum_expressions


def build_sum(
    model: Model, *, id: UUID, sources: Sequence[UUID], result: UUID
) -> Formulation:
    """Declare an elementwise sum. All coordinates and units must be compatible.

    Empty sources and mismatched coordinates raise ValueError. No Model is changed.
    """
    if not sources:
        raise ValueError("sum requires sources")
    equations = [
        (
            str(m.id),
            equal(
                reference(target(result, m)),
                sum_expressions(
                    [reference(target(v, s)) for v, s in zip(sources, matches)]
                ),
            ),
        )
        for m, matches in aligned(model, sources, result)
    ]
    return construct(id, "sum", equations, (*sources, result))


def build_scale(
    model: Model, *, id: UUID, source: UUID, factor: Reference | UUID, result: UUID
) -> Formulation:
    """Declare source times a scalar or aligned Flow factor, retaining product units."""
    sources = (source,) if isinstance(factor, Reference) else (source, factor)
    equations = []
    for m, matches in aligned(model, sources, result):
        ref = factor if isinstance(factor, Reference) else target(factor, matches[1])
        equations.append(
            (
                str(m.id),
                equal(
                    reference(target(result, m)),
                    multiply(reference(target(source, matches[0])), reference(ref)),
                ),
            )
        )
    return construct(
        id,
        "scale",
        equations,
        (
            source,
            owner(model, factor) if isinstance(factor, Reference) else factor,
            result,
        ),
    )


def build_accumulation(
    model: Model, *, id: UUID, source: UUID, initial: Reference, result: UUID
) -> Formulation:
    """Declare closing balance = prior balance + signed movement for each period.

    The initial balance is a symbol. The source's sign determines inflow/outflow;
    no overdraft branch or hidden initial zero is introduced.
    """
    equations, prior = [], initial
    for m, matches in aligned(model, (source,), result):
        current = target(result, m)
        equations.append(
            (
                str(m.id),
                equal(
                    reference(current),
                    add(reference(prior), reference(target(source, matches[0]))),
                ),
            )
        )
        prior = current
    return construct(
        id, "accumulation", equations, (source, owner(model, initial), result)
    )
