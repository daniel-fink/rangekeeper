"""Finite Flow equations. Shapes are read; recorded magnitudes remain passive."""

from collections.abc import Sequence
from uuid import UUID
from ..model import Model
from .._schema.records import Formulation, Reference
from .authoring import declare
from ..model.scope import target_value
from .expression import reference, equal, add, multiply, sum as expression_sum


from .._coordinates import index
from .._schema.enums import ValueKind
from ..model.flow import Flow


def shape(model: Model, value: UUID) -> Flow:
    record = model.value(value)
    if record.kind is not ValueKind.FLOW or record.flow is None:
        raise ValueError("builder requires a declared Flow shape")
    return record.flow


def aligned(model: Model, sources, result, *, shapes=None):
    """Match exact coordinate sets, retaining destination order and unresolved amounts.

    A caller that already prepared shapes can supply its operation-local mapping.
    Each declared shape is resolved once in this call.
    """
    prepared = dict(shapes or {})
    for identity in (*sources, result):
        if identity not in prepared:
            prepared[identity] = shape(model, identity)
    destination = prepared[result]
    coordinates = index(destination.movements)
    maps = [index(prepared[source].movements) for source in sources]
    if any(set(mapping) != set(coordinates) for mapping in maps):
        raise ValueError(
            "Flow coordinates do not match; supply an explicit mapping for lagged relationships"
        )
    return [
        (movement, tuple(mapping[coordinate] for mapping in maps))
        for coordinate, movement in coordinates.items()
    ]


def sum(
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
                reference(Reference(target=m.id)),
                expression_sum(
                    [
                        reference(Reference(target=s.id))
                        for v, s in zip(sources, matches)
                    ]
                ),
            ),
        )
        for m, matches in aligned(model, sources, result)
    ]
    return declare(id, "sum", equations, (*sources, result))


def scale(
    model: Model, *, id: UUID, source: UUID, factor: Reference | UUID, result: UUID
) -> Formulation:
    """Declare source times a scalar or aligned Flow factor, retaining product units."""
    sources = (source,) if isinstance(factor, Reference) else (source, factor)
    equations = []
    for m, matches in aligned(model, sources, result):
        ref = (
            factor if isinstance(factor, Reference) else Reference(target=matches[1].id)
        )
        equations.append(
            (
                str(m.id),
                equal(
                    reference(Reference(target=m.id)),
                    multiply(
                        reference(Reference(target=matches[0].id)), reference(ref)
                    ),
                ),
            )
        )
    return declare(
        id,
        "scale",
        equations,
        (
            source,
            target_value(model, factor).id if isinstance(factor, Reference) else factor,
            result,
        ),
    )


def accumulate(
    model: Model, *, id: UUID, source: UUID, initial: Reference, result: UUID
) -> Formulation:
    """Declare closing balance = prior balance + signed movement for each period.

    The initial balance is a symbol. The source's sign determines inflow/outflow;
    no overdraft branch or hidden initial zero is introduced.
    """
    equations, prior = [], initial
    for m, matches in aligned(model, (source,), result):
        current = Reference(target=m.id)
        equations.append(
            (
                str(m.id),
                equal(
                    reference(current),
                    add(reference(prior), reference(Reference(target=matches[0].id))),
                ),
            )
        )
        prior = current
    return declare(
        id, "accumulation", equations, (source, target_value(model, initial).id, result)
    )
