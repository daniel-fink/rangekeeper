"""Explicit innovation generation; no hidden global random state."""

from ...model.distribution import Distribution
from ..distribution import sample


def sample_noise(
    distribution: Distribution, *, count: int, generator
) -> tuple[float, ...]:
    """Draw exactly count innovations from the supplied random generator."""
    return sample(distribution, size=count, generator=generator)
