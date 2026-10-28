"""Structural and bounded Model semantics; no evaluation or unit inference."""

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.flow import Flow
from rangekeeper.model.definitions import check_definitions
from rangekeeper.model.formulation.preparation import prepare_formulations
from rangekeeper.model.provenance import check_provenance
from rangekeeper.model.system.validation import check_system
from rangekeeper.quantity import UnitSystem, default_units
from rangekeeper.schema.index import RecordIndex, walk, walk_data
from rangekeeper.schema.records import (
    Domain,
    Measure,
    Quantity,
    Value,
)
from rangekeeper.schema.records import (
    Model as ModelRecord,
)
from rangekeeper.schema.runtime import Record
from rangekeeper.schema.validation import (
    checked,
    checked_record,
    document_version,
    require_declarations,
    supports_version,
)
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import UnitError
from rangekeeper.shared.validation import bounded, require, require_acyclic

if TYPE_CHECKING:
    from rangekeeper.model.model import Model
    from rangekeeper.shared.references import SpecificationResolver


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


def validate_document(
    model: "Model",
    *,
    resolver: "SpecificationResolver | None" = None,
    units: UnitSystem | None = None,
) -> ValidationReport:
    """Report the semantic problems of one Model revision; raise none for them.

    The check uses ``units``, or the unit system of the revision. A Model
    references no other document, so ``resolver`` reads nothing. Lineage is
    optional context: a store need not hold the predecessor.
    """
    return _validate(
        model._record, index=model._index, units=units or model.unit_system
    )


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
    data = (
        record._data
        if type(record) is ModelRecord and "geometry" not in record._data
        else record.to_data()
    )
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
        fields: dict[str, object] = {}
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
                    fields = {
                        "units": item.quantity.units,
                        "expected": expected.units,
                    }
                    raise UnitError(
                        f"recorded quantity of Value {_named(item)} is incompatible "
                        f"with its Measure: {item.quantity.units} is not "
                        f"{expected.units}"
                    )
            if isinstance(item, Value) and item.flow is not None:
                issue_path = path + "/flow/units"
                assert item.measure is not None
                expected = measure(item.measure)
                if not units.compatible(item.flow.units, expected.units):
                    fields = {"units": item.flow.units, "expected": expected.units}
                    raise UnitError(
                        f"recorded Flow of Value {_named(item)} is incompatible "
                        f"with its Measure: {item.flow.units} is not "
                        f"{expected.units}"
                    )
        except UnitError as error:
            if error.suggestions:
                fields["suggestions"] = error.suggestions
            issues.append(
                Issue(
                    Code.UNITS,
                    str(error),
                    document_id,
                    issue_path,
                    (item.id,) if isinstance(item, Value) else (),
                    fields,
                )
            )
    return tuple(issues)


def check_model(model, schema_version, history=(), *, index=None):
    """Check Model domains and optional revision history without reconstruction."""
    metadata = model["metadata"]
    require(
        supports_version(metadata["schema_version"], schema_version),
        "unsupported schema version",
    )
    from rangekeeper.model.geometry import check_geometry

    check_geometry(model)
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


def _named(value) -> str:
    """Name a Value by its key and UUID."""
    return f"{value.key} ({value.id})" if value.key else str(value.id)
