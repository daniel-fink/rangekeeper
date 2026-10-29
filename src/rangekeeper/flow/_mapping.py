"""Amount-independent Flow coordinates and fixed interval membership.

This module imports neither a dataframe engine nor execution. Both numerical and
symbolic consumers use these exact coordinate and interval rules.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from datetime import date

from rangekeeper.duration import Period
from rangekeeper.flow._flow import Flow, Movement
from rangekeeper.flow._options import ResampleMethod

# The resample methods that weight each value.
MEANS = frozenset({ResampleMethod.MEAN, ResampleMethod.ELAPSED_MEAN})


def alignment(
    flows: Sequence[Flow], reference: Flow
) -> list[tuple[Movement, tuple[Movement, ...]]]:
    """Match exact coordinate sets in reference order, without reading amounts."""
    coordinates = reference.coordinate_index()
    maps = [flow.coordinate_index() for flow in flows]
    if any(set(mapping) != set(coordinates) for mapping in maps):
        raise ValueError(
            "Flow coordinates do not match; supply an explicit mapping for lagged relationships"
        )
    return [
        (movement, tuple(mapping[key] for mapping in maps))
        for key, movement in coordinates.items()
    ]


def period_indices(
    coordinates: Sequence[tuple], periods: Sequence[Period]
) -> tuple[int, ...]:
    """Map each coordinate to one complete containing period in O(n log p)."""
    starts = []
    for i, period in enumerate(periods):
        if i and periods[i - 1].end > period.start:
            raise ValueError("resampling periods overlap or are unordered")
        starts.append(period.start)
    groups = []
    for coordinate in coordinates:
        start = date.fromisoformat(coordinate[1])
        index = bisect_right(starts, start) - 1
        end = date.fromisoformat(coordinate[2]) if coordinate[0] == "period" else None
        if (
            index < 0
            or start >= periods[index].end
            or (end is not None and end > periods[index].end)
        ):
            raise ValueError("movement is outside or crosses target periods")
        groups.append(index)
    return tuple(groups)


def weights(
    coordinates: Sequence[tuple], *, method: ResampleMethod
) -> tuple[float, ...]:
    """Return the fixed weight of each coordinate, independent of knownness.

    ``ELAPSED_MEAN`` weights each Period by the days that it covers; every other
    method gives each value the weight 1.
    """
    if method is not ResampleMethod.ELAPSED_MEAN:
        return (1.0,) * len(coordinates)
    if any(c[0] != "period" for c in coordinates):
        raise ValueError("an elapsed mean requires bounded movements")
    return tuple(
        float((date.fromisoformat(c[2]) - date.fromisoformat(c[1])).days)
        for c in coordinates
    )
