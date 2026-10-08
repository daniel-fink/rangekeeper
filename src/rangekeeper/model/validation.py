"""Structural and bounded Model semantics; no evaluation or unit inference."""

from collections.abc import Mapping, Sequence, Callable
from typing import TYPE_CHECKING
from rangekeeper.schema.runtime import Record
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.validation import (
    bounded,
    checked,
    checked_record,
    require,
    require_acyclic,
    require_declarations,
)
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.schema.records import (
    Model as ModelRecord,
    Measure,
    Domain,
    Quantity,
    Value,
    Flow,
)
from rangekeeper.shared.units import UnitSystem, default_units
from rangekeeper.schema.index import RecordIndex, walk, walk_data
from uuid import UUID
from rangekeeper.shared.errors import UnitError
from rangekeeper.model.definitions import check_definitions
from rangekeeper.model.system.validation import check_system
from rangekeeper.model.provenance import check_provenance
from rangekeeper.model.formulation.preparation import prepare_formulations


if TYPE_CHECKING:
    from rangekeeper.model.model import Model


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
    from rangekeeper.model.model import Model

    if isinstance(model, Model):
        return _validate(
            model._record, index=model._index, history=history, units=units
        )
    if isinstance(model, ModelRecord):
        return _validate(model, history=history, units=units)
    issues: list[Issue] = []
    record = checked_record("Model", model, "", issues)
    return _validate(record, history=history, units=units, initial_issues=issues)


def _validate(
    record: ModelRecord | None,
    *,
    index: RecordIndex | None = None,
    initial_issues: list[Issue] | None = None,
    history: Sequence[Mapping[str, object]] = (),
    units: UnitSystem = default_units,
) -> ValidationReport:
    """Check a structurally valid record, reusing the facade's ownership index.

    Only generated records enter this path. Raw mappings first pass the public
    structural check. No index or validation result is cached across revisions.
    """
    issues = list(initial_issues or ())
    prior = [
        checked("Metadata", value, f"/history/{position}", issues)
        for position, value in enumerate(history)
    ]
    if issues:
        return ValidationReport(tuple(issues))
    assert record is not None
    data = record.to_data()
    report = bounded(
        issues,
        lambda: check_model(data, document_version("Model"), prior, index=index),
        document=data,
    )
    if not report.valid:
        return report
    if index is None:
        index = RecordIndex.build(record)
    return ValidationReport(
        recorded_unit_issues(
            record,
            measure=lambda id: index.get(id, Measure),
            units=units,
            document_id=record.metadata.id,
        )
    )


def recorded_unit_issues(
    root: Record,
    *,
    measure: Callable[[UUID], Measure],
    units: UnitSystem,
    document_id: UUID,
) -> tuple[Issue, ...]:
    """Report unknown units and recorded Value/Measure dimension mismatches.

    Reference/ownership validation must run first. Thus a missing Measure is a
    programming/validation-order error, rather than a swallowed unit failure.
    Opaque Claim content never enters this traversal.
    """
    issues = []
    for item, _, path in walk(root):
        issue_path = path
        try:
            if (
                isinstance(item, (Domain, Measure, Quantity, Flow))
                and item.units is not None
            ):
                issue_path = path + "/units"
                units.validate_units(item.units)
            if isinstance(item, Value) and item.quantity is not None:
                issue_path = path + "/quantity/units"
                assert item.measure is not None
                expected = measure(item.measure)
                if not units.compatible(item.quantity.units, expected.units):
                    raise UnitError(
                        "recorded Value quantity is incompatible with its Measure"
                    )
            if isinstance(item, Value) and item.flow is not None:
                issue_path = path + "/flow/units"
                assert item.measure is not None
                if not units.compatible(item.flow.units, measure(item.measure).units):
                    raise UnitError("recorded Flow is incompatible with its Measure")
        except UnitError as error:
            issues.append(Issue("semantic.units", str(error), document_id, issue_path))
    return tuple(issues)


def check_model(model, schema_version, history=(), *, index=None):
    """Check Model domains and optional revision history without reconstruction."""
    metadata = model["metadata"]
    require(metadata["schema_version"] == schema_version, "unsupported schema version")
    if index is None:
        internal_ids = require_declarations((("Model", model),))
        locations = {
            record["id"]: path
            for record, path in walk_data("Model", model)
            if "id" in record
        }
    else:
        internal_ids = {str(identity) for identity in index.records}
        locations = {str(identity): path for identity, path in index.paths.items()}
    check_definitions(model.get("definitions") or {})
    scope, _, _ = prepare_formulations(model, path="/system")
    targets = check_system(model.get("system") or {}, scope=scope, locations=locations)
    check_provenance(
        model.get("provenance") or {}, scope=scope, targets=targets, paths=locations
    )
    previous = metadata.get("previous")
    require(previous != metadata["id"], "self predecessor")
    require(previous not in internal_ids, "previous targets current snapshot content")
    revisions = {metadata["id"]: metadata}
    for record in history:
        require(record["id"] not in revisions, "duplicate history identity")
        require(record["id"] not in internal_ids, "history identity in current scope")
        revisions[record["id"]] = record
    require_acyclic(
        {
            key: [record["previous"]] if record.get("previous") else []
            for key, record in revisions.items()
        },
        "revision history",
    )
    return scope
