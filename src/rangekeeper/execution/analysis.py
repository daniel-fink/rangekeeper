"""Rank and free-variable analysis of affine rows, in pure Python, before any backend."""

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Analysis:
    """What the rows of an affine problem fix, independent of any backend.

    ``equality_rank`` is the numerical rank of the equality rows over
    ``unknown_count`` unknowns. ``undetermined`` names the unknowns that the
    equality rows do not fix, in unknown order: each unknown that no row
    reads, and each unknown whose value changes along a direction that the
    rows leave free. ``bounded`` names the
    undetermined unknowns that an inequality row reads, in unknown order: a
    bound can restrict them, but the rank analysis does not say how far.
    """

    equality_rank: int
    unknown_count: int
    undetermined: tuple[UUID, ...] = ()
    bounded: tuple[UUID, ...] = ()

    @property
    def underdetermined(self) -> bool:
        """Return whether the equality rank is below the number of unknowns."""
        return self.equality_rank < self.unknown_count


def equality_rank(rows: Sequence[Mapping[UUID, float]], unknown_count: int) -> int:
    """Return the numerical rank of sparse rows by Gaussian elimination.

    Each row is divided by its largest absolute coefficient. Elimination uses
    the largest remaining entry of each row as its pivot. An entry at or below
    ``max(len(rows), unknown_count)`` times the machine epsilon counts as zero,
    the order of NumPy's default threshold for ``matrix_rank``.
    """
    tolerance = max(len(rows), unknown_count, 1) * sys.float_info.epsilon
    pivots: list[tuple[UUID, dict[UUID, float]]] = []
    for coefficients in rows:
        largest = max((abs(value) for value in coefficients.values()), default=0.0)
        if largest == 0:
            continue
        row = {key: value / largest for key, value in coefficients.items()}
        for column, pivot in pivots:
            factor = row.get(column)
            if not factor:
                continue
            factor /= pivot[column]
            for key, value in pivot.items():
                row[key] = row.get(key, 0.0) - factor * value
            row = {key: value for key, value in row.items() if abs(value) > tolerance}
        if row:
            column = max(row, key=lambda key: abs(row[key]))
            pivots.append((column, row))
    return len(pivots)


def undetermined(
    rows: Sequence[Mapping[UUID, float]], unknowns: Sequence[UUID]
) -> tuple[UUID, ...]:
    """Return the unknowns that the equality rows do not fix, in unknown order.

    The rows are reduced to reduced row echelon form, with the pivots and the
    zero threshold of ``equality_rank``. An unknown without a pivot is free. A
    pivot unknown is undetermined when its reduced row keeps a coefficient on a
    free unknown: its value then changes with that free unknown.
    """
    tolerance = max(len(rows), len(unknowns), 1) * sys.float_info.epsilon
    pivots: dict[UUID, dict[UUID, float]] = {}
    for coefficients in rows:
        largest = max((abs(value) for value in coefficients.values()), default=0.0)
        if largest == 0:
            continue
        row = {key: value / largest for key, value in coefficients.items()}
        for column, pivot in pivots.items():
            factor = row.get(column)
            if factor:
                row = _eliminate(row, pivot, factor=factor, tolerance=tolerance)
        if not row:
            continue
        column = max(row, key=lambda key: abs(row[key]))
        scale = row[column]
        row = {key: value / scale for key, value in row.items()}
        for other, pivot in pivots.items():
            factor = pivot.get(column)
            if factor:
                pivots[other] = _eliminate(
                    pivot, row, factor=factor, tolerance=tolerance
                )
        pivots[column] = row
    found = set()
    for column, row in pivots.items():
        if any(key not in pivots for key in row):
            found.add(column)
    return tuple(id for id in unknowns if id not in pivots or id in found)


def _eliminate(
    row: Mapping[UUID, float],
    pivot: Mapping[UUID, float],
    *,
    factor: float,
    tolerance: float,
) -> dict[UUID, float]:
    """Subtract ``factor`` times a pivot row whose pivot is 1; drop entries near 0."""
    result = dict(row)
    for key, value in pivot.items():
        result[key] = result.get(key, 0.0) - factor * value
    return {key: value for key, value in result.items() if abs(value) > tolerance}
