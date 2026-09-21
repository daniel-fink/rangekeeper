"""Sequential catalog execution and operation bookkeeping, independent of formats."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.graph.provenance import Claim

if TYPE_CHECKING:
    from .specification import StepSpec

from rangekeeper.graph.operation import Operation, fingerprint
from rangekeeper.graph.provenance import Method

from ._contracts import ExecutionContext, Produced
from .catalog import OPERATIONS


class Unavailable(Exception):
    """Propagate native diagnostics without discarding them or catching programmer errors."""

    def __init__(self, diagnostics):
        self.diagnostics = diagnostics


def execute_steps(
    steps: Sequence[StepSpec],
    *,
    root: Path,
    namespace: UUID,
    settings: Claim[str],
    operations: list[Operation],
) -> tuple[dict[str, Produced], dict[str, object]]:
    """Only declared prerequisites are visible to a handler; outputs remain native."""
    produced = {}
    records = {}
    for step in steps:
        handler = OPERATIONS[step.operation]
        inputs = MappingProxyType({name: produced[name].value for name in step.inputs})
        invocation = Operation(
            method=Method(code="rk.workflow." + step.operation, version="1"),
            specification=step.to_mapping(),
            inputs={name: produced[name].fingerprint for name in step.inputs},
        )
        operations.append(invocation)
        result = handler.execute(
            step.request, inputs, ExecutionContext(root, namespace, settings, step.id)
        )
        operations.append(result.operation)
        if result.output is None:
            raise Unavailable(result.diagnostics)
        produced[step.id] = handler.describe(result.output)
        records[step.id] = {
            "dispatch": fingerprint(invocation),
            "native": (fingerprint(result.operation),),
        }
    return produced, records
