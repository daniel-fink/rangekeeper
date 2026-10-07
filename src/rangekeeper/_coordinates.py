"""Duplicate-aware Movement indexing without an ordering or join policy."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model.flow import Movement


def index(movements: Iterable[Movement]) -> dict[tuple, Movement]:
    """Index exact coordinates in encounter order, rejecting ambiguous matches."""
    result = {}
    for movement in movements:
        coordinate = movement.coordinate
        if coordinate in result:
            raise ValueError(
                "duplicate coordinates make alignment ambiguous; use explicit key equations"
            )
        result[coordinate] = movement
    return result
