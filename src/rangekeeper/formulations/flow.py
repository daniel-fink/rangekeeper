"""Finite Flow equations. Shapes are read; recorded magnitudes remain passive."""

from collections.abc import Sequence
from uuid import UUID
from ..model import Model
from .._schema.records import Formulation, ValueReference
from ._alignment import aligned, shape, target
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
            m.key,
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
    model: Model, *, id: UUID, source: UUID, factor: ValueReference | UUID, result: UUID
) -> Formulation:
    """Declare source times a scalar or aligned Flow factor, retaining product units."""
    sources = (source,) if isinstance(factor, ValueReference) else (source, factor)
    equations = []
    for m, matches in aligned(model, sources, result):
        ref = (
            factor if isinstance(factor, ValueReference) else target(factor, matches[1])
        )
        equations.append(
            (
                m.key,
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
            factor.value if isinstance(factor, ValueReference) else factor,
            result,
        ),
    )


def build_accumulation(
    model: Model, *, id: UUID, source: UUID, initial: ValueReference, result: UUID
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
                m.key,
                equal(
                    reference(current),
                    add(reference(prior), reference(target(source, matches[0]))),
                ),
            )
        )
        prior = current
    return construct(id, "accumulation", equations, (source, initial.value, result))
