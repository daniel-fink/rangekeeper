"""Resolve immutable mathematics and explicit solve roles without a solver import."""

from dataclasses import dataclass
from collections.abc import Mapping
from types import MappingProxyType
from uuid import UUID

from .._records import Record
from .._schema.records import Constraint, Expression, Quantity, Value
from ..model import Model
from ..model._index import walk
from ..model.definitions import measure
from ..references import SpecificationResolver
from ..specification import Specification, Composition, compose, validate
from ..units import UnitSystem, default_units
from .errors import UnsupportedProblem


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
    value_units: Mapping[UUID, str]
    assignments: Mapping[UUID, Quantity]
    unknowns: tuple[UUID, ...]
    assertions: tuple[Assertion, ...]
    units: UnitSystem


def prepare(
    specification: Specification,
    *,
    resolver: SpecificationResolver,
    units: UnitSystem = default_units
) -> Prepared:
    """Validate a concrete composition and normalize assignments to Measure units.

    Only imposed mathematics is prepared. Unused reporting queries stay passive.
    Recorded quantities and estimates never supply missing fixed roles. This slice
    publishes Model-owned scalar Values; local Specification Values and ordered
    optimization objectives are rejected explicitly before invoking a backend.
    """
    composition = compose(specification, resolver=resolver)
    validate(composition, resolver=resolver, units=units).raise_if_invalid()
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
            if isinstance(record, Value):
                values[record.id] = record
            elif isinstance(record, Expression):
                expressions[record.id] = record
            elif isinstance(record, Constraint):
                declarations.append((document, record))

    if model.system is not None:
        collect(model.system, model.id)
    model_values = set(values)
    for contributor in composition.contributions:
        for formulation in contributor.record.formulations or ():
            collect(formulation, contributor.id)
    roles = set(requirements.unknowns or ()) | {
        a.value for a in requirements.assignments or ()
    }
    if not roles <= model_values:
        raise UnsupportedProblem(
            "Specification-local Value publication requires a later adapter"
        )
    value_units = {
        id: measure(model.definitions, value.measure).units
        for id, value in values.items()
        if value.measure is not None
    }
    assignments = {
        item.value: units.convert(item.quantity, to=value_units[item.value])
        for item in requirements.assignments or ()
    }
    return Prepared(
        model,
        composition,
        MappingProxyType(values),
        MappingProxyType(value_units),
        MappingProxyType(assignments),
        requirements.unknowns or (),
        tuple(
            Assertion(document, declaration, expressions[declaration.predicate])
            for document, declaration in declarations
        ),
        units,
    )
