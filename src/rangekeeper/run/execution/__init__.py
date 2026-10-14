"""Affine scalar execution; numerical backends remain optional and process-local."""

from rangekeeper.run.execution.executor import Executor
from rangekeeper.run.execution.acceptance import Tolerances

__all__ = ["Executor", "Tolerances"]
