"""Assemble generated immutable records from finite equation declarations."""

from .._schema.records import Binding, Constraint, Formulation
from ._identity import identify, identify_tree


def construct(id, operation, equations, values):
    expressions = tuple(
        identify_tree(id, operation, key, expression) for key, expression in equations
    )
    constraints = tuple(
        Constraint(
            id=identify(id, operation, key, "constraint"), predicate=expression.id
        )
        for (key, _), expression in zip(equations, expressions)
    )
    return Formulation(
        id=id,
        name=operation,
        expressions=expressions,
        constraints=constraints,
        bindings=tuple(
            Binding(name=f"value_{index}", value=value)
            for index, value in enumerate(dict.fromkeys(values))
        ),
    )
