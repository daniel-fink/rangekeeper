"""Old Graph algorithms retained for unmigrated tables, adapters and workflows.

These operations accept the old Graph only, without converting to Model. Remove
this package after its remaining consumers migrate in Step 6C–F.
"""
from .view import View as View
from . import reduction as reduction

__all__ = ["View", "reduction"]
