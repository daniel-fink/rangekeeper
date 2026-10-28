"""Stages 2 and 3: validate a composition, then bind its roles; no solver import."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from rangekeeper.execution.errors import UnsupportedError
from rangekeeper.flow import Movement
from rangekeeper.model import Model
from rangekeeper.model.targets import target_units
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import (
    Assignment,
    Constraint,
    Expression,
    Reference,
    RuleEvidence,
    Value,
)
from rangekeeper.shared.diagnostics import ValidationReport
from rangekeeper.shared.references import SpecificationResolver
from rangekeeper.specification import Composition
from rangekeeper.specification.validation import prepare as validate_prepared


@dataclass(frozen=True)
class Assertion:
    """One imposed predicate and the revision owning its Constraint declaration."""

    document: UUID
    constraint: Constraint
    predicate: Expression


@dataclass(frozen=True)
class Validation:
    """The validation of one composition against its input Model.

    ``model`` and ``units`` are set when the input Model resolved. ``units`` is
    the unit system that the later stages use.
    """

    report: ValidationReport
    composition: Composition
    model: Model | None = None
    units: UnitSystem | None = None
    # The scope of a valid Specification check, which Run validation reuses.
    scope: object = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class Binding:
    """The bound roles of one composition; derived, never serialized."""

    model: Model
    composition: Composition
    value_units: Mapping[UUID, str]
    assignments: Mapping[UUID, Quantity]
    unknowns: tuple[UUID, ...]
    assertions: tuple[Assertion, ...]
    units: UnitSystem
    references: Mapping[UUID, Reference]
    rule_evidence: tuple[RuleEvidence, ...] = ()


def validate(
    composition: Composition,
    *,
    resolver: SpecificationResolver,
    units: UnitSystem | None = None,
) -> Validation:
    """Validate a composition against its input Model once; raise nothing.

    Without ``units``, validation uses the unit system of the input Model. A
    content problem is an issue in ``report``.
    """
    validated = validate_prepared(composition, resolver=resolver, units=units)
    model = validated.model
    return Validation(
        validated.report,
        composition,
        model,
        None if model is None else model.unit_system if units is None else units,
        validated.scope,
    )


def bind_roles(
    validation: Validation,
    *,
    checkpoint: Callable[[], None] = lambda: None,
) -> Binding:
    """Give each value its role and normalize assignments to Measure units.

    Raise ValidationError for an invalid ``validation``. Only imposed
    mathematics is bound. Unused reporting queries stay passive. Recorded
    quantities and estimates never supply missing fixed roles. This slice
    publishes Model-owned scalar Values; local Specification Values and ordered
    optimization objectives raise UnsupportedError before any backend runs.
    """
    validation.report.raise_if_invalid()
    checkpoint()
    composition = validation.composition
    model, units = validation.model, validation.units
    assert model is not None and units is not None
    requirements = composition.requirements
    if requirements.objectives:
        raise UnsupportedError(
            "ordered optimization objectives are not supported by scalar feasibility execution"
        )
    expressions = {
        identity: record
        for identity, record in model._index.records.items()
        if isinstance(record, Expression)
    }
    declarations = [
        (model.id, record)
        for record in model._index.records.values()
        if isinstance(record, Constraint)
    ]
    model_values = {
        identity
        for identity, record in model._index.records.items()
        if isinstance(record, (Value, Movement))
    }
    for contributor in composition.contributors:
        for formulation in contributor.record.formulations or ():
            for record, _, _ in walk(formulation):
                checkpoint()
                if isinstance(record, Expression):
                    expressions[record.id] = record
                elif isinstance(record, Constraint):
                    declarations.append((contributor.id, record))
    role_references = list(requirements.unknowns or ()) + [
        a.target for a in requirements.assignments or ()
    ]
    rule_evidence: tuple[RuleEvidence, ...] = ()
    rule_assignments: tuple[Assignment, ...] = ()
    if requirements.rules is not None:
        unknown_tokens = {ref.target for ref in requirements.unknowns or ()}
        if any(
            binding.target.target in unknown_tokens
            for point in requirements.rules.decisions
            for binding in point.observations
        ):
            raise UnsupportedError(
                "rule observation targets an endogenous unknown; sequential numerical rules are unsupported"
            )
        from rangekeeper.execution.rule.evaluation import evaluate
        from rangekeeper.execution.rule.observation import RuleCapabilityError

        try:
            rule_result = evaluate(requirements.rules, model=model, units=units)
            checkpoint()
        except RuleCapabilityError as error:
            raise UnsupportedError(str(error)) from error
        rule_evidence = rule_result.evidence
        rule_assignments = rule_result.assignments
        role_references.extend(a.target for a in rule_assignments)
    if any(ref.target not in model_values for ref in role_references):
        raise UnsupportedError(
            "Specification-local Value publication requires a later adapter"
        )
    references = {ref.target: ref for ref in role_references}
    value_units = {token: target_units(model, ref) for token, ref in references.items()}
    assignments = {
        item.target.target: units.convert(
            item.quantity, to=value_units[item.target.target]
        )
        for item in (*(requirements.assignments or ()), *rule_assignments)
    }
    return Binding(
        model,
        composition,
        MappingProxyType(value_units),
        MappingProxyType(assignments),
        tuple(ref.target for ref in requirements.unknowns or ()),
        tuple(
            Assertion(document, declaration, expressions[declaration.predicate])
            for document, declaration in declarations
        ),
        units,
        MappingProxyType(references),
        rule_evidence,
    )
