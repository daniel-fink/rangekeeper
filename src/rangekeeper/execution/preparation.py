"""Stages 2 and 3: validate a composition, then bind its roles; no solver import."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from rangekeeper.duration.dates import NEVER, DateValue
from rangekeeper.execution.errors import UnsupportedError
from rangekeeper.flow import Movement
from rangekeeper.model import Model
from rangekeeper.model.expression.text import render
from rangekeeper.model.targets import date_target, target_units
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
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.shared.diagnostics import ValidationReport
from rangekeeper.shared.references import SpecificationResolver
from rangekeeper.specification import Composition
from rangekeeper.specification.validation import prepare as validate_prepared


@dataclass(frozen=True, kw_only=True)
class Assertion:
    """One imposed predicate and the revision owning its Constraint declaration.

    ``irr_flow`` is the Flow of an equation that fixes an IRR, when ``predicate``
    is the NPV row of that equation (``execution.expansion``).
    """

    document: UUID
    constraint: Constraint
    predicate: Expression
    irr_flow: Expression | None = None


@dataclass(frozen=True, kw_only=True)
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
    _scope: object = field(default=None, init=False, repr=False, compare=False)


@dataclass(frozen=True, kw_only=True)
class Binding:
    """The bound roles of one composition; derived, never serialized.

    ``assignments`` and ``unknowns`` are the numerical roles, in Measure units.
    ``dates`` are the fixed date Values, each a date or NEVER, and
    ``date_unknowns`` the free ones; the date equations determine them before
    the affine stages (#280).
    """

    model: Model
    composition: Composition
    value_units: Mapping[UUID, str]
    assignments: Mapping[UUID, Quantity]
    unknowns: tuple[UUID, ...]
    assertions: tuple[Assertion, ...]
    units: UnitSystem
    references: Mapping[UUID, Reference]
    rule_evidence: tuple[RuleEvidence, ...] = ()
    dates: Mapping[UUID, DateValue] = field(
        default_factory=lambda: MappingProxyType({})
    )
    date_unknowns: tuple[UUID, ...] = ()

    def key(self, reference: Reference) -> str:
        """Return the key of a referenced Value or Movement, or else its UUID.

        The key is the one that ``Model.key_of`` gives: unique in the Model.
        A Specification Value that the Model does not declare gives its UUID.
        """
        try:
            return self.model.key_of(reference.target)
        except (LookupError, TypeError):
            return str(reference.target)

    def text(self, expression: Expression) -> str:
        """Return the text of ``expression``, with each reference named by its key."""
        return render(expression=expression, name=self.key)


def validate(
    *,
    composition: Composition,
    resolver: SpecificationResolver,
    units: UnitSystem | None = None,
) -> Validation:
    """Validate a composition against its input Model once; raise nothing.

    Without ``units``, validation uses the unit system of the input Model. A
    content problem is an issue in ``report``.
    """
    validated = validate_prepared(composition, resolver=resolver, units=units)
    model = validated.model
    validation = Validation(
        report=validated.report,
        composition=composition,
        model=model,
        units=(
            None if model is None else model.unit_system if units is None else units
        ),
    )
    object.__setattr__(validation, "_scope", validated.scope)
    return validation


def bind_roles(
    *,
    validation: Validation,
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
    _refuse_declared_rules(requirements)
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
            rule_result = evaluate(rules=requirements.rules, model=model, units=units)
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
    dated = {token for token, ref in references.items() if date_target(model, ref)}
    value_units = {
        token: target_units(model, ref)
        for token, ref in references.items()
        if token not in dated
    }
    supplied = (*(requirements.assignments or ()), *rule_assignments)
    assignments = {
        item.target.target: units.convert(
            quantity=item.quantity, to=value_units[item.target.target]
        )
        for item in supplied
        if item.quantity is not None
    }
    dates: dict[UUID, DateValue] = {}
    for item in supplied:
        found = _supplied_date(item)
        if found is not None:
            dates[item.target.target] = found
    free = tuple(ref.target for ref in requirements.unknowns or ())
    return Binding(
        model=model,
        composition=composition,
        value_units=MappingProxyType(value_units),
        assignments=MappingProxyType(assignments),
        unknowns=tuple(id for id in free if id not in dated),
        assertions=tuple(
            Assertion(
                document=document,
                constraint=declaration,
                predicate=expressions[declaration.predicate],
            )
            for document, declaration in declarations
        ),
        units=units,
        references=MappingProxyType(references),
        rule_evidence=rule_evidence,
        dates=MappingProxyType(dates),
        date_unknowns=tuple(id for id in free if id in dated),
    )


def _refuse_declared_rules(requirements: SpecificationRecord) -> None:
    """Raise UnsupportedError for rules: the solve does not run them yet (#300)."""
    if requirements.declared_rules:
        raise UnsupportedError(
            "rk.execution.solve does not run a Specification's rules yet (#300)"
        )


def _supplied_date(item: Assignment) -> DateValue | None:
    """Return the date or NEVER that an Assignment supplies, else None."""
    if item.never is not None:
        return NEVER
    return item.date
