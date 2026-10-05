"""Symmetric and asymmetric cycles with a bounded numerical root calculation."""

import math


def calculate_cycle(
    *,
    count: int,
    period: float,
    phase: float,
    amplitude: float,
    asymmetry: float = 0,
    tolerance: float = 1e-10
) -> tuple[float, ...]:
    """Evaluate a sine or the legacy sheared sine; zero asymmetry is exactly sine.

    Restrict shear to (-1, 1) so the implicit equation has a unique root. The
    bisection interval follows the sine bound and iteration count is finite.
    """
    if (
        type(count) is not int
        or count < 0
        or period <= 0
        or not -1 < asymmetry < 1
        or not 0 < tolerance < 1
    ):
        raise ValueError("invalid cycle parameters")
    if not all(math.isfinite(x) for x in (period, phase, amplitude, asymmetry)):
        raise ValueError("cycle parameters must be finite")
    values = []
    for i in range(count):
        angle = (i - phase) * 2 * math.pi / period
        if asymmetry == 0:
            values.append(amplitude * math.sin(angle))
            continue
        low, high = -1.0, 1.0
        for _ in range(math.ceil(math.log2(2 / tolerance)) + 1):
            mid = (low + high) / 2
            # y = sin(angle - shear*y), equivalent to the old auxiliary-root form.
            if mid - math.sin(angle - asymmetry * mid) < 0:
                low = mid
            else:
                high = mid
        values.append(amplitude * (low + high) / 2)
    return tuple(values)
