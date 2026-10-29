"""Rank and free-variable analysis of affine rows, in pure Python, before any backend."""

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Analysis:
    """What the rows of an affine problem fix, independent of any backend.

    ``rank`` is the numerical rank of the equality rows over ``unknown_count``
    unknowns. ``free`` names the unknowns that no row constrains, in unknown
    order. ``has_bounds`` is true when an inequality row exists; bounds can
    restrict directions that the equality rank leaves free.
    """

    rank: int
    unknown_count: int
    free: tuple[UUID, ...]
    has_bounds: bool

    @property
    def underdetermined(self) -> bool:
        """Return whether the equality rank is below the number of unknowns."""
        return self.rank < self.unknown_count


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
