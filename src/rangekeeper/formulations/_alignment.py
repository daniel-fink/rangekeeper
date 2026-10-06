"""Explicit shape matching; no interpolation, positional matching or amount reads."""

from uuid import UUID
from ..model import Model
from ..model.flow import Flow, Movement, movement_coordinate
from .._schema.records import ValueReference


def shape(model: Model, value: UUID) -> Flow:
    record = model.value(value)
    if record.kind != "flow" or record.flow is None:
        raise ValueError("builder requires a declared Flow shape")
    return record.flow


def aligned(model: Model, sources, result):
    destination = shape(model, result)
    maps = [
        {movement_coordinate(m): m for m in shape(model, source).movements}
        for source in sources
    ]
    coordinates = {movement_coordinate(m) for m in destination.movements}
    if len(coordinates) != len(destination.movements) or any(
        len(mapping) != len(shape(model, source).movements)
        for mapping, source in zip(maps, sources)
    ):
        raise ValueError(
            "duplicate coordinates make alignment ambiguous; use explicit key equations"
        )
    if any(set(mapping) != coordinates for mapping in maps):
        raise ValueError(
            "Flow coordinates do not match; supply an explicit mapping for lagged relationships"
        )
    return [
        (m, tuple(mapping[movement_coordinate(m)] for mapping in maps))
        for m in destination.movements
    ]


def target(value: UUID, item: Movement) -> ValueReference:
    return ValueReference(value=value, movement=item.key)
