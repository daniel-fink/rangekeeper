"""Resolve immutable mathematics and explicit solve roles without a solver import."""

from dataclasses import dataclass
from collections.abc import Mapping, Callable
from types import MappingProxyType
from uuid import UUID

from .._records import Record
from .._schema.records import Constraint, Expression, Quantity, Value, Movement
from ..model import Model
from ..model._index import walk
from ..model.definitions import measure
from ..references import SpecificationResolver
from ..specification import Composition, validate
from ..units import UnitSystem, default_units
from .errors import UnsupportedProblem
from . import symbols
from .._schema.records import Decision, Reference, Assignment


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
    values: Mapping[UUID, Value]
    value_units: Mapping[str, str]
    assignments: Mapping[str, Quantity]
    unknowns: tuple[str, ...]
    assertions: tuple[Assertion, ...]
    units: UnitSystem
    references: Mapping[str, Reference]
    decisions: tuple[Decision, ...] = ()


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
    validate(composition, resolver=resolver, units=units).raise_if_invalid()
    checkpoint()
    assert composition.model_id is not None
    model = resolver.load_model(composition.model_id)
    requirements = composition.requirements
    if requirements.objectives:
        raise UnsupportedProblem(
            "ordered optimization objectives are not supported by scalar feasibility execution"
        )
    values: dict[UUID, Value] = {}
    expressions: dict[UUID, Expression] = {}
    declarations: list[tuple[UUID, Constraint]] = []

    def collect(root: Record, document: UUID) -> None:
        for record, _, _ in walk(root):
            checkpoint()
            if isinstance(record, Value):
                values[record.id] = record
            elif isinstance(record, Expression):
                expressions[record.id] = record
            elif isinstance(record, Constraint):
                declarations.append((document, record))

    if model.system is not None:
        collect(model.system, model.id)
    model_values = {
        r.id for r, _, _ in walk(model._record) if isinstance(r, (Value, Movement))
    }
    for contributor in composition.contributions:
        for formulation in contributor.record.formulations or ():
            collect(formulation, contributor.id)
    role_references = list(requirements.unknowns or ()) + [
        a.target for a in requirements.assignments or ()
    ]
    decisions: tuple[Decision, ...] = ()
    policy_assignments: tuple[Assignment, ...] = ()
    if requirements.policy is not None:
        unknown_tokens = {symbols.key(ref) for ref in requirements.unknowns or ()}
        if any(
            symbols.key(binding.target) in unknown_tokens
            for point in requirements.policy.points
            for binding in point.observations
        ):
            raise UnsupportedProblem(
                "policy observation targets an endogenous unknown; sequential numerical policies are unsupported"
            )
        from ..policies.evaluation import evaluate
        from ..policies.observation import PolicyCapabilityError

        try:
            policy_result = evaluate(requirements.policy, model=model)
            checkpoint()
        except PolicyCapabilityError as error:
            raise UnsupportedProblem(str(error)) from error
        decisions = policy_result.decisions
        policy_assignments = policy_result.assignments
        role_references.extend(a.target for a in policy_assignments)
    if any(ref.target not in model_values for ref in role_references):
        raise UnsupportedProblem(
            "Specification-local Value publication requires a later adapter"
        )
    references = {symbols.key(ref): ref for ref in role_references}
    value_units = {
        token: symbols.units_for(model, ref) for token, ref in references.items()
    }
    assignments = {
        symbols.key(item.target): units.convert(
            item.quantity, to=value_units[symbols.key(item.target)]
        )
        for item in (*(requirements.assignments or ()), *policy_assignments)
    }
    return Prepared(
        model,
        composition,
        MappingProxyType(values),
        MappingProxyType(value_units),
        MappingProxyType(assignments),
        tuple(symbols.key(ref) for ref in requirements.unknowns or ()),
        tuple(
            Assertion(document, declaration, expressions[declaration.predicate])
            for document, declaration in declarations
        ),
        units,
        MappingProxyType(references),
        decisions,
    )
