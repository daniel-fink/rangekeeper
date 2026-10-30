"""The path generator extension point and its registry (ADR-013, ADR-014).

A path generator makes market paths from parameters. It is registered by
name in ``generators``; an installed distribution can declare one in the entry
point group ``rangekeeper.market``. The capture record of the paths keeps the
name, the fingerprint and the parameters, so ``Paths.regenerate`` finds the
generator again and makes the paths with another seed.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from rangekeeper.duration import Period
from rangekeeper.schema.records import PathParameter
from rangekeeper.shared.registry import Registry

if TYPE_CHECKING:
    from rangekeeper.market.paths import Paths

__all__ = ["PathGenerator", "generators"]


@runtime_checkable
class PathGenerator(Protocol):
    """A method that makes market paths from parameters, Periods, a seed and a count.

    ``parameters`` are the constants or distributions of each series, as the
    capture record keeps them. ``seed`` is None when nothing is random. The
    same parameters, Periods, seed and count make the same paths, whatever
    the process or the order of the calls.
    """

    def generate(
        self,
        *,
        parameters: Sequence[PathParameter],
        periods: Sequence[Period],
        seed: int | None,
        count: int,
    ) -> "Paths":
        """Return ``count`` paths over ``periods``, with the capture record."""
        ...


generators: Registry[PathGenerator] = Registry("market", PathGenerator)
