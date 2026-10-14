"""Amount-independent Flow coordinates and fixed interval membership.

This module imports neither a dataframe engine nor execution. Both numerical and
symbolic consumers use these exact coordinate and interval rules.
"""

from __future__ import annotations
from bisect import bisect_right
from collections.abc import Sequence
from datetime import date
from rangekeeper.schema.records import Flow, Movement, Period


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
        period.check()
        if i and periods[i - 1].end_exclusive > period.start_inclusive:
            raise ValueError("resampling periods overlap or are unordered")
        starts.append(period.start_inclusive)
    groups = []
    for coordinate in coordinates:
        start = date.fromisoformat(coordinate[1])
        index = bisect_right(starts, start) - 1
        end = date.fromisoformat(coordinate[2]) if coordinate[0] == "period" else None
        if (
            index < 0
            or start >= periods[index].end_exclusive
            or (end is not None and end > periods[index].end_exclusive)
        ):
            raise ValueError("movement is outside or crosses target periods")
        groups.append(index)
    return tuple(groups)


def weights(coordinates: Sequence[tuple], *, elapsed: bool) -> tuple[float, ...]:
    """Return fixed observation or coverage-day weights, independent of knownness."""
    if elapsed and any(c[0] != "period" for c in coordinates):
        raise ValueError("elapsed weighting requires bounded movements")
    return tuple(
        (
            float((date.fromisoformat(c[2]) - date.fromisoformat(c[1])).days)
            if elapsed
            else 1.0
        )
        for c in coordinates
    )
