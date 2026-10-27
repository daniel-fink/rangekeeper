"""Calculations on known inputs; importing this package loads no numerical backend.

The submodules projection, financial, account and dynamics load on first access.
Intrinsic Flow and Distribution operations are record methods. Calculations
return detached results and never publish Runs.
"""

from rangekeeper.shared.exports import lazy as _lazy

_MODULES = {"account", "dynamics", "financial", "projection"}
__all__ = sorted(_MODULES)
__getattr__, __dir__ = _lazy(__name__, modules=_MODULES)
