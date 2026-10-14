"""Resolve immutable mathematics and explicit solve roles without a solver import."""

from dataclasses import dataclass
from collections.abc import Mapping, Callable
from types import MappingProxyType
from uuid import UUID

from rangekeeper.schema.records import Constraint, Expression, Quantity, Value, Movement
from rangekeeper.model import Model
from rangekeeper.schema.index import walk
from rangekeeper.shared.references import SpecificationResolver
from rangekeeper.specification import Composition
from rangekeeper.specification.validation import prepare as validate_prepared
from rangekeeper.shared.units import UnitSystem, default_units
from rangekeeper.run.execution.errors import UnsupportedProblem
from rangekeeper.model.scope import target_units
from rangekeeper.schema.records import DecisionOutcome, Reference, Assignment


@dataclass(frozen=True)
class Assertion:
    """One imposed predicate and the revision owning its Constraint declaration."""

    document: UUID
    constraint: Constraint
    predicate: Expression


@dataclass(frozen=True)
class Prepared:
    """A derived solve scope; never a serialized or independently authoritative schema."""

    model: Model
    composition: Composition
    value_units: Mapping[UUID, str]
    assignments: Mapping[UUID, Quantity]
    unknowns: tuple[UUID, ...]
    assertions: tuple[Assertion, ...]
    units: UnitSystem
    references: Mapping[UUID, Reference]
    outcomes: tuple[DecisionOutcome, ...] = ()


def prepare(
    composition: Composition,
    *,
    resolver: SpecificationResolver,
    units: UnitSystem = default_units,
    checkpoint: Callable[[], None] = lambda: None,
) -> Prepared:
    """Validate an existing composition and normalize assignments to Measure units.

    Only imposed mathematics is prepared. Unused reporting queries stay passive.
    Recorded quantities and estimates never supply missing fixed roles. This slice
    publishes Model-owned scalar Values; local Specification Values and ordered
    optimization objectives are rejected explicitly before invoking a backend.
    """
    validated = validate_prepared(composition, resolver=resolver, units=units)
    validated.report.raise_if_invalid()
    checkpoint()
    assert composition.model_id is not None
    model = validated.model
    assert model is not None
    requirements = composition.requirements
    if requirements.objectives:
        raise UnsupportedProblem(
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
    outcomes: tuple[DecisionOutcome, ...] = ()
    policy_assignments: tuple[Assignment, ...] = ()
    if requirements.policy is not None:
        unknown_tokens = {ref.target for ref in requirements.unknowns or ()}
        if any(
            binding.target.target in unknown_tokens
            for point in requirements.policy.decisions
            for binding in point.observations
        ):
            raise UnsupportedProblem(
                "policy observation targets an endogenous unknown; sequential numerical policies are unsupported"
            )
        from rangekeeper.specification.policy.evaluation import evaluate
        from rangekeeper.specification.policy.observation import PolicyCapabilityError

        try:
            policy_result = evaluate(requirements.policy, model=model, units=units)
            checkpoint()
        except PolicyCapabilityError as error:
            raise UnsupportedProblem(str(error)) from error
        outcomes = policy_result.outcomes
        policy_assignments = policy_result.assignments
        role_references.extend(a.target for a in policy_assignments)
    if any(ref.target not in model_values for ref in role_references):
        raise UnsupportedProblem(
            "Specification-local Value publication requires a later adapter"
        )
    references = {ref.target: ref for ref in role_references}
    value_units = {token: target_units(model, ref) for token, ref in references.items()}
    assignments = {
        item.target.target: units.convert(
            item.quantity, to=value_units[item.target.target]
        )
        for item in (*(requirements.assignments or ()), *policy_assignments)
    }
    return Prepared(
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
        outcomes,
    )
