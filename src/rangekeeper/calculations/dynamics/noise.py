"""Explicit innovation generation; no hidden global random state."""

from ...model.distribution import Distribution


def sample_noise(
    distribution: Distribution, *, count: int, generator
) -> tuple[float, ...]:
    """Draw exactly count innovations from the supplied random generator."""
    return distribution.sample(size=count, generator=generator)
