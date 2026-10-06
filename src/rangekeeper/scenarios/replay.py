"""Replay captured calculations without asking any generator for another draw."""

from uuid import UUID
from typing import Any, cast
from ..model import Model
from .market import captured_inputs, _flow
from ._paths import construct_paths
from .view import Market


def replay(model: Model, *, realization: UUID | None = None) -> Market:
    """Check stored paths against captured inputs and return the same immutable Model.

    Missing inputs, mismatched paths and changed calculations raise ValueError.
    Stored paths remain ordinary usable Flows even when replay is unavailable in
    a different implementation version. No file, store or random state is touched.
    """
    candidates = (
        [
            r
            for r in model.provenance.scenarios or ()
            if realization is None or r.id == realization
        ]
        if model.provenance
        else []
    )
    if len(candidates) != 1:
        raise ValueError("select exactly one captured realization")
    record = candidates[0]
    _, parameters, arrays = captured_inputs(model, record.plan)
    paths, _ = construct_paths(record.plan.method, parameters, arrays)
    if {o.name for o in record.outputs} != set(paths):
        raise ValueError("captured output inventory mismatch")
    for output in record.outputs:
        flow = model.value(output.value).flow
        if flow is None:
            raise ValueError("stored output is not a Flow")
        actual = cast(dict[str, Any], flow.to_data())
        for item in actual["movements"]:
            item.pop("claims", None)
        if actual != _flow(record.plan, paths[output.name]).to_data():
            raise ValueError(f"replay differs from stored path: {output.name}")
    return Market(model, record)
