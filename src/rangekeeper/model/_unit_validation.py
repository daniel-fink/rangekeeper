"""Recorded-unit checks shared by Model and composed Specification validation.

The measure resolver is deliberately narrow. This module neither owns a catalogue
nor infers expression result units; it inspects only schema-declared typed records.
"""

from collections.abc import Callable
from uuid import UUID

from .._records import Record
from .._schema.records import Domain, Measure, Quantity, Value
from ..diagnostics import Issue
from ..errors import UnitError
from ..units import UnitSystem
from ._index import walk


def recorded_unit_issues(
    root: Record,
    *,
    measure: Callable[[UUID], Measure],
    units: UnitSystem,
    document_id: UUID
) -> tuple[Issue, ...]:
    """Report unknown units and recorded Value/Measure dimension mismatches.

    Reference/ownership validation must run first. Thus a missing Measure is a
    programming/validation-order error, rather than a swallowed unit failure.
    Opaque Claim content never enters this traversal.
    """
    issues = []
    for item, _, path in walk(root):
        try:
            if isinstance(item, (Domain, Measure, Quantity)) and item.units is not None:
                units.compatible(item.units, item.units)
            if isinstance(item, Value) and item.quantity is not None:
                assert item.measure is not None
                expected = measure(item.measure)
                if not units.compatible(item.quantity.units, expected.units):
                    raise UnitError(
                        "recorded Value quantity is incompatible with its Measure"
                    )
            if isinstance(item, Value) and item.flow is not None:
                assert item.measure is not None
                if not units.compatible(item.flow.units, measure(item.measure).units):
                    raise UnitError("recorded Flow is incompatible with its Measure")
        except UnitError as error:
            issues.append(Issue("semantic.units", str(error), document_id, path))
    return tuple(issues)
