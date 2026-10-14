"""Stable declaration identities independent of recorded amounts and array insertion."""

from collections.abc import Sequence
import json
from uuid import UUID, uuid5
from rangekeeper.schema.records import Binding, Constraint, Expression, Formulation


def identify(owner: UUID, *parts: str | UUID) -> UUID:
    return uuid5(
        owner, json.dumps([str(part) for part in parts], separators=(",", ":"))
    )


def identify_tree(
    owner: UUID, operation: str, key: str, expression: Expression
) -> Expression:
    """Give each owned occurrence a distinct path identity, preserving operand order."""
    data = expression.to_data()

    def visit(node, path):
        if isinstance(node, dict):
            if "id" in node:
                node["id"] = str(identify(owner, operation, key, path))
            for name, value in node.items():
                visit(value, path + "/" + name)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, path + "/" + str(index))

    visit(data, "expression")
    return Expression.from_data(data)


def declare(
    id: UUID,
    name: str,
    equations: Sequence[tuple[str | UUID, Expression]],
    values: Sequence[UUID],
) -> Formulation:
    """Own named equations with stable occurrence IDs and whole-Value bindings."""
    entries = tuple((str(key), expression) for key, expression in equations)
    if len({key for key, _ in entries}) != len(entries):
        raise ValueError("duplicate equation key")
    operation = name
    expressions = tuple(
        identify_tree(id, operation, key, expression) for key, expression in entries
    )
    constraints = tuple(
        Constraint(
            id=identify(id, operation, key, "constraint"), predicate=expression.id
        )
        for (key, _), expression in zip(entries, expressions)
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
