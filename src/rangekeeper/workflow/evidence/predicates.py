"""Bounded table selection, keeping booleans distinct from numeric values."""

from collections.abc import Mapping
from dataclasses import dataclass

from rangekeeper.shared import structured as _structured
from rangekeeper.workflow.operation import _Failure, _invoke
from rangekeeper.workflow.evidence import Method


def equal(actual, expected):
    """Exact-type equality avoids treating a boolean flag as a count of one."""
    return type(actual) is type(expected) and actual == expected


@dataclass(frozen=True, slots=True)
class Predicate:
    """An explicit set of accepted values, without executable expressions."""

    column: str
    values: tuple

    def __post_init__(self):
        if type(self.column) is not str or not self.column.strip():
            raise ValueError("Predicate column requires nonempty text")
        if not isinstance(self.values, (list, tuple)):
            raise TypeError("Predicate values require an ordered sequence")
        object.__setattr__(
            self,
            "values",
            _structured.freeze_mapping({"values": self.values})["values"],
        )

    @classmethod
    def from_mapping(cls, value):
        if not isinstance(value, Mapping):
            raise TypeError("Predicate requires a mapping")
        if set(value) not in ({"column", "equals"}, {"column", "in"}):
            raise ValueError("Predicate requires column and exactly one of equals/in")
        return cls(
            value["column"], (value["equals"],) if "equals" in value else value["in"]
        )

    def matches(self, value):
        return any(equal(value, expected) for expected in self.values)


def select_where(evidence, *, predicate: Predicate, columns=None, name=None):
    """Select matching rows through the same Claim and Issue projection as select."""
    from rangekeeper.workflow.evidence import tabular

    if not isinstance(predicate, Predicate):
        raise TypeError("Expected Predicate")
    from rangekeeper.workflow.evidence.validation import prepare

    prepared = prepare(evidence)

    def execute(operation):
        if predicate.column not in evidence.data.columns:
            raise _Failure("missing_column", "Selection references an absent column")
        selected = tabular._select(
            prepared,
            row_ids=tuple(
                r.id
                for r in evidence.data.rows
                if predicate.matches(r.values[predicate.column])
            ),
            columns=columns,
            name=name,
        )
        if selected.output is None:
            raise _Failure(
                selected.diagnostics[0].code, selected.diagnostics[0].message
            )
        return selected.output

    return _invoke(
        Method(code="rk.tabular.select_where", version="1"),
        {
            "column": predicate.column,
            "values": predicate.values,
            "columns": columns,
            "name": name or evidence.name,
        },
        {"evidence": prepared.fingerprint},
        execute,
    )
