"""Stable declaration identities independent of recorded amounts and array insertion."""

import json
from uuid import UUID, uuid5
from .._schema.records import Expression


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
