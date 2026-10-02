"""Structural and bounded Model semantics; no evaluation or unit inference."""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from .._records import Record
from .._schema.validation import document_version
from .._validation import bounded, checked
from ..diagnostics import Issue, ValidationReport
from ._validation import validate_model
from .._schema.records import Model as ModelRecord, Measure
from ..units import UnitSystem, default_units
from ._index import Index
from ._unit_validation import recorded_unit_issues

if TYPE_CHECKING:
    from .model import Model


def validate(
    model: "Model | Record | Mapping[str, object]",
    *,
    history: Sequence[Mapping[str, object]] = (),
    units: UnitSystem = default_units,
) -> ValidationReport:
    """Check current references/ownership and supported recorded units without solving.

    History is optional Metadata context. Unit checks parse declared units and match
    recorded Value quantities to their Measures; they do not infer equation units
    or inspect arbitrary Claim content. Input/export data is never mutated.
    """
    from .model import Model

    if isinstance(model, Model):
        model = model.to_data()
    issues: list[Issue] = []
    data = checked("Model", model, "", issues)
    prior = [
        checked("Metadata", value, f"/history/{index}", issues)
        for index, value in enumerate(history)
    ]
    report = bounded(
        issues,
        lambda: validate_model(data, document_version("Model"), prior),
        document=data,
    )
    if not report.valid:
        return report
    record = ModelRecord.from_data(data)
    index = Index.build(record)
    return ValidationReport(
        recorded_unit_issues(
            record,
            measure=lambda id: index.get(id, Measure),
            units=units,
            document_id=record.metadata.id,
        )
    )
