"""Affine scalar execution; numerical backends remain optional and process-local."""

from .executor import Executor
from .acceptance import Tolerances

__all__ = ["Executor", "Tolerances"]
