"""Bounded Specification conformance checks; no evaluation, graph executor, or solver.

Run generated structural validation on both documents first. Assignment checks
accept exact canonical unit spellings, or an explicit unit-compatibility adapter.
Other spellings are reported as unsupported without such an adapter. This is not
expression unit inference or a shared unit registry. Query dependencies in imposed
mathematics require a graph adapter and are reported explicitly as unsupported.
"""

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from rangekeeper.model._scope import (
    Scope,
    date_reference,
    numerical_units,
    reference_key,
)
from rangekeeper.model.expression.validation import ExpressionAnalysis
from rangekeeper.model.formulation.preparation import prepare_formulations
from rangekeeper.model.validation import check_model
from rangekeeper.quantity import UnitSystem
from rangekeeper.schema.index import walk_data
from rangekeeper.schema.runtime import Record
from rangekeeper.schema.validation import (
    checked,
    document_version,
    require_declarations,
    supports_version,
)
from rangekeeper.shared.amounts import number
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import (
    ContractError,
    IdentityConflictError,
    MissingReferenceError,
    RangekeeperError,
    ReferenceTypeError,
    UnitError,
    ValidationError,
)
from rangekeeper.shared.references import SpecificationResolver
from rangekeeper.shared.validation import bounded, require, require_acyclic
from rangekeeper.specification.composition import (
    Composition,
    batch_cases,
    check_roles,
    collect_specifications,
    compose,
    compose_specification,
    specification_catalogue,
)

if TYPE_CHECKING:
    from rangekeeper.model.model import Model
    from rangekeeper.specification.specification import Specification


def validate_document(
    specification: "Specification",
    *,
    resolver: SpecificationResolver | None = None,
    units: UnitSystem | None = None,
) -> ValidationReport:
    """Report the problems of one Specification; raise none for content problems.

    Without ``resolver``, repeat the local rules. With it, resolve the case graph
    once, then compose and validate each concrete case once. A batch also checks
    that each case uses the input Model that the batch pins.
    """
    from rangekeeper.specification.specification import _validate_local

    report = _validate_local(specification.record)
    if resolver is None or not report.valid:
        return report
    try:
        documents, catalogue = collect_specifications(specification, resolver=resolver)
    except ValidationError as error:
        return error.report
    except RangekeeperError as error:
        return ValidationReport((Issue(error.code, str(error), specification.id),))
    issues: list[Issue] = []
    compositions: dict[UUID, Composition | None] = {}

    def visit(current: "Specification", pins: tuple[UUID, ...]) -> None:
        if current.record.cases:
            if current.record.model is not None:
                pins += (current.record.model,)
            for identity in current.record.cases:
                visit(documents[identity], pins)
            return
        if current.id not in compositions:
            try:
                composition = compose(
                    current, resolver=resolver, documents=documents, catalogue=catalogue
                )
            except ValidationError as error:
                compositions[current.id] = None
                issues.extend(error.report.issues)
            else:
                compositions[current.id] = composition
                issues.extend(
                    composition.validate(resolver=resolver, units=units).issues
                )
        resolved = compositions[current.id]
        if resolved is None or resolved.model_id is None:
            return
        for pin in pins:
            if pin != resolved.model_id:
                issues.append(
                    Issue(
                        Code.BATCH_MODEL,
                        f"case {current.id} uses Model {resolved.model_id}, "
                        f"but its batch pins Model {pin}",
                        current.id,
                        targets=(resolved.model_id, pin),
                        values={
                            "case": str(current.id),
                            "model": str(resolved.model_id),
                            "pinned": str(pin),
                        },
                    )
                )

    visit(specification, ())
    return ValidationReport(tuple(issues))


def check_specification(
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
    """Check one concrete composition and roles without changing its inputs.

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
        return _check_concrete(
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
            Issue.from_error(error, document_id=composition.root_id),
            composition,
            UUID(model["metadata"]["id"]),
            formulation_prefix="/additional_formulations/",
        )
        raise ContractError.from_issue(issue) from error


def check_batch(
    specification,
    models,
    schema_version,
    model_schema_version,
    *,
    specifications=None,
    units_compatible=None,
):
    """Check every leaf independently; return case paths, not runs or results."""
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
            check_specification(
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


def _check_concrete(
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
        supports_version(metadata["schema_version"], schema_version),
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
            if date_reference(target, scope.targets):
                # A date Value takes a date or NEVER (#280).
                require(
                    "quantity" not in assignment,
                    "a date Value takes a date or NEVER",
                )
                continue
            require(
                "quantity" in assignment,
                "a date or NEVER supplies a date Value only",
            )
            expected = eligible(target)
            quantity = assignment["quantity"]
            require(
                math.isfinite(number(quantity["magnitude"])),
                "non-finite supplied magnitude",
            )
            actual = quantity["units"]
            if actual != expected:
                require(
                    units_compatible is not None,
                    "unit compatibility requires a unit-aware adapter",
                )
            if units_compatible is not None:
                key = _key(scope, UUID(target["target"]))
                require(
                    units_compatible(actual, expected),
                    f"incompatible units: {key or target['target']} has units "
                    f"{expected}, and the quantity that fixes it {actual}",
                    code=Code.INCOMPATIBLE_UNITS,
                    values={"key": key, "units": actual, "expected": expected},
                )

    roles = check_roles(specification)
    assigned, unknowns, controlled = (
        roles["assignments"],
        roles["unknowns"],
        roles["rules"],
    )
    supplied("assignments")
    references = specification.get("unknowns") or []
    for target in references:
        if not date_reference(target, scope.targets):
            eligible(target)
    supplied("estimates")
    require(roles["estimates"] <= unknowns, "estimate target is not an unknown")
    if specification.get("rules"):
        from rangekeeper.specification.rule.validation import validate_rules

        validate_rules(
            specification["rules"], scope=scope, units_compatible=units_compatible
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
                required.update(_role_targets(scope, reference_key(node["target"])))
    missing = sorted(required - (assigned | unknowns | controlled), key=str)
    require(
        not missing,
        "missing solve role for required Value "
        + ", ".join(_named(scope, identity) for identity in missing),
        code=Code.ROLE_MISSING,
        targets=missing,
        values={"keys": tuple(_key(scope, identity) for identity in missing)},
    )

    from rangekeeper.specification.composition import check_settings

    check_settings(specification.get("settings") or {})
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
                        Code.IDENTITY,
                        "catalogue key differs from revision identity",
                    )
                )

    def check():
        versions = document_version("Specification"), document_version("Model")
        if data.get("cases"):
            check_batch(
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
            check_specification(
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
    """Validation report of one composition, with its successful prerequisites."""

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
        return issue.replace(
            document_id=source.document_id,
            path=source.path + ("/" + "/".join(tail) if tail else ""),
        )
    if issue.path.startswith("/system/"):
        return issue.replace(document_id=model_id)
    return issue


def prepare(
    composition: Composition,
    *,
    resolver: SpecificationResolver,
    units: UnitSystem | None = None,
) -> PreparedValidation:
    """Check one composition without recomposing; retain successful prerequisites.

    Without ``units``, the check uses the unit system of the input Model.
    """
    from rangekeeper.model.model import Model
    from rangekeeper.model.validation import recorded_unit_issues
    from rangekeeper.schema.records import Measure

    if not isinstance(composition, Composition):
        raise TypeError("composition must be a Composition")
    if composition.model_id is None:
        return PreparedValidation(
            ValidationReport(
                (
                    Issue(
                        Code.MODEL_MISSING,
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
        if units is None:
            units = model.unit_system
        elif model.unit_system != units:
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
            scope, analysis = check_specification(
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
        return PreparedValidation(
            ValidationReport((Issue(error.code, str(error), composition.root_id),)),
            composition,
            model,
        )


def _role_targets(scope: Scope, identity: UUID) -> tuple[UUID, ...]:
    """Return the targets that need a role for a reference: a Flow's Movements.

    A reference to a whole Flow Value, in a Flow-valued equation (#279), needs a
    role for each of its Movements; another reference needs its own.
    """
    value, movement = scope.targets.get(identity, ({}, None))
    movements = (value.get("flow") or {}).get("movements") or []
    if movement is None and value.get("kind") == "flow" and movements:
        return tuple(UUID(item["id"]) for item in movements)
    return (identity,)


def _key(scope: Scope, identity: UUID) -> str | None:
    """Return the key of a Value or Movement target, if it has one."""
    value, movement = scope.targets.get(identity, ({}, None))
    return (movement or value).get("key")


def _named(scope: Scope, identity: UUID) -> str:
    """Name a target by its key and UUID."""
    key = _key(scope, identity)
    return f"{key} ({identity})" if key else str(identity)
