"""Finite Flow equations. Shapes are read; recorded magnitudes remain passive."""

from collections.abc import Sequence, Mapping
from typing import TYPE_CHECKING
import math

if TYPE_CHECKING:
    from rangekeeper.calculations.series import ResamplingMethod, MeanWeighting
from uuid import UUID
from rangekeeper.model import Model
from rangekeeper.schema.records import Formulation, Reference
from rangekeeper.model.formulation.authoring import declare
from rangekeeper.model.scope import target_value
from rangekeeper.model.expression.authoring import (
    reference,
    equal,
    add,
    multiply,
    sum as expression_sum,
)


from rangekeeper.schema.enums import ValueKind
from rangekeeper.model.flux import Flow, Stream, Movement, MissingValueHandling


def shape(model: Model, value: UUID) -> Flow:
    record = model.value(value)
    if record.kind is not ValueKind.FLOW or record.flow is None:
        raise ValueError("builder requires a declared Flow shape")
    return record.flow


def aligned(
    model: Model,
    members: Sequence[UUID],
    reference: UUID,
    *,
    shapes: Mapping[UUID, Flow] | None = None,
) -> list[tuple[Movement, tuple[Movement, ...]]]:
    """Match member coordinates in reference order; amounts and solve roles are unused."""
    from rangekeeper.model._flow_mapping import alignment

    prepared = dict(shapes or {})
    for identity in (*members, reference):
        if identity not in prepared:
            prepared[identity] = shape(model, identity)
    return alignment([prepared[identity] for identity in members], prepared[reference])


def sum(
    model: Model,
    *,
    id: UUID,
    summands: Stream | Sequence[UUID],
    total: UUID,
) -> Formulation:
    """Declare an elementwise sum. All coordinates and units must be compatible.

    Summands are Flow Value IDs with compatible units; total is the related Flow.
    Empty summands and mismatched coordinates raise ValueError. No Model is changed.
    """
    shapes = None
    if isinstance(summands, Stream):
        if not summands._symbolic or summands.model is None:
            raise ValueError(
                "declare intermediate Flow Values and relationships for transformed or detached Streams"
            )
        if summands.model.id != model.id or summands.model._record != model._record:
            raise ValueError("Stream must pin the exact Model revision and content")
        shapes = dict(zip(summands.value_ids, summands.flows))
        summands = summands.value_ids
    summands = tuple(summands)
    if len(set(summands)) != len(summands):
        raise ValueError("duplicate summand Value")
    if not summands:
        raise ValueError("sum requires summands")
    equations = [
        (
            str(m.id),
            equal(
                reference(Reference(target=m.id)),
                expression_sum(
                    [
                        reference(Reference(target=s.id))
                        for v, s in zip(summands, matches)
                    ]
                ),
            ),
        )
        for m, matches in aligned(model, summands, total, shapes=shapes)
    ]
    return declare(id, "sum", equations, (*summands, total))


def scale(
    model: Model,
    *,
    id: UUID,
    multiplicand: UUID,
    multiplier: Reference | UUID,
    product: UUID,
) -> Formulation:
    """Declare multiplicand times multiplier equals product.

    Multiplicand and product identify Flow Values. Multiplier is a scalar
    Reference or aligned Flow Value UUID; product units retain both factors."""
    sources = (
        (multiplicand,)
        if isinstance(multiplier, Reference)
        else (multiplicand, multiplier)
    )
    equations = []
    for m, matches in aligned(model, sources, product):
        ref = (
            multiplier
            if isinstance(multiplier, Reference)
            else Reference(target=matches[1].id)
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
            multiplicand,
            (
                target_value(model, multiplier).id
                if isinstance(multiplier, Reference)
                else multiplier
            ),
            product,
        ),
    )


def accumulate(
    model: Model,
    *,
    id: UUID,
    increments: UUID,
    initial: Reference,
    accumulation: UUID,
) -> Formulation:
    """Declare closing balance = prior balance + signed movement for each period.

    Increments and accumulation identify compatible-unit Flow Values.
    Initial is a scalar Reference in those units. The increment sign determines inflow/outflow;
    no overdraft branch or hidden initial zero is introduced.
    """
    equations, prior = [], initial
    for m, matches in aligned(model, (increments,), accumulation):
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
        id,
        "accumulation",
        equations,
        (increments, target_value(model, initial).id, accumulation),
    )


def _resampled_terms(sequence: Flow, periods, *, method, weighting, missing):
    """Use fixed structural membership, never known-only numerical masks."""
    from rangekeeper.calculations.series import ResamplingMethod, MeanWeighting
    from rangekeeper.model._flow_mapping import period_indices, weights
    from rangekeeper.model.expression.authoring import literal

    if not isinstance(method, ResamplingMethod):
        raise TypeError("method must be a ResamplingMethod")
    if method in (ResamplingMethod.MIN, ResamplingMethod.MAX):
        raise ValueError(
            "MIN/MAX formulations require an unsupported piecewise solver capability"
        )
    if missing not in (MissingValueHandling.ERROR, MissingValueHandling.ZERO):
        raise ValueError(
            "passive resampling permits ERROR or explicit empty-group ZERO; unknown symbols cannot be skipped"
        )
    if weighting is not None and not isinstance(weighting, MeanWeighting):
        raise TypeError("weighting must be a MeanWeighting")
    if (method is ResamplingMethod.MEAN) != (weighting is not None):
        raise ValueError(
            "means require explicit weighting; weighting applies only to means"
        )
    coordinates = tuple(sequence.coordinate_index())
    groups: list[list[tuple[Movement, float]]] = [[] for _ in periods]
    indices = period_indices(coordinates, periods)
    fixed = weights(coordinates, elapsed=weighting is MeanWeighting.ELAPSED)
    for movement, group_index, weight in zip(sequence.movements, indices, fixed):
        groups[group_index].append((movement, weight))
    expressions = []
    for group in groups:
        if not group:
            if missing is MissingValueHandling.ERROR:
                raise ValueError("empty target period requires explicit ZERO policy")
            expressions.append(literal(0, sequence.units))
            continue
        if method is ResamplingMethod.FIRST:
            group = group[:1]
        elif method is ResamplingMethod.LAST:
            group = group[-1:]
        denominator = math.fsum(weight for _, weight in group)
        terms = []
        for movement, weight in group:
            term = reference(Reference(target=movement.id))
            if method is ResamplingMethod.MEAN:
                term = multiply(term, literal(weight / denominator))
            terms.append(term)
        expressions.append(expression_sum(terms))
    return expressions


def resample(
    model: Model,
    *,
    id: UUID,
    sequence: UUID,
    resampled: UUID,
    method: "ResamplingMethod",
    weighting: "MeanWeighting | None" = None,
    missing: MissingValueHandling = MissingValueHandling.ERROR,
) -> Formulation:
    """Relate a sequence to a declared period grid in compatible units.

    All declared source Movements participate even with null amounts. SUM, fixed
    MEAN and FIRST/LAST are supported. No roles, allocation or amounts are inferred.
    """
    source, grouped = shape(model, sequence), shape(model, resampled)
    if any(m.period is None for m in grouped.movements):
        raise ValueError("resampled Flow requires bounded periods")
    terms = _resampled_terms(
        source,
        tuple(m.period for m in grouped.movements),
        method=method,
        weighting=weighting,
        missing=missing,
    )
    equations = [
        (str(m.id), equal(reference(Reference(target=m.id)), term))
        for m, term in zip(grouped.movements, terms)
    ]
    return declare(id, "resample", equations, (sequence, resampled))
