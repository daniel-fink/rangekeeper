"""Complete investigation validation, separate from partial saved contributions.

``validate`` consumes a Composition and a narrow resolver. ``validate_records`` is
the low-level catalogue entrypoint retained for conformance and synthetic Run checks.
Neither performs equation solving or certifies numerical feasibility.
"""

from collections.abc import Callable, Mapping

from .._records import Record
from .._schema.validation import document_version
from .._validation import bounded, checked
from ..diagnostics import Issue, ValidationReport
from ._composition import compose_specification
from ._validation import validate_batch, validate_specification
from ..errors import ContractError
from ..errors import (
    MissingReferenceError,
    ReferenceTypeError,
    IdentityConflictError,
    UnitError,
)
from ..references import SpecificationResolver
from ..units import UnitSystem, default_units
from .composition import Composition


def validate_records(
    specification: Record | Mapping[str, object],
    *,
    models: Mapping[str, Record | Mapping[str, object]],
    specifications: Mapping[str, Record | Mapping[str, object]] | None = None,
    units_compatible: Callable[[str, str], bool] | None = None,
) -> ValidationReport:
    """Check all concrete leaves and their pinned Models, retaining batch boundaries."""
    issues: list[Issue] = []
    data = checked("Specification", specification, "", issues)
    model_data = {
        key: checked("Model", value, f"/models/{key}", issues)
        for key, value in models.items()
    }
    spec_data = {
        key: checked("Specification", value, f"/specifications/{key}", issues)
        for key, value in (specifications or {}).items()
    }
    for catalogue in (model_data, spec_data):
        for key, value in catalogue.items():
            if value and value["metadata"]["id"] != key:
                issues.append(
                    Issue(
                        "semantic.identity",
                        "catalogue key differs from revision identity",
                    )
                )

    def check():
        versions = document_version("Specification"), document_version("Model")
        if data.get("cases"):
            validate_batch(
                data,
                model_data,
                *versions,
                specifications=spec_data,
                units_compatible=units_compatible,
            )
        else:
            effective = compose_specification(data, spec_data, versions[0]).effective
            model = model_data.get(effective.get("model"))
            if model is None:
                raise ContractError("unresolved input Model revision")
            validate_specification(
                data,
                model,
                *versions,
                specifications=spec_data,
                units_compatible=units_compatible,
            )

    return bounded(issues, check, document=data)


def validate(
    composition: Composition,
    *,
    resolver: SpecificationResolver,
    units: UnitSystem = default_units,
) -> ValidationReport:
    """Validate complete roles, ownership and units against an exact pinned Model.

    Composition contributors are the immutable snapshots resolved during compose;
    this call resolves only their pinned Model. Resolution failures become diagnostic
    reports. Partial contributions remain valid saved records even when this complete
    investigation check reports missing input/roles. No IO occurs except the explicitly
    supplied resolver call.
    """
    if not isinstance(composition, Composition):
        raise TypeError(
            "composition must be a Composition; use validate_records for raw catalogues"
        )
    from ..model.model import Model
    from ..model.definitions import measure
    from ..model._unit_validation import recorded_unit_issues
    from ..diagnostics import ValidationReport

    if composition.model_id is None:
        return ValidationReport(
            (
                Issue(
                    "semantic.model",
                    "composition has no input Model",
                    composition.root_id,
                ),
            )
        )
    try:
        model = resolver.load_model(composition.model_id)
        if not isinstance(model, Model):
            raise ReferenceTypeError("resolver did not return a Model")
        if model.id != composition.model_id:
            raise IdentityConflictError("resolver returned a different Model revision")
        documents = {str(doc.id): doc.to_data() for doc in composition.contributions}
        report = validate_records(
            documents[str(composition.root_id)],
            models={str(model.id): model.to_data()},
            specifications=documents,
            units_compatible=units.compatible,
        )
        if not report.valid:
            return report
        return ValidationReport(
            recorded_unit_issues(
                composition.requirements,
                measure=lambda id: measure(model.definitions, id),
                units=units,
                document_id=composition.root_id,
            )
        )
    except (
        MissingReferenceError,
        ReferenceTypeError,
        IdentityConflictError,
        UnitError,
    ) as error:
        codes = {
            MissingReferenceError: "reference.missing",
            ReferenceTypeError: "reference.kind",
            IdentityConflictError: "reference.identity",
            UnitError: "semantic.units",
        }
        code = next(code for kind, code in codes.items() if isinstance(error, kind))
        return ValidationReport((Issue(code, str(error), composition.root_id),))
