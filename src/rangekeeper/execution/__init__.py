"""Affine scalar execution; numerical backends remain optional and process-local."""

from rangekeeper.execution.acceptance import Tolerances
from rangekeeper.execution.executor import Executor

__all__ = ["Executor", "Tolerances"]
