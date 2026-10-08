"""Bounded Specification conformance checks; no evaluation, graph executor, or solver.

Run generated structural validation on both documents first. Assignment checks
accept exact canonical unit spellings, or an explicit unit-compatibility adapter.
Other spellings are reported as unsupported without such an adapter. This is not
expression unit inference or a shared unit registry. Query dependencies in imposed
mathematics require a graph adapter and are reported explicitly as unsupported.
"""

import math
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID
from rangekeeper.model.scope import Scope, reference_key, numerical_units
from rangekeeper.shared.validation import require, require_declarations, require_acyclic
from rangekeeper.model.expression.validation import ExpressionAnalysis
from rangekeeper.model.formulation.preparation import prepare_formulations
from rangekeeper.model.validation import check_model
from rangekeeper.specification.composition import (
    batch_cases,
    specification_catalogue,
    validate_roles,
)
from rangekeeper.schema.index import walk_data
from collections.abc import Callable, Mapping
from rangekeeper.schema.runtime import Record
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.validation import bounded, checked
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.specification.composition import compose_specification, Composition
from rangekeeper.shared.errors import (
    ContractError,
    MissingReferenceError,
    ReferenceTypeError,
    IdentityConflictError,
    UnitError,
)
from rangekeeper.shared.references import SpecificationResolver
from rangekeeper.shared.units import UnitSystem, default_units
from dataclasses import dataclass


if TYPE_CHECKING:
    from rangekeeper.model.model import Model


def validate_specification(
    specification,
    model,
    schema_version,
    model_schema_version,
    *,
    history=(),
    units_compatible=None,
    specifications=None,
    composition=None,
    validate_input=True,
):
    """Validate one concrete composition and roles without changing its inputs.

    The caller supplies structurally validated Model/Specification documents and
    an optional UUID-keyed Specification catalogue. Historical Metadata, if
    supplied, must come from Specification revisions. External resolution is absent.
    """
    composition = composition or compose_specification(
        specification, specifications, schema_version
    )
    effective = composition.requirements._data
    require("model" in effective, "concrete Specification requires an input Model")
    internal_ids = require_declarations(
        (
            ("Model", model),
            *(
                ("Specification", item.record._data)
                for item in composition.contributors
            ),
        )
    )
    # Contributor lineage is distinct from include edges. A predecessor may be
    # explicitly included, but cannot masquerade as a Model/domain declaration.
    domain_ids = {r["id"] for r, _ in walk_data("Model", model) if "id" in r}
    domain_ids.update(
        r["id"]
        for d in (item.record._data for item in composition.contributors)
        for root in d.get("formulations") or ()
        for r, _ in walk_data("Formulation", root)
        if "id" in r
    )
    for contributor in (item.record._data for item in composition.contributors):
        require(
            contributor["metadata"].get("previous") not in domain_ids,
            "Specification predecessor targets current scope",
        )
    internal_ids.difference_update(
        str(item.id)
        for item in composition.contributors
        if item.id != composition.root_id
    )
    try:
        return _validate_concrete(
            effective,
            model,
            schema_version,
            model_schema_version,
            history=history,
            units_compatible=units_compatible,
            validate_input=validate_input,
            internal_ids=internal_ids,
        )
    except ContractError as error:
        issue = _source_issue(
            Issue(
                error.code,
                str(error),
                error.document_id or composition.root_id,
                error.path,
            ),
            composition,
            UUID(model["metadata"]["id"]),
            formulation_prefix="/additional_formulations/",
        )
        raise ContractError(
            issue.message,
            code=issue.code,
            path=issue.path,
            document_id=issue.document_id,
        ) from error


def validate_batch(
    specification,
    models,
    schema_version,
    model_schema_version,
    *,
    specifications=None,
    units_compatible=None,
):
    """Validate every leaf independently; return case paths, not runs or results."""
    catalogue = specification_catalogue(specification, specifications, schema_version)
    paths, prepared, validated = [], {}, set()
    for path, leaf, assertions in batch_cases(
        specification, catalogue, schema_version, catalogue=catalogue
    ):
        identity = leaf["metadata"]["id"]
        if identity not in prepared:
            prepared[identity] = compose_specification(
                leaf, catalogue, schema_version, catalogue=catalogue
            )
        composition = prepared[identity]
        effective = composition.requirements._data
        require("model" in effective, "concrete Specification requires an input Model")
        model_id = effective["model"]
        require(
            all(ref == model_id for ref in assertions),
            "batch input Model assertion mismatch",
        )
        require(model_id in models, "unresolved input Model revision")
        require_declarations(
            (
                ("Model", models[model_id]),
                *(
                    ("Metadata", document["metadata"])
                    for document in catalogue.values()
                ),
                (
                    "Specification",
                    {"formulations": effective.get("formulations") or ()},
                ),
            )
        )
        if identity not in validated:
            validate_specification(
                leaf,
                models[model_id],
                schema_version,
                model_schema_version,
                specifications=catalogue,
                units_compatible=units_compatible,
                composition=composition,
            )
            validated.add(identity)
        paths.append(path)
    return paths


def _validate_concrete(
    specification,
    model,
    schema_version,
    model_schema_version,
    *,
    history=(),
    units_compatible=None,
    validate_input=True,
    internal_ids=None,
):
    require("model" not in model, "input document must be a Model, not a Specification")
    if validate_input:
        check_model(model, model_schema_version)
    metadata = specification["metadata"]
    require(
        metadata["schema_version"] == schema_version,
        "unsupported Specification schema version",
    )
    require(
        specification["model"] == model["metadata"]["id"],
        "input Model revision mismatch",
    )
    internal_ids = internal_ids or require_declarations(
        (("Model", model), ("Specification", specification))
    )
    previous = metadata.get("previous")
    require(previous != metadata["id"], "self predecessor")
    require(
        previous not in internal_ids, "Specification predecessor targets current scope"
    )
    revisions = {metadata["id"]: metadata}
    for record in history:
        require(record["id"] not in internal_ids, "history identity in current scope")
        require(record["id"] not in revisions, "duplicate history identity")
        revisions[record["id"]] = record
    require_acyclic(
        {
            key: [r["previous"]] if r.get("previous") else []
            for key, r in revisions.items()
        },
        "Specification revision history",
    )

    additions = specification.get("formulations") or []
    scope, analysis, located = prepare_formulations(
        model, additional_formulations=additions, path="/system"
    )

    def eligible(target):
        return numerical_units(target, scope.targets, scope.measures)

    def supplied(collection):
        for assignment in specification.get(collection) or []:
            target = assignment["target"]
            expected = eligible(target)
            quantity = assignment["quantity"]
            require(
                math.isfinite(quantity["magnitude"]), "non-finite supplied magnitude"
            )
            actual = quantity["units"]
            if actual != expected:
                require(
                    units_compatible is not None,
                    "unit compatibility requires a unit-aware adapter",
                )
            if units_compatible is not None:
                require(
                    units_compatible(actual, expected), "incompatible supplied units"
                )

    roles = validate_roles(specification)
    assigned, unknowns, controlled = (
        roles["assignments"],
        roles["unknowns"],
        roles["policy"],
    )
    supplied("assignments")
    references = specification.get("unknowns") or []
    for target in references:
        eligible(target)
    supplied("estimates")
    require(roles["estimates"] <= unknowns, "estimate target is not an unknown")
    if specification.get("policy"):
        from rangekeeper.specification.policy.validation import validate_policy

        validate_policy(
            specification["policy"], scope=scope, units_compatible=units_compatible
        )

    # Imposed predicates and every objective need role completeness. Unused
    # expressions (including reporting queries) need not be prepared for a solve.
    constraints = [
        constraint
        for formulation, _ in located
        for constraint in formulation.get("constraints") or ()
    ]
    by_id = analysis.nodes_by_id
    imposed = [by_id[UUID(c["predicate"])] for c in constraints]
    # Validate all criteria without ranking, selecting, or reordering candidates.
    for objective in specification.get("objectives") or []:
        ref = UUID(objective["expression"])
        require(ref in by_id, "unknown or non-Expression objective")
        require(
            analysis.domains_by_id[ref]["kind"]
            in ("number", "quantity", "measurement"),
            "objective must be scalar numerical",
        )
        imposed.append(by_id[ref])
    required = set()
    for expression in imposed:
        for node, _ in walk_data("Expression", expression):
            require(
                node.get("kind") != "query",
                "query dependency resolution requires a graph adapter",
            )
            if node.get("kind") == "reference":
                required.add(reference_key(node["target"]))
    require(
        required <= assigned | unknowns | controlled,
        "missing solve role for required Value",
    )

    from rangekeeper.specification.composition import validate_settings

    validate_settings(specification.get("settings") or {})
    return scope, analysis


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
            composition = compose_specification(data, spec_data, versions[0])
            effective = composition.requirements._data
            model = model_data.get(effective.get("model"))
            if model is None:
                raise ContractError("unresolved input Model revision")
            validate_specification(
                data,
                model,
                *versions,
                specifications=spec_data,
                units_compatible=units_compatible,
                composition=composition,
            )

    return bounded(issues, check, document=data)


@dataclass(frozen=True)
class PreparedValidation:
    report: ValidationReport
    composition: Composition
    model: "Model | None" = None
    scope: Scope | None = None
    analysis: ExpressionAnalysis | None = None


def _source_issue(
    issue: Issue,
    composition: Composition,
    model_id: UUID,
    *,
    formulation_prefix: str,
) -> Issue:
    """Translate an effective validation location to its original declaration."""
    if issue.path.startswith(formulation_prefix):
        _, _, position, *tail = issue.path.split("/")
        formulation = (composition.requirements.formulations or ())[int(position)]
        source = composition.sources[("formulations", str(formulation.id))]
        return Issue(
            issue.code,
            issue.message,
            source.document_id,
            source.path + ("/" + "/".join(tail) if tail else ""),
        )
    if issue.path.startswith("/system/"):
        return Issue(issue.code, issue.message, model_id, issue.path)
    return issue


def prepare(
    composition: Composition,
    *,
    resolver: SpecificationResolver,
    units: UnitSystem = default_units,
) -> PreparedValidation:
    """Check one composition without recomposing; retain successful prerequisites."""
    from rangekeeper.model.model import Model
    from rangekeeper.schema.records import Measure
    from rangekeeper.model.validation import recorded_unit_issues

    if not isinstance(composition, Composition):
        raise TypeError("composition must be a Composition")
    if composition.model_id is None:
        return PreparedValidation(
            ValidationReport(
                (
                    Issue(
                        "semantic.model",
                        "composition has no input Model",
                        composition.root_id,
                    ),
                )
            ),
            composition,
        )
    model: Model | None = None
    scope: Scope | None = None
    analysis: ExpressionAnalysis | None = None
    try:
        model = resolver.load_model(composition.model_id)
        if not isinstance(model, Model):
            raise ReferenceTypeError("resolver did not return a Model")
        if model.id != composition.model_id:
            raise IdentityConflictError("resolver returned a different Model revision")
        effective = cast(Mapping[str, Any], composition.requirements._data)
        resolved_model = model
        issues: list[Issue] = []
        if model._units != units:
            issues.extend(
                recorded_unit_issues(
                    model._record,
                    measure=lambda identity: resolved_model._index.get(
                        identity, Measure
                    ),
                    units=units,
                    document_id=model.id,
                )
            )

        def check():
            nonlocal scope, analysis
            scope, analysis = validate_specification(
                effective,
                resolved_model._record._data,
                document_version("Specification"),
                document_version("Model"),
                composition=composition,
                validate_input=False,
                units_compatible=units.compatible,
            )

        report = bounded(issues, check, document=effective)
        if report.valid:
            report = ValidationReport(
                tuple(
                    _source_issue(
                        issue,
                        composition,
                        model.id,
                        formulation_prefix="/formulations/",
                    )
                    for issue in recorded_unit_issues(
                        composition.requirements,
                        measure=lambda identity: resolved_model._index.get(
                            identity, Measure
                        ),
                        units=units,
                        document_id=composition.root_id,
                    )
                )
            )
        return PreparedValidation(
            report,
            composition,
            model,
            scope if report.valid else None,
            analysis if report.valid else None,
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
        code = next(value for kind, value in codes.items() if isinstance(error, kind))
        return PreparedValidation(
            ValidationReport((Issue(code, str(error), composition.root_id),)),
            composition,
            model,
        )
