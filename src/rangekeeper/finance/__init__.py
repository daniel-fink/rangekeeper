"""Calculations on known inputs; importing this package loads no numerical backend.

``pv``, ``npv``, ``irr`` and ``payment`` take Flows and Quantities with units
and return them. The submodule financial loads on first access. Intrinsic Flow
and Distribution operations are record methods. Calculations return detached
results and never publish Runs.
"""

from rangekeeper.finance._valuation import irr, npv, payment, pv
from rangekeeper.shared.exports import lazy as _lazy

_MODULES = {"financial"}
__all__ = ["irr", "npv", "payment", "pv", *sorted(_MODULES)]
__getattr__, __dir__ = _lazy(__name__, modules=_MODULES)
